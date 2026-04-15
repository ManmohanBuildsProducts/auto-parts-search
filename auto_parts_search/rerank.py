"""T601 — LLM-based re-ranker for hybrid retrieval top-N candidates.

Applies DeepSeek V3 (chat) as a semantic re-ranker over the top-20 from
our hybrid BM25+v3 RRF pipeline. LLM brings world-knowledge for
Hindi/brand-as-generic/symptom queries where pure embedding retrieval
underperforms OpenAI.

Design:
  - Stateless function-call per query (simplest; parallelizable later)
  - JSON-structured output via response_format (not regex parsing)
  - Temperature 0.0, deterministic where possible
  - Graceful fallback: if LLM fails after retries, return original order
  - Target: <400ms p50, <$0.001 per query

Usage:
    from auto_parts_search.rerank import rerank
    top_ids = rerank(
        query="engine garam ho raha",
        candidate_ids=[...],   # 20 from hybrid
        candidate_docs=[...],  # corresponding doc texts
    )
    # Returns list[str], best-first, length <= len(candidate_ids)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import requests

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

RERANK_SYSTEM = """You are an expert Indian auto-parts mechanic evaluating search-result relevance for an auto-parts e-commerce search engine.

You understand Hindi/Hinglish ("patti" = brake pad, "gaadi ki battery" = car battery, "kicker" = kick starter), symptoms ("engine garam" = overheating → radiator/thermostat/coolant), brand-as-generic usage ("Mobil" = engine oil, "Amaron" = battery, "Bosch plug" = spark plug), misspellings ("break pad" → brake pad), and part numbers.

Re-rank the candidates by how well each matches the user's query intent. The FIRST item should be the single best match. Partial matches go in the middle. Irrelevant items go last.

Output ONLY a JSON object (no prose, no markdown fences):
  {"ranked": [1-indexed candidate numbers, best first]}

The array must contain every candidate number exactly once. Example for 20 candidates:
  {"ranked": [7, 3, 14, 1, 12, 19, 5, 8, 20, 2, 9, 17, 11, 4, 6, 15, 13, 16, 10, 18]}"""


@dataclass
class RerankerConfig:
    model: str = "deepseek-chat"
    temperature: float = 0.0
    max_tokens: int = 1500
    timeout: int = 60
    retries: int = 3


def _parse_ranked(content: str, n: int) -> list[int]:
    """Parse LLM output into validated 1-indexed rank list, best-first."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if content.startswith("json"):
            content = content.split("\n", 1)[1].strip()
    parsed = json.loads(content)
    ranked = parsed.get("ranked") if isinstance(parsed, dict) else parsed
    if not isinstance(ranked, list):
        raise ValueError(f"expected list, got {type(ranked).__name__}")
    valid: list[int] = []
    seen: set[int] = set()
    for x in ranked:
        try:
            i = int(x)
        except (TypeError, ValueError):
            continue
        if 1 <= i <= n and i not in seen:
            seen.add(i)
            valid.append(i)
    if not valid:
        raise ValueError(f"no valid indices in {ranked!r}")
    # Pad with any missing indices at the end (preserve LLM signal for ones it ranked)
    for i in range(1, n + 1):
        if i not in seen:
            valid.append(i)
    return valid


def rerank_with_deepseek(
    query: str,
    candidate_docs: list[str],
    api_key: str,
    config: RerankerConfig | None = None,
) -> list[int]:
    """Return a 1-indexed rank list (best first) over `candidate_docs`."""
    cfg = config or RerankerConfig()
    n = len(candidate_docs)
    numbered = "\n".join(f"{i+1}. {c[:200]}" for i, c in enumerate(candidate_docs))
    user_msg = f"QUERY: {query}\n\nCANDIDATES ({n}):\n{numbered}\n\nReturn JSON per the system message."

    body = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": RERANK_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "response_format": {"type": "json_object"},
    }

    last_err: Exception | None = None
    for attempt in range(cfg.retries):
        try:
            r = requests.post(
                DEEPSEEK_URL,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                json=body,
                timeout=cfg.timeout,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return _parse_ranked(content, n)
        except Exception as e:
            last_err = e
            if attempt < cfg.retries - 1:
                time.sleep(2 ** attempt)
    # Fallback: original order
    print(f"[rerank] FALLBACK to original order after {cfg.retries} retries: {last_err}", flush=True)
    return list(range(1, n + 1))


def rerank(
    query: str,
    candidate_ids: list[str],
    candidate_docs: list[str],
    config: RerankerConfig | None = None,
) -> list[str]:
    """Entry point. Returns reranked candidate_ids, best-first."""
    assert len(candidate_ids) == len(candidate_docs), "ids/docs length mismatch"
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY missing")
    ranks = rerank_with_deepseek(query, candidate_docs, api_key, config)
    return [candidate_ids[r - 1] for r in ranks]


if __name__ == "__main__":
    # Smoke test
    from dotenv import load_dotenv
    load_dotenv()
    cand_ids = ["a", "b", "c", "d"]
    cand_docs = [
        "Spark plug | plug, sparking plug | system: Ignition",
        "Brake pad (front) for Maruti Swift",
        "Engine oil filter, universal fit",
        "Skoda Genuine Parts - Part Number 6U7853952 PLATFORM",
    ]
    out = rerank("garam engine", cand_ids, cand_docs)
    print("rerank order:", out)
