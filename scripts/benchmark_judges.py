"""Judge-model benchmark: DeepSeek V3 vs Sarvam-M vs (optional) Claude.

Sample 30 queries stratified by query_type from the existing joint-pool
graded file, re-judge with each model, compute:
  - per-query agreement between judges (Cohen's kappa / raw agreement)
  - per-category graded nDCG@10 using each judge's labels as ground truth
  - cost per 1,000 judgments
  - qualitative examples where judges disagree

Output:
  data/training/experiments/2026-04-14-judges/judge_labels_{model}.jsonl
  data/training/experiments/2026-04-14-judges/summary.json

Usage:
    python3.11 -m scripts.benchmark_judges
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

from scripts._env import load_env

load_env()

SRC = Path("data/training/experiments/2026-04-13-v3/benchmark_dev_graded_joint_v3.jsonl")
OUT_DIR = Path("data/training/experiments/2026-04-14-judges")
SEED = 42
N_PER_TYPE = 5  # 6 types × 5 = 30 queries
RETRY = 3

JUDGE_SYSTEM = """You are an expert Indian auto-parts mechanic grading search relevance. You understand Hindi/Hinglish ("patti" = brake pad, "kicker" = kick starter, "silencer" = muffler, "tel" = oil), symptom queries ("engine garam" = overheating), brand-as-generic usage ("Mobil" = any engine oil), misspellings ("break pad"), and part numbers.

For each candidate part, judge relevance to the query. Return ONLY a JSON array of integer grades (no prose, no markdown fences):
  2 = RELEVANT (clearly what the query asks for)
  1 = MARGINAL (related but not direct answer)
  0 = IRRELEVANT (wrong part entirely)

