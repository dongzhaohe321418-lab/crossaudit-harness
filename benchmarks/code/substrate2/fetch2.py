"""Study 23 — fetch BigCodeBench v0.1.4 into benchmarks/code/data/ and pin its digest.

    python benchmarks/code/substrate2/fetch2.py

Apache-2.0. The file is gitignored like every other corpus here; what the study commits is
the frame record, not the corpus.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "bigcodebench.jsonl"
ROWS = "https://datasets-server.huggingface.co/rows"
DATASET, CONFIG, SPLIT = "bigcode/bigcodebench", "default", "v0.1.4"


def main() -> int:
    rows: list[dict] = []
    offset, total = 0, None
    while total is None or offset < total:
        query = urllib.parse.urlencode({"dataset": DATASET, "config": CONFIG, "split": SPLIT,
                                        "offset": offset, "length": 100})
        payload = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(f"{ROWS}?{query}", timeout=120) as response:
                    payload = json.load(response)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 4:
                    raise SystemExit(f"could not fetch {DATASET}: {exc}")
                time.sleep(2 * (attempt + 1))
        total = payload["num_rows_total"]
        batch = [r["row"] for r in payload["rows"]]
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                            for r in rows), encoding="utf-8")
    digest = hashlib.sha256(DATA.read_bytes()).hexdigest()
    print(f"{len(rows)} rows -> {DATA}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
