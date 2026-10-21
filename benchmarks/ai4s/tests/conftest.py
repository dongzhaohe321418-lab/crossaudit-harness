"""Fixtures for the AI4S corpus tests: one reduced corpus (2 seeds per domain)
generated once per session into a temporary directory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

AI4S = Path(__file__).resolve().parent.parent
if str(AI4S) not in sys.path:
    sys.path.insert(0, str(AI4S))

SEED = 20261021
SEEDS = 2


@pytest.fixture(scope="session")
def corpus(tmp_path_factory):
    import generate
    out = tmp_path_factory.mktemp("ai4s") / "corpus"
    generate.generate(SEED, out, seeds_per_domain=SEEDS)
    rows = [json.loads(line) for line in (out / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    return out, rows


def instance_files(out: Path, row: dict) -> dict:
    root = out / row["instance_id"]
    return {p: (root / p).read_bytes() for p in row["files_sha256"]}
