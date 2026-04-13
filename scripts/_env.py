"""Tiny .env loader. No external dep.

Usage:
    from scripts._env import load_env
    load_env()  # populates os.environ from ./.env
"""
from __future__ import annotations

import os
from pathlib import Path


def load_env(path: Path | str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)