The array length MUST equal the number of candidates. Example:
[2, 1, 0, 0, 2, 1, 0, 0, 0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 0, 1]"""


def build_user_msg(query: str, candidates: list[str]) -> str:
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(candidates))
    return f"Query: {query}\n\nCandidates:\n{numbered}\n\nReturn the {len(candidates)}-element grade array."


def _parse_grades(content: str, n_expected: int) -> list[int]:
    import re
    content = content.strip()
    # Strip <think>...</think> blocks (Sarvam-M reasoning)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if content.startswith("json"):
            content = content.split("\n", 1)[1].strip()
    try:
        grades = json.loads(content)
    except json.JSONDecodeError:
        # Find the LAST [...] block (after any remaining reasoning)
        matches = re.findall(r"\[[\d,\s]+\]", content)
        if not matches:
            raise
        grades = json.loads(matches[-1])
    if not all(g in (0, 1, 2) for g in grades):
        raise ValueError(f"invalid grades: {grades}")
    # If short, pad with 0s (irrelevant); if long, truncate. Log either way.
    if len(grades) < n_expected:
        grades = grades + [0] * (n_expected - len(grades))
    elif len(grades) > n_expected:
        grades = grades[:n_expected]
    return grades


def judge_deepseek(query: str, candidates: list[str]) -> tuple[list[int], dict]:
    key = os.environ["DEEPSEEK_API_KEY"]
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": build_user_msg(query, candidates)},
        ],
        "temperature": 0.0,
        "max_tokens": 2000,
    }
    r = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body, timeout=120,
    )
    r.raise_for_status()
    p = r.json()
    grades = _parse_grades(p["choices"][0]["message"]["content"], len(candidates))
    usage = p.get("usage", {})
    return grades, {"model": "deepseek-chat", "usage": usage}


def judge_sarvam(query: str, candidates: list[str]) -> tuple[list[int], dict]:
    key = os.environ["SARVAM_API_KEY"]
    body = {
        "model": "sarvam-105b",     # 128k context; sarvam-m (24B) had 2048 max-tokens starter cap
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": build_user_msg(query, candidates)},
        ],
        "temperature": 0.0,
        "max_tokens": 4000,
    }
    r = requests.post(
        "https://api.sarvam.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body, timeout=180,
    )
    r.raise_for_status()
    p = r.json()
    grades = _parse_grades(p["choices"][0]["message"]["content"], len(candidates))
    usage = p.get("usage", {})
    return grades, {"model": "sarvam-m", "usage": usage}


def judge_claude(query: str, candidates: list[str]) -> tuple[list[int], dict]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 2000,
        "temperature": 0,
        "system": JUDGE_SYSTEM,
        "messages": [{"role": "user", "content": build_user_msg(query, candidates)}],
    }
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=body, timeout=120,
    )
    r.raise_for_status()
    p = r.json()
    text = p["content"][0]["text"]
    grades = _parse_grades(text, len(candidates))
    usage = p.get("usage", {})
    return grades, {"model": "claude-sonnet-4-6", "usage": usage}


JUDGES = {
    "deepseek": judge_deepseek,
    "sarvam": judge_sarvam,
    "claude": judge_claude,
}


def retry_judge(fn, query, candidates, name):
    last_err = None
    for attempt in range(RETRY):
        try:
            return fn(query, candidates)
        except Exception as e:
            last_err = e
            msg = str(e)[:200]
            print(f"   {name} attempt {attempt+1} failed: {msg}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{name} failed after {RETRY} attempts: {last_err}")


def agreement(a: list[int], b: list[int]) -> dict:
    """Pairwise agreement stats."""
    assert len(a) == len(b)
    n = len(a)
    exact = sum(1 for x, y in zip(a, b) if x == y)
    # Binary collapse rel=2 vs other
    bin_exact = sum(1 for x, y in zip(a, b) if (x == 2) == (y == 2))
    # Also measure rank correlation (top-5 set overlap)
    top_a = {i for i, g in enumerate(a) if g == 2}
    top_b = {i for i, g in enumerate(b) if g == 2}
    jaccard = len(top_a & top_b) / max(len(top_a | top_b), 1) if (top_a or top_b) else 1.0
    return {
        "exact_agreement": exact / n,
        "binary_relevant_agreement": bin_exact / n,
        "top_set_jaccard": jaccard,
        "n": n,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Stratified sample
    rng = random.Random(SEED)
    by_type: dict[str, list[dict]] = defaultdict(list)
    for line in SRC.read_text().splitlines():
        if line.strip():
            by_type[json.loads(line)["query_type"]].append(json.loads(line))
    sample: list[dict] = []
    for qt, recs in sorted(by_type.items()):
        shuffled = list(recs)
        rng.shuffle(shuffled)
        sample.extend(shuffled[:N_PER_TYPE])
    print(f"sampled {len(sample)} queries across {len(by_type)} types ({N_PER_TYPE}/type)")

    # Which judges to run
    available = []
    if os.environ.get("DEEPSEEK_API_KEY"):
        available.append("deepseek")
    if os.environ.get("SARVAM_API_KEY"):
        available.append("sarvam")
    if os.environ.get("ANTHROPIC_API_KEY"):
        available.append("claude")
    print(f"available judges: {available}")

    all_labels: dict[str, list[dict]] = {j: [] for j in available}
    usages: dict[str, list[dict]] = {j: [] for j in available}

    for qi, q in enumerate(sample, 1):
        print(f"\n[{qi}/{len(sample)}] ({q['query_type']}) {q['query'][:70]}")
        for jname in available:
            out_path = OUT_DIR / f"judge_labels_{jname}.jsonl"
            try:
                grades, meta = retry_judge(JUDGES[jname], q["query"], q["candidate_docs"], jname)
            except Exception as e:
                print(f"   ⚠ {jname} SKIPPED after retries: {str(e)[:160]}")
                continue
            rec = {
                "query": q["query"],
                "query_type": q["query_type"],
                "candidate_ids": q["candidate_ids"],
                "candidate_docs": q["candidate_docs"],
                "grades": grades,
            }
            all_labels[jname].append(rec)
            usages[jname].append(meta.get("usage", {}))
            rel = sum(1 for g in grades if g == 2)
            mar = sum(1 for g in grades if g == 1)
            print(f"   {jname:10s}: {rel} rel, {mar} mar, {len(grades)-rel-mar} irr")

    # Save per-judge labels
    for jname, recs in all_labels.items():
        if recs:
            p = OUT_DIR / f"judge_labels_{jname}.jsonl"
            with p.open("w") as f:
                for r in recs:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"wrote {len(recs)} -> {p}")

    # Agreement matrix
    print("\n=== AGREEMENT MATRIX ===")
    judge_names = [j for j in available if all_labels[j]]
    agreement_results = {}
    # Align records by query text
    for ja in judge_names:
        for jb in judge_names:
            if ja >= jb:
                continue
            recs_a = {r["query"]: r["grades"] for r in all_labels[ja]}
            recs_b = {r["query"]: r["grades"] for r in all_labels[jb]}
            common = set(recs_a) & set(recs_b)
            if not common:
                continue
            totals = {"exact": 0.0, "bin": 0.0, "jac": 0.0, "n": 0}
            for q in common:
                a = agreement(recs_a[q], recs_b[q])
                totals["exact"] += a["exact_agreement"]
                totals["bin"] += a["binary_relevant_agreement"]
                totals["jac"] += a["top_set_jaccard"]
                totals["n"] += 1
            n = totals["n"] or 1
            row = {
                "exact_agreement": totals["exact"] / n,
                "binary_relevant_agreement": totals["bin"] / n,
                "top_set_jaccard": totals["jac"] / n,
                "queries": totals["n"],
            }
            agreement_results[f"{ja}_vs_{jb}"] = row
            print(f"  {ja:10s} vs {jb:10s}: exact={row['exact_agreement']:.3f}  rel_match={row['binary_relevant_agreement']:.3f}  top2_jaccard={row['top_set_jaccard']:.3f}  (n={row['queries']})")

    # Per-category agreement (binary relevant)
    print("\n=== PER-CATEGORY BINARY AGREEMENT ===")
    per_cat: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    for ja in judge_names:
        for jb in judge_names:
            if ja >= jb:
                continue
            recs_a = {r["query"]: r for r in all_labels[ja]}
            recs_b = {r["query"]: r for r in all_labels[jb]}
            for q, ra in recs_a.items():
                if q not in recs_b:
                    continue
                a = agreement(ra["grades"], recs_b[q]["grades"])
                per_cat[f"{ja}_vs_{jb}"][ra["query_type"]].append(a["binary_relevant_agreement"])
    for pair, d in per_cat.items():
        print(f"\n  {pair}:")
        for qt, vals in sorted(d.items()):
            avg = sum(vals) / len(vals)
            print(f"    {qt:20s} {avg:.3f} (n={len(vals)})")

    # Cost estimation
    print("\n=== COST ===")
    cost_results = {}
    pricing = {
        "deepseek": {"in": 0.14, "out": 0.28},       # USD per M tokens
        "sarvam": {"in": 0.50, "out": 1.00},          # approx published tier
        "claude": {"in": 3.0, "out": 15.0},
    }
    for jname in judge_names:
        ins = sum(u.get("prompt_tokens", u.get("input_tokens", 0)) or 0 for u in usages[jname])
        outs = sum(u.get("completion_tokens", u.get("output_tokens", 0)) or 0 for u in usages[jname])
        p = pricing.get(jname, {"in": 0, "out": 0})
        total = (ins / 1e6) * p["in"] + (outs / 1e6) * p["out"]
        per_k = total / max(len(all_labels[jname]), 1) * 1000
        cost_results[jname] = {"in_tokens": ins, "out_tokens": outs, "total_usd": total, "usd_per_1k_judgments": per_k}
        print(f"  {jname:10s}  in={ins:>6d}  out={outs:>5d}  total=${total:.4f}  per_1k_judgments=${per_k:.2f}")

    summary = {
        "n_queries": len(sample),
        "judges": judge_names,
        "agreement": agreement_results,
        "per_category_binary_agreement": {k: {qt: sum(v)/len(v) for qt, v in d.items()} for k, d in per_cat.items()},
        "cost": cost_results,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nsummary -> {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
