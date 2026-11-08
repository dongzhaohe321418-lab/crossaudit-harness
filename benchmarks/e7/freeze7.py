"""E7 pre-test freeze (to be completed before any held-out E7 audit): until then, held-out audits are refused."""
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent / "records" / "FREEZE7_test.json"


def verify() -> None:
    if not MANIFEST.exists():
        raise SystemExit("no E7 freeze manifest: E7 held-out audits are not released")
    raise SystemExit("E7 freeze verification is not implemented yet")
