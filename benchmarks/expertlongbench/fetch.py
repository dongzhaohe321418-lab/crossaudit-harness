"""Fetch the public ExpertLongBench tasks and pin them by digest.

The corpus is CC BY-NC-SA 4.0 (see NOTES.md section 7). We never redistribute it: this
script downloads it into a gitignored ``data/`` directory, and the only thing that enters
git is ``manifest.json`` -- filenames, sha256 digests, row counts and checklist item
names. No dataset text.

Usage::

    python -m benchmarks.expertlongbench.fetch            # download + verify against manifest
    python -m benchmarks.expertlongbench.fetch --verify   # verify what is on disk, download nothing
    python -m benchmarks.expertlongbench.fetch --rewrite-manifest   # deliberately re-pin

A digest that differs from the manifest is a hard failure. The upstream dataset is
mutable (it is a git repo on the Hub), and a silent corpus change would invalidate every
number we have published against it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
MANIFEST_PATH = HERE / "manifest.json"

DATASET_REPO = "launch/ExpertLongBench"
BASE_URL = f"https://huggingface.co/datasets/{DATASET_REPO}/resolve/main"

#: The seven publicly released tasks. T02, T05, T09 and T10 remain private (paper S-I.6).
PUBLIC_TASKS = (
    "T01LegalMDS",
    "T03MaterialSEG",
    "T04EduPAE",
    "T06HealthCNG",
    "T07ChemMDG",
    "T08BioPDG",
    "T11CyberRDG",
)

REQUIRED_FIELDS = ("id", "input", "raw_human_reference", "human_reference_checklist")


class FetchError(RuntimeError):
    """Raised on any digest mismatch, schema violation or download failure."""


@dataclass(frozen=True)
class TaskFacts:
    """Everything about a task file that is safe to commit."""

    task: str
    filename: str
    sha256: str
    bytes: int
    rows: int
    checklist_items: list[str]

    def to_json(self) -> dict:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "rows": self.rows,
            "checklist_items": self.checklist_items,
        }


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:  # pragma: no cover - corrupt download
                raise FetchError(f"{path.name}:{lineno} is not valid JSON: {exc}") from exc
    return rows


def describe(task: str, path: Path) -> TaskFacts:
    """Compute the committable facts about a downloaded task file.

    Also enforces the schema, because a schema drift upstream would break the scorer in
    a much more confusing way later.
    """
    rows = load_rows(path)
    if not rows:
        raise FetchError(f"{path.name} has no rows")

    for row in rows:
        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if missing:
            raise FetchError(f"{path.name}: row {row.get('id', '<no id>')} is missing {missing}")
        checklist = row["human_reference_checklist"]
        if not isinstance(checklist, dict) or not checklist:
            raise FetchError(
                f"{path.name}: row {row.get('id')} has a non-dict or empty human_reference_checklist"
            )

    # The checklist is the rubric; every row of a task must carry the same *set* of items,
    # otherwise "the fraction of checklist items" is not well defined for the task. Key
    # *order* is allowed to vary and does (T06HealthCNG ships 8 distinct orderings of the
    # same 29 items), so we compare and pin the sorted set.
    first_items = sorted(rows[0]["human_reference_checklist"])
    for row in rows[1:]:
        items = sorted(row["human_reference_checklist"])
        if items != first_items:
            extra = sorted(set(items) - set(first_items))
            missing = sorted(set(first_items) - set(items))
            raise FetchError(
                f"{path.name}: row {row.get('id')} has a different checklist to the first row "
                f"(extra={extra}, missing={missing}); the task rubric is not uniform"
            )

    return TaskFacts(
        task=task,
        filename=path.name,
        sha256=sha256_of(path),
        bytes=path.stat().st_size,
        rows=len(rows),
        checklist_items=first_items,
    )


def download(task: str, dest: Path) -> None:
    url = f"{BASE_URL}/{task}.jsonl"
    tmp = dest.with_suffix(".jsonl.part")
    try:
        with urllib.request.urlopen(url, timeout=300) as response:  # noqa: S310 - fixed host
            if response.status != 200:  # pragma: no cover - urlopen raises instead
                raise FetchError(f"{url} returned HTTP {response.status}")
            with tmp.open("wb") as handle:
                while chunk := response.read(1 << 20):
                    handle.write(chunk)
    except FetchError:
        raise
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise FetchError(
            f"could not download {url}: {exc}. "
            "This host usually needs a proxy; try "
            "https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897"
        ) from exc
    tmp.replace(dest)


def read_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def write_manifest(facts: dict[str, TaskFacts]) -> None:
    payload = {
        "dataset": DATASET_REPO,
        "source": f"https://huggingface.co/datasets/{DATASET_REPO}",
        "paper": "arXiv:2506.01241",
        "license": "CC BY-NC-SA 4.0",
        "note": (
            "Digests and row counts only. The corpus itself is never committed -- see NOTES.md "
            "section 7. Regenerate with --rewrite-manifest only when an upstream change has been "
            "reviewed on purpose."
        ),
        "tasks": {task: facts[task].to_json() for task in sorted(facts)},
    }
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify(facts: TaskFacts, pinned: dict) -> None:
    problems = []
    if facts.sha256 != pinned["sha256"]:
        problems.append(f"sha256 {facts.sha256} != pinned {pinned['sha256']}")
    if facts.rows != pinned["rows"]:
        problems.append(f"row count {facts.rows} != pinned {pinned['rows']}")
    if facts.checklist_items != pinned["checklist_items"]:
        problems.append("checklist items differ from the pinned rubric")
    if problems:
        raise FetchError(
            f"{facts.task} does not match the pinned manifest:\n  - "
            + "\n  - ".join(problems)
            + "\nThe upstream dataset has changed. Every number measured against the old digest is "
            "now unverifiable. Review the change, then re-pin with --rewrite-manifest and re-run "
            "the study."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", nargs="*", default=list(PUBLIC_TASKS), choices=list(PUBLIC_TASKS))
    parser.add_argument("--verify", action="store_true", help="check files already on disk; download nothing")
    parser.add_argument("--rewrite-manifest", action="store_true", help="re-pin the manifest to what is on disk")
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest()
    pinned_tasks = manifest.get("tasks", {})

    facts: dict[str, TaskFacts] = {}
    # Preserve pins for tasks we are not touching, so a partial fetch cannot silently
    # drop other tasks from the manifest.
    for task, pinned in pinned_tasks.items():
        if task not in args.tasks:
            facts[task] = TaskFacts(
                task=task,
                filename=pinned["filename"],
                sha256=pinned["sha256"],
                bytes=pinned["bytes"],
                rows=pinned["rows"],
                checklist_items=pinned["checklist_items"],
            )

    failures = []
    for task in args.tasks:
        path = DATA_DIR / f"{task}.jsonl"
        if not path.exists():
            if args.verify:
                failures.append(f"{task}: {path} is missing (run without --verify to download)")
                continue
            print(f"downloading {task} ...", flush=True)
            download(task, path)
        try:
            task_facts = describe(task, path)
        except FetchError as exc:
            failures.append(str(exc))
            continue
        facts[task] = task_facts

        if task in pinned_tasks and not args.rewrite_manifest:
            try:
                verify(task_facts, pinned_tasks[task])
            except FetchError as exc:
                failures.append(str(exc))
                continue
            status = "verified"
        else:
            status = "pinned" if args.rewrite_manifest or task not in pinned_tasks else "verified"
        print(
            f"  {task}: {task_facts.rows} rows, {len(task_facts.checklist_items)} checklist items, "
            f"sha256 {task_facts.sha256[:16]}... [{status}]"
        )

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    if args.rewrite_manifest or not pinned_tasks:
        write_manifest(facts)
        print(f"\nwrote {MANIFEST_PATH.name}")
    elif not args.verify:
        missing_pins = [t for t in args.tasks if t not in pinned_tasks]
        if missing_pins:
            write_manifest(facts)
            print(f"\nadded {', '.join(missing_pins)} to {MANIFEST_PATH.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
