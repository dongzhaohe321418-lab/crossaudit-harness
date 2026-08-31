# w1 — CLI i18n wave 1, R3: the five findings from auditor3

Per D38. Branch `agentA/cli-i18n-wave1`, rebased onto current `v5-redesign`.

**The framing I am taking from the manager**: my branch was green inside a green
four-branch staging tree — 1,968 passed, 0 failed — and it had three S1s. The
suite could not see any of them. That is the product's own thesis landing on our
merge queue, and it is the argument for the audit rather than against the work.

## F1 — S1 — CLOSED. Init said Ready; doctor denied it one command later

Not a translation bug. `init` derived readiness from `_missing_credentials()`
alone while `doctor` also weighed whether the install is admission-capable, so a
keyed setup printed **Ready** and the next command returned 20 and said
**尚未就绪** — in the person's own language, with the second line being true.

`_missing_credentials`'s own docstring claimed *"so `init` cannot report a state
that `doctor` will contradict a moment later"*. The claim was false in code.

**Fixed as one decision, not two that agree.** `doctor_shared.install_blocks()`
joins `constitution_state()` in the module that exists for exactly this class,
and both `cmd_doctor` and the wizard read it. Init withholds Ready when the
install blocks, and **says what remains** rather than only withholding.

    driven, source install with both keys present
      before   init: "Ready"        doctor: exit 20      CONTRADICTION
      after    init: not ready +
               names the admission remedy               doctor: exit 20   agree

The guard was the weak one the audit named: it asserted init printed Ready and
**never ran doctor**. It runs both now and asserts only that they *agree*,
because which answer is right depends on the machine and the agreement is the
property.

## F3 — S1 — CLOSED. Translated data reached the machine surfaces

`--all` and `--json` are a contract with a parser, and a parser does not read
Chinese: a script consuming doctor broke under `LANG=zh`, silently and only for
Chinese users.

**The line is drawn explicitly rather than by convention.** `detail` is the
machine field and is never translated; a line that needs a sentence in the
person's language names it with the new `detail_copy`, which only the human
renderer reads. The producer stores English; `_doctor_detail()` is the single
place translation enters the human view.

    doctor --lang zh, project on the note() branch
      before   --all: Chinese in the row   --json: Chinese in `detail`
      after    --all: 0 CJK   --json: 0 CJK   human view: 22 CJK lines

**The guard sits on the boundary, not on today's strings**: for every check a
real run produces, no `check`/`detail`/`fix` may contain CJK — so the next
producer that translates into `detail` is caught by the same test.

**And my first version of that guard did not work.** Its fixture used a
constitution with no headings, which takes the `add()` branch and never reaches
the row that leaked — the identical flaw the audit found in the committed test.
Mutation M3 stayed green and that is how I found it. The fixture now writes
`"No rules yet."`, which is what puts doctor on the `note()` branch.

## F2 — S1 — CLOSED, one half by finishing and one by withdrawing

* **init's console tail is translated.** `_open_console` printed English failure
  and remedy at the end of a Chinese setup. init is a translated flow and this
  is its tail; an English remedy there tells the person something broke. Four
  strings, both catalogues, shipped English wording unchanged.
* **`build` is no longer offered `--lang`.** Its banner and closing copy are
  translated, but the round-by-round narration is `RunEvent` prose from the
  agent loop; translating that needs a kind-to-catalogue mapping and is wave 2.
  Rather than ship "what happened in Chinese, what went wrong in English", build
  is **consistently one language** until the narration can follow. The help text
  no longer claims it: *"wave 1: init, doctor"*.

  The translated `build.*` strings stay in the catalogue as **present, not
  satisfied** — translated, not reachable — which is the state already recorded
  for the front door.

## F4 — S2 — CLOSED. Fallback reporting on every command

`_report_untranslated()` existed and only `init` and the denial path called it.
It now runs **once at the dispatcher**, so a command cannot be added that
silently drops the notice — the same reason the language set comes from
argparse rather than a list. It is skipped for `--json`, because a defect notice
printed into a machine surface would be F3 wearing another hat.

    deleting a reached zh key, real `doctor --lang zh`
      before   inline [en] marker, no [i18n] summary
      after    [i18n] 1 string(s) fell back … doctor.admission_capable.label

## F5 — S2 — CLOSED. My own guard that could not fail

`test_the_drafted_header_agrees_with_its_count` said it was *"driven through the
shipped selection"* and read catalogue entries; its `inspect.getsource()` result
was unused. Changing the shipped selection to always choose `.plural` left it
green.

**A decision can only be executed by a test if it has a name.** The choice is now
`wizard.drafted_header_key(count, attributed)`, called by production and by the
test. The catalogue assertion is kept, not deleted: the audit established it
uniquely guards the singular text (D97 subsumption).

## Mutations — 7 of 7 red, and two of them corrected me

    M1   init readiness reverts to credentials only     RED  F1 guard
    M2a  console failure reverts to English             RED  F2 guard
    M2b  build is offered --lang again                  RED  F2 guard
    M3   the producer translates into `detail` again    RED  F3 boundary guards
    M3b  the human renderer reads `detail`              RED  (10 tests)
    M4   the dispatcher stops reporting fallbacks       RED  F4 guard
    M5   the selection always chooses `.plural`         RED  F5 guard

Two mutations did not apply on the first attempt because my shell quoting
mangled the anchor, and both "passed" as a result. Re-run from files, M2a went
red and **M3 stayed green** — which is what exposed the fixture flaw above. A
mutation that silently fails to apply reports the same thing as a guard that
works, and only the anchor assertion tells them apart.
