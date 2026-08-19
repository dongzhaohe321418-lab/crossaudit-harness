"""The auditor's context meter is fail-closed on every channel.

Overflow on ANY channel — increment, committed task, deterministic-check output,
or the governed-evidence projection — must set `bounded`, which run.py turns into
ESCALATE/BOUNDS_EXCEEDED. Previously three channels were fail-OPEN: a binary file
consumed no budget, the DCL json and the evidence rows were dumped uncapped, and
the byte meter counted code points, so multi-byte (CJK) content could sail several
times over the nominal cap. These lock those holes shut.
"""
from __future__ import annotations

import json

from crossaudit.auditor import prompt as pm


def test_small_inbound_audit_is_not_bounded_and_not_truncated():
    files = {"work/a.md": b"# Title\n\nA short, in-bound increment.\n"}
    prompt, bounded, _sha = pm.build("CONST", "abc123", {"total_hard_failures": 0},
                                     files, task="write a note")
    assert bounded is False
    assert "<truncated at the prompt bound>" not in prompt
    assert "COMMITTED TASK REQUIREMENTS" in prompt and "write a note" in prompt


def test_cjk_increment_over_the_byte_ceiling_is_bounded():
    # 100k CJK code points = ~300k UTF-8 bytes: under the old code-point meter it
    # slipped through; a true byte ceiling catches it.
    big_cjk = ("审" * 100_000).encode("utf-8")
    assert len("审" * 100_000) < pm.MAX_INCREMENT_BYTES          # code points: passes
    assert len(big_cjk) > pm.MAX_INCREMENT_BYTES                 # bytes: over
    _rendered, bounded = pm.render_increment({"work/big.md": big_cjk})
    assert bounded is True


def test_a_binary_file_consumes_budget_and_can_bound():
    # A text file that fills the budget, then a binary file: the binary used to
    # append for free and never trip the bound. Now it is fail-closed.
    filler = ("x" * pm.MAX_INCREMENT_BYTES).encode("utf-8")
    files = {"work/a.txt": filler, "work/z.bin": b"\x00\x01\x02\x03"}
    rendered, bounded = pm.render_increment(files)
    assert bounded is True
    assert "<binary" in rendered or "<omitted" in rendered


def test_oversized_dcl_output_forces_bounded():
    fat_dcl = {"total_hard_failures": 0,
               "note": "n" * (pm.MAX_DCL_BYTES + 10_000)}
    _prompt, bounded, _sha = pm.build("CONST", "abc123", fat_dcl,
                                      {"work/a.md": b"ok\n"})
    assert bounded is True


def test_oversized_evidence_projection_forces_bounded():
    fat_evidence = [{"tool": "web.fetch", "reason": "r" * 2000}
                    for _ in range(200)]
    assert len(json.dumps(fat_evidence)) > pm.MAX_EVIDENCE_BYTES
    _prompt, bounded, _sha = pm.build("CONST", "abc123", {"total_hard_failures": 0},
                                      {"work/a.md": b"ok\n"}, tool_evidence=fat_evidence)
    assert bounded is True


def test_ascii_truncation_output_is_unchanged_for_pure_ascii():
    # The byte meter must not change truncation of pure-ASCII content: byte and
    # code-point counts coincide, so an over-cap ASCII increment truncates to the
    # same bytes it always did (protects existing replay fixtures).
    over = ("a" * (pm.MAX_INCREMENT_BYTES + 50)).encode("utf-8")
    rendered, bounded = pm.render_increment({"work/a.txt": over})
    assert bounded is True
    body = rendered.split("---\n", 1)[1]
    assert body.startswith("a" * 100)  # real content, byte-accurate prefix
    assert "<truncated at the prompt bound>" in rendered
