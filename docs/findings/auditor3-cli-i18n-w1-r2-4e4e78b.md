# Cross-vendor audit — CLI i18n wave 1, `4e4e78b`

Auditor: `auditor3` (Codex), independent of the Claude author.

Verdict: **MERGE AFTER FIXES** — 0 S0, 3 S1, 2 S2, 0 S3.

The detached checkout was `/tmp/crossaudit-audit3-cli-i18n-r2-4e4e78b` at
`4e4e78bbb04d58a178cbcc3cf4c6d06bd2f4722a`. The imported package was asserted
to be
`/private/tmp/crossaudit-audit3-cli-i18n-r2-4e4e78b/src/crossaudit/__init__.py`.
With the shared interpreter, the full result was **1,877 collected, 1,875
passed, 2 skipped, 0 failed** (`1875 passed, 2 skipped in 254.98s`). The checkout
was clean after all mutations were restored.

## Findings

### F1 — S1: keyed init says Ready while the immediately following doctor denies readiness

This is the same producer/consumer contradiction found at the earlier SHA and
it still executes on this tree. A real keyed `cmd_init` run prints `Ready` and
returns success; a real `cmd_doctor` against the project immediately returns 20
and prints `尚未就绪`. Init derives readiness only from
`_missing_credentials()` (`wizard.py:842-846`), while doctor also evaluates
whether the source install is admission-capable. The test named
`test_init_says_ready_only_when_doctor_would_agree` never drives doctor on its
keyed case. Setup completion is true, but the advertised doctor agreement is
false.

### F2 — S1: the reachable Chinese setup and build paths cross into English

The front-door decision is honest in isolation: not advertising `--lang` on an
otherwise English bare invocation avoids adding one isolated Chinese line.
The shipped wave as a whole is nevertheless **half-shipped**, because surfaces
which explicitly accept `--lang zh` cross into untranslated prose:

- Default Chinese init reaches `_open_console()` and prints English success or
  fallback instructions (`main.py:1351-1376`). A forced console failure ended
  with `The console did not start ... Start it yourself with: crossaudit
  console` after the Chinese setup.
- A real `build --lang zh` prints its banner, task/rules/round narration,
  provider failure and stop reason in English before its translated closing
  copy. This is the exact “what happened in Chinese, what to do in English”
  split the dispatch forbids.

The claimed end-to-end init test hard-codes `no_console=True`
(`tests/test_cli_i18n.py:93-106`). Replacing the real console-error prose with
`UNTRANSLATED SENTINEL` left
`test_the_whole_wizard_speaks_chinese_end_to_end` green by its own name. The
build test calls `i18n.t()` directly (`tests/test_cli_i18n.py:379-392`); forcing
production `_speak()` to select English left that test green by its own name.
These guards stop before the reachable consumers.

### F3 — S1: translated producer data leaks into doctor machine surfaces

On a project with an intentionally empty rules file, real `doctor --lang zh
--all` contains Chinese and real `--json doctor --lang zh` carries Chinese in
the `constitution rules` detail. `_render_doctor_full` promises every line
unchanged for a stable CI/script surface, but the producer stores
`i18n.t("doctor.constitution_rules.none")` into the shared check object
(`main.py:394-397`). The committed machine-surface test uses an earlier empty
project seam that does not reach this row. Correct translation at the producer
is wrong at these consumers.

### F4 — S2: fallback completion reporting is present only on selected paths

Deleting the reached Chinese key `doctor.admission_capable.label` at runtime
and executing real doctor produced the inline `[en]` marker but no final
`[i18n]` count/key summary. `_report_untranslated()` exists and init invokes it
(`main.py:1329,1334-1348`), but the normal doctor and build returns do not. The
feature therefore cannot support its claim that a partial translation is both
visible and countable on each shipped command.

### F5 — S2: the newest count guard is filed as producer coverage but stops at the catalogue

Production singular selection is correct: an independent call through
`wizard._show_and_agree()` rendered `1 rule`, not `1 rules`. The test named
`test_the_drafted_header_agrees_with_its_count`, however, says it is “Driven
through the shipped selection” while only reading catalogue entries; its
`inspect.getsource()` result is unused (`tests/test_cli_i18n.py:608-619`).
Changing the shipped selection at `wizard.py:449` to always choose `.plural`
left that named test green, and the entire 26-test i18n file remained green.
The test must execute that selection if it is to carry this claim.

This is **not a duplicate deletion** under D97. Changing the singular catalogue
entry itself to `1 rules` left the two general catalogue guards green and
reddened this test by its own name, so it uniquely guards catalogue text. Keep
that useful assertion and extend or refocus the test; do not delete it on
resemblance alone.

## Cleared suspicions and boundaries

- **F3 remains open.** `docs/findings/w1-bundle-reachability-b5b3ea5.md:62-83`
  says OPEN and explains that new code cannot alter the stale binary which is
  answering. D66, D77 and D82 retain that ruling. The branch's self-origin
  output and the merged app-side `path_identity()` reach different populations;
  neither closes the CLI-only PATH collision.
- **No duplicate mechanism found.** The app PATH detector and CLI self-origin
  identify different states. The console's browser strings and CLI catalogue
  serve different consumers. The one apparent plural-test duplicate failed
  the D97 subsumption test described above.
- **Frozen GUI parity is not established.** All evidence here executes the
  source CLI. It stops at terminal output and package identity; it says nothing
  about a frozen GUI bundle.
- **Current-integration ancestry changed during the audit.** The target was
  initially based on then-current `8bff651`; `v5-redesign` advanced to
  `85b05e8` (D97 only). At close, merge-base is still `8bff651`, so a rebase is
  needed. This audit is for committed SHA `4e4e78b` and does not automatically
  carry to the rewritten SHA.

## Independence declaration

My weakest independence is the product-policy judgement that the deliberately
English bare front door is honest while the branch overall is half-shipped.
The executable facts behind that judgement—the default console handoff, build
transcript, error remedy, and machine-output leak—are direct observations, but
the exact boundary at which a “present, not satisfied” language becomes a
shipping promise deserves a second policy reader.
