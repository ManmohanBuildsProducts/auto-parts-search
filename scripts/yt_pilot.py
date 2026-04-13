"""YouTube Hindi auto-repair STT pilot.

End-to-end pipeline:
  1. For each channel URL, list recent videos via yt-dlp.
  2. Filter: 5-20 min, >5k views, last 3 years.
  3. Download audio only (opus/m4a/mp3) to data/external/yt_pilot/<ch>/<vid>.m4a
  4. For each audio, submit to Sarvam Saarika batch STT job.
  5. Poll until transcript is ready; save data/external/yt_pilot/<ch>/<vid>.json
  6. Report: total minutes transcribed, total Devanagari tokens, unique tokens
     that intersect with our KG vocab.

Resume-safe: skips audio/transcripts that already exist.

Usage:
    python3.11 -m scripts.yt_pilot --channels Mechanical\\ Tech\\ Hindi "Bike Point" ...
    (or run with default pilot channel list)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from scripts._env import load_env

load_env()

PILOT_ROOT = Path("data/external/yt_pilot")
SUMMARY = Path("data/external/processed/yt_pilot_summary.json")
SARVAM_BATCH_URL = "https://api.sarvam.ai/speech-to-text/batch"  # fallback if batch-job URL differs
SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"  # sync endpoint for short audio

# Pilot channel list — verified Hindi auto-repair channels (2026-04-14)
DEFAULT_CHANNELS = [
    "https://www.youtube.com/@MechanicalTechHindi",                       # 2W+4W, general
    "https://www.youtube.com/channel/UC_ac2x2rwzSwCDMwvcFooOA",            # My Mechanical Support
    "https://www.youtube.com/channel/UCs1QiQlbUsbMalNC8KB6Y_w",            # Bike Mechanic Mahesh
    "https://www.youtube.com/channel/UCxb7vkrqAAACtPXF-goCDPg",            # Tiwari car cure
    "https://www.youtube.com/channel/UCcDoa80KgEoXBKM0a-kjcpQ",            # Baba Automobile
]
PER_CHANNEL_VIDEOS = 10      # pilot: 3 channels × 10 = 30 videos
MIN_DURATION_SEC = 180        # 3 min
MAX_DURATION_SEC = 1200       # 20 min
MIN_VIEWS = 5_000
DEVANAGARI_TOKEN = re.compile(r"[\u0900-\u097F]+(?:[\s\-][\u0900-\u097F]+){0,3}")


def run(cmd: list[str], capture: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout)


def list_videos(channel_url: str, n: int) -> list[dict[str, Any]]:
    """Use yt-dlp to get metadata for the latest N videos on a channel."""
    cmd = [
        "yt-dlp", "-j", "--flat-playlist", "--playlist-end", str(n * 3),
        channel_url,
    ]
    proc = run(cmd, timeout=120)
    if proc.returncode != 0:
        print(f"  yt-dlp list failed: {proc.stderr[:400]}")
        return []
    vids = []
    for line in proc.stdout.splitlines():
        try:
            j = json.loads(line)
            vids.append({
                "id": j.get("id"),
                "title": j.get("title"),
                "duration": j.get("duration") or 0,
                "views": j.get("view_count") or 0,
                "channel": j.get("channel") or j.get("uploader") or channel_url,
                "url": f"https://www.youtube.com/watch?v={j.get('id')}",
            })
        except json.JSONDecodeError:
            continue
    return vids


def filter_videos(vids: list[dict]) -> list[dict]:
    out = []
    for v in vids:
        d = v.get("duration") or 0
        views = v.get("views") or 0
        if d < MIN_DURATION_SEC or d > MAX_DURATION_SEC:
            continue
        if views < MIN_VIEWS:
            continue
        out.append(v)
    return out


def safe_channel(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:60] or "channel"


def download_audio(video: dict, out_dir: Path) -> Path | None:
    """Download smallest usable audio. yt-dlp picks best format."""
    vid = video["id"]
    target = out_dir / f"{vid}.m4a"
    if target.exists() and target.stat().st_size > 0:
        return target
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio",
        "--extract-audio", "--audio-format", "m4a",
        "-o", str(out_dir / f"{vid}.%(ext)s"),
        video["url"],
    ]
    proc = run(cmd, capture=True, timeout=600)
    if proc.returncode != 0:
        print(f"  DL failed for {vid}: {proc.stderr[-300:]}")
        return None
    # yt-dlp may write .m4a or different ext depending on source
    for cand in [target, out_dir / f"{vid}.mp3", out_dir / f"{vid}.opus", out_dir / f"{vid}.webm"]:
        if cand.exists():
            return cand
    return None


def sarvam_stt(audio_path: Path, api_key: str, language: str = "hi-IN") -> dict | None:
    """Submit audio to Sarvam saarika:v2.5 via sync endpoint. Chunks audio
    to 25-sec windows (Sarvam's sync cap is 30 sec) and concatenates.
    """
    import requests
    probe = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path),
    ], timeout=30)
    if probe.returncode != 0:
        print(f"  ffprobe failed: {probe.stderr[:200]}")
        return None
    try:
        total_sec = float(probe.stdout.strip())
    except ValueError:
        return None

    chunk_sec = 25
    tmp_dir_path = Path(str(audio_path.with_suffix("")) + "_chunks")
    tmp_dir_path.mkdir(exist_ok=True)
    segments: list[str] = []
    ts = 0.0
    idx = 0
    while ts < total_sec:
        seg_path = tmp_dir_path / f"seg_{idx:04d}.wav"
        if not seg_path.exists() or seg_path.stat().st_size == 0:
            proc = run([
                "ffmpeg", "-y", "-ss", f"{ts:.2f}", "-t", str(chunk_sec),
                "-i", str(audio_path), "-ac", "1", "-ar", "16000",
                "-acodec", "pcm_s16le", str(seg_path),
            ], timeout=120)
            if proc.returncode != 0:
                print(f"  ffmpeg chunk failed @ {ts:.1f}s: {proc.stderr[-200:]}")
                break
        segments.append(str(seg_path))
        ts += chunk_sec
        idx += 1

    transcripts: list[dict] = []
    for i, seg in enumerate(segments):
        last_err = None
        for attempt in range(3):
            try:
                with open(seg, "rb") as f:
                    r = requests.post(
                        SARVAM_STT_URL,
                        headers={"api-subscription-key": api_key},
                        data={"model": "saarika:v2.5", "language_code": language},
                        files={"file": (Path(seg).name, f, "audio/wav")},
                        timeout=90,
                    )
                if r.status_code == 200:
                    payload = r.json()
                    transcripts.append({
                        "segment": i,
                        "start_sec": i * chunk_sec,
                        "transcript": payload.get("transcript", ""),
                        "language_code": payload.get("language_code"),
                    })
                    break
                else:
                    last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                    if attempt < 2:
                        time.sleep(2 ** attempt)
            except Exception as e:
                last_err = str(e)
                if attempt < 2:
                    time.sleep(2 ** attempt)
        else:
            print(f"  sarvam chunk {i} failed after 3 attempts: {last_err}")
            transcripts.append({"segment": i, "start_sec": i * chunk_sec, "transcript": "", "error": last_err})

    return {
        "audio_path": str(audio_path),
        "duration_sec": total_sec,
        "n_chunks": len(segments),
        "segments": transcripts,
        "full_transcript": " ".join(s["transcript"] for s in transcripts if s.get("transcript")),
    }


def load_kg_vocab() -> set[str]:
    import sqlite3
    conn = sqlite3.connect("data/knowledge_graph/graph.db")
    vocab = set()
    for (name,) in conn.execute(
        "SELECT name FROM nodes WHERE type IN ('part','alias','symptom','system')"
    ):
        if name and name.strip():
            vocab.add(name.strip().lower())
    conn.close()
    return vocab


def analyze(transcripts_dir: Path, kg_vocab: set[str]) -> dict:
    total_minutes = 0.0
    all_devan = set()
    all_texts: list[str] = []
    per_video: list[dict] = []
    for f in sorted(transcripts_dir.rglob("*.json")):
        j = json.loads(f.read_text())
        dur = j.get("duration_sec", 0)
        total_minutes += dur / 60.0
        text = j.get("full_transcript", "")
        all_texts.append(text)
        devan = set(m.group(0).strip() for m in DEVANAGARI_TOKEN.finditer(text))
        all_devan |= devan
        per_video.append({
            "file": str(f),
            "duration_min": dur / 60.0,
            "chars": len(text),
            "devanagari_tokens": len(devan),
        })
    blob = " ".join(all_texts).lower()
    vocab_hits = sum(1 for v in kg_vocab if v and v in blob)
    return {
        "total_videos": len(per_video),
        "total_minutes": round(total_minutes, 1),
        "total_chars": sum(len(t) for t in all_texts),
        "unique_devanagari_tokens": len(all_devan),
        "kg_vocab_hits": vocab_hits,
        "kg_vocab_total": len(kg_vocab),
        "per_video": per_video,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", nargs="*", default=DEFAULT_CHANNELS)
    ap.add_argument("--videos-per-channel", type=int, default=PER_CHANNEL_VIDEOS)
    ap.add_argument("--language", default="hi-IN")
    ap.add_argument("--skip-stt", action="store_true", help="Only download audio, skip STT")
    args = ap.parse_args()

    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key and not args.skip_stt:
        print("ERROR: SARVAM_API_KEY not set (check .env)", file=sys.stderr)
        sys.exit(1)

    PILOT_ROOT.mkdir(parents=True, exist_ok=True)

    selected: list[tuple[str, dict]] = []
    for ch in args.channels:
        ch_slug = safe_channel(ch.split("@")[-1].split("/")[-1])
        print(f"\n=== listing {ch} ===")
        vids = list_videos(ch, args.videos_per_channel)
        vids = filter_videos(vids)[: args.videos_per_channel]
        print(f"  selected {len(vids)} videos after filter")
        for v in vids:
            selected.append((ch_slug, v))

    print(f"\n=== total videos to process: {len(selected)} ===\n")

    for i, (ch_slug, v) in enumerate(selected, 1):
        ch_dir = PILOT_ROOT / ch_slug
        print(f"[{i}/{len(selected)}] {ch_slug} / {v['id']} ({v['duration']}s, {v['views']} views) - {v['title'][:70]}")
        audio = download_audio(v, ch_dir)
        if audio is None:
            continue
        if args.skip_stt:
            continue

        transcript_path = ch_dir / f"{v['id']}.json"
        if transcript_path.exists() and transcript_path.stat().st_size > 0:
            print(f"   ✓ transcript already exists")
            continue

        print(f"   transcribing {audio.name}...")
        t0 = time.time()
        result = sarvam_stt(audio, api_key, language=args.language)
        if result is None:
            continue
        result["video_meta"] = v
        transcript_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        dt = time.time() - t0
        full = result.get("full_transcript", "")
        print(f"   ✓ {len(full)} chars in {dt:.1f}s (audio {result.get('duration_sec', 0):.0f}s)")

    # Analyze
    kg_vocab = load_kg_vocab()
    summary = analyze(PILOT_ROOT, kg_vocab)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n=== PILOT SUMMARY ===")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_video"}, indent=2))
    print(f"(per-video details -> {SUMMARY})")


if __name__ == "__main__":
    main()
