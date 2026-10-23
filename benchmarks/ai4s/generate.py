#!/usr/bin/env python3
"""Generate the AI4S audit corpus (DESIGN.md §2, §8.1).

    python generate.py --seed 20261021 --out records/corpus \
        [--seeds-per-domain 10] [--domains a,b] [--classes D01,...]

Writes one directory per instance (``<out>/<instance_id>/...``, laid out as
the audited scope of a scaffolded science project) and ``<out>/manifest.jsonl``
(one row per instance, clean controls first within each template). Every
instance's random stream is ``random.Random`` seeded from
sha256(generation seed, domain, seed index), and every planter's from the same
plus the class and variant, so a subset run (``--domains``/``--classes``)
yields byte-identical instances to the full run for the instances it shares.

Byte-deterministic: no timestamps, no wall clock, fixed date 2026-10-21 in
the experiment slug, every map serialised in a fixed order. An existing
``--out`` is replaced only if it is empty or holds a previous corpus
(a manifest.jsonl or the .ai4s-corpus marker); anything else is refused.

Honest boundary: the corpus is synthetic. A clean instance is correct against
its own data by construction; nothing here says what real increments look like.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import domains  # noqa: E402
import planted  # noqa: E402


#: Written first into --out, so a run that failed half-way can be replaced.
MARKER = ".ai4s-corpus"


def files_sha256(files: dict) -> dict:
    return {p: hashlib.sha256(files[p]).hexdigest() for p in sorted(files)}


def manifest_row(inst, instance_id, cls=None, variant=None, plant_rec=None, expected=None) -> dict:
    return {"instance_id": instance_id, "pair_id": f"{inst.domain}-s{inst.seed}",
            "domain": inst.domain, "seed": inst.seed, "clean": cls is None,
            "defect_class": cls, "variant": variant, "planted": plant_rec,
            "expected": expected, "files_sha256": files_sha256(inst.files)}


def write_instance(out: Path, instance_id: str, files: dict) -> None:
    root = out / instance_id
    for rel in sorted(files):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[rel])


def iter_corpus(generation_seed: int, seeds_per_domain: int, domain_names, classes):
    """Yield (instance_id, Instance, manifest row) in manifest order."""
    for name in domain_names:
        mod = domains.get(name)
        for idx in range(seeds_per_domain):
            rng = random.Random(domains.instance_seed(generation_seed, name, idx))
            clean = mod.build_clean(rng, idx)
            cid = f"{name}-s{idx}-clean"
            yield cid, clean, manifest_row(clean, cid)
            for c in planted.TAXONOMY["classes"]:
                if classes and c["id"] not in classes:
                    continue
                for variant in c["variants"]:
                    if not planted.applicable(c["id"], variant, clean):
                        continue
                    prng = random.Random(f"{generation_seed}:{name}:{idx}:{c['id']}:{variant}")
                    new, rec, exp = planted.plant(c["id"], variant, clean, prng)
                    iid = f"{name}-s{idx}-{c['id']}-{variant}"
                    yield iid, new, manifest_row(new, iid, c["id"], variant, rec, exp)


def prepare_out(out: Path) -> None:
    if out.exists():
        ours = (out / "manifest.jsonl").exists() or (out / MARKER).exists()
        if any(out.iterdir()) and not ours:
            raise SystemExit(f"refusing to overwrite {out}: not empty and not a previous corpus")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / MARKER).write_bytes(b"")


def generate(generation_seed: int, out: Path, seeds_per_domain: int = 10,
             domain_names=None, classes=None) -> list:
    domain_names = list(domain_names or domains.DOMAIN_NAMES)
    unknown = [d for d in domain_names if d not in domains.DOMAIN_NAMES]
    if unknown:
        raise SystemExit(f"unknown domains {unknown}")
    prepare_out(out)
    rows = []
    for iid, inst, row in iter_corpus(generation_seed, seeds_per_domain, domain_names, classes):
        write_instance(out, iid, inst.files)
        rows.append(row)
    with open(out / "manifest.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=planted.TAXONOMY["generation_seed"])
    ap.add_argument("--out", type=Path, default=HERE / "records" / "corpus")
    ap.add_argument("--seeds-per-domain", type=int, default=planted.TAXONOMY["seeds_per_domain"])
    ap.add_argument("--domains", default="")
    ap.add_argument("--classes", default="")
    a = ap.parse_args(argv)
    doms = [d for d in a.domains.split(",") if d] or None
    classes = set(c for c in a.classes.split(",") if c) or None
    t0 = time.perf_counter()
    rows = generate(a.seed, a.out, a.seeds_per_domain, doms, classes)
    clean = sum(r["clean"] for r in rows)
    sys.stderr.write(f"{len(rows)} instances ({clean} clean, {len(rows) - clean} defective) "
                     f"in {time.perf_counter() - t0:.1f} s -> {a.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
