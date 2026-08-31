# w1 — the Chinese layer was complete and unreachable

Per D38. Branch `fix/lang-reachable` off `v5-redesign@5a428b2`.

## 1. What was true

The mechanism was right and the catalogue was right. Three routes to it, all
closed:

    crossaudit --lang zh doctor   → argparse: invalid choice: 'zh' (verb)
    LANG=zh_CN.UTF-8  doctor      → English
    crossaudit --help | grep lang → nothing

**Not a coverage problem.** Until this is fixed every translation added is
unreachable, which is worse than the ~10% figure we have been tracking: that one
says some strings lack Chinese, this said a Chinese user cannot get Chinese at
all.

**One correction to the framing, because it changes where the guard belongs.**
This is not a bundle-vs-source split. `packaging/macos/core_entry.py` calls
`crossaudit.app.main`, and `app._dispatch` delegates every public command to the
same `cli.main.main` — so the packaged grammar *is* the source grammar. Driven
in source at the reported SHA, `--lang zh doctor` failed and `doctor --lang zh`
already worked. The bundle reproduced the source behaviour rather than differing
from it.

The guards still drive `crossaudit.app.main`, the packaged entry point, because
that is the claim worth holding even though the two agree today.

## 2. The three fixes

**The flag parses before the verb.** `--lang` was registered on the commands
only, so `--lang zh doctor` put `zh` where a verb belongs. It is now on the
top-level parser too.

**And the per-command flags use `argparse.SUPPRESS`.** This is the part that
would have silently undone the fix: `doctor` defines its own `--lang`, and an
option carrying a default *overwrites the global value whenever the person does
not repeat the flag*. The global flag would parse, change nothing, and nothing
would fail. Mutation L2 restores that default and the guards redden.

**The system locale is followed.** `LC_ALL`, then `LC_MESSAGES`, then `LANG`.
A neutral `C`/`POSIX` value means *no preference stated* and is stepped over
rather than treated as an answer — otherwise `LC_ALL=C LANG=zh_CN.UTF-8`, an
ordinary shell, ends the search before the person's real preference is read.
Only a language the catalogue serves is honoured; `fr_FR.UTF-8` defers to
English rather than selecting something that cannot be rendered.

Resolution order, in one place: **explicit flag → system locale → English.**

**`--help` documents it**: `--lang {en,zh}` now appears in the usage line and
the options list.

## 3. Executed, through the packaged entry point

    LANG unset            doctor              Not ready — 1 thing needs attention.
    LANG=zh_CN.UTF-8      doctor              尚未就绪 — 有 1 项需要处理。
    (no LANG) --lang zh   doctor              尚未就绪 — 有 1 项需要处理。
    LANG=zh   --lang en   doctor              Not ready — 1 thing needs attention.
    LANG=C / POSIX        doctor              English

Both Chinese lines above come from `crossaudit.app.main(...)` — the frozen
core's entry — not from the CLI module directly.

**Not verified on a freshly built DMG.** The bundle in `/Applications` is from
21 August, predates the i18n merge, and hung on `doctor`; I did not build a new
one. What I can claim is the packaged *entry point* and grammar, and I have not
claimed more.

## 4. Mutations — 4 of 4 red, and one of them found a missing guard

    L1  the global --lang is removed              RED (3 tests)
    L2  a per-command default overwrites it       RED (3 tests)
    L3  the system locale is ignored again        RED
    L4  the C/POSIX step-over is removed          RED — after a guard was added

**L4 was green on the first run**, and it was a real mutation rather than a bad
one. With `LC_ALL=C` alone the outcome is identical either way, so nothing I had
written could tell them apart; only `LC_ALL=C` *paired with* `LANG=zh_CN.UTF-8`
distinguishes stepping over a neutral value from treating it as an answer. That
pairing is now a named test.

## 5. Two tests changed as a consequence, and why

`test_every_command_the_readme_shows_actually_exists` took `next(a.choices for a
in parser._actions if a.choices)` — the *first* action with choices. A global
option carrying `choices=` now precedes the subparsers, so it compared the
README against `{en, zh}`. It names the `_SubParsersAction` now, which is what
it always meant.

`test_init_and_doctor_state_the_same_wave_scope` pinned `help=LANG_HELP` at two
occurrences; there are three now that the top-level flag shares the same
sentence. The property is unchanged — one sentence, shared by every
registration — and the number moves only when a registration is added on purpose.


---

## Follow-up: two of the three remaining items resolved by checking rather than fixing

**`--lang` IS in `--help`, and has been since `8e8e295`.** Driven through the
packaged entry point at every level:

    crossaudit --help          --lang {en,zh}   present
    crossaudit doctor --help   --lang {en,zh}   present
    crossaudit init --help     --lang {en,zh}   present

**A hypothesis for the observation, and it is one of ours.** On this machine
`which -a crossaudit` resolves to the framework `bin`, and that binary reports
`crossaudit 3.2.0 (receipt schema 2)` — the August pip install. A shell running
`crossaudit --help | grep -i lang` gets **3.2.0**, which has no `--lang` at all.
That is D40/F3 biting a verification rather than a user. Checkable in one
command: `which crossaudit && crossaudit --version`. Offered as a hypothesis —
running the bundle core directly would not hit it.

**What WAS missing, and is the real form of the point**: the help listed the flag
and never said what it is for. Now that the default follows the system locale,
overriding it is the flag's only purpose, and a person on a Chinese system who
wants the English original — to quote in a report, or to search for — had no
reason to try it. Fixed:

    --lang {en,zh}   language for this command; overrides your system
                     locale (wave 1: init and doctor only)

Guarded on the purpose rather than the presence, and mutation L5 (help stops
saying what the flag is for) reddens it.

**`CROSSAUDIT_LANG` is correctly ruled out** and I would have been wrong to
build it. I confirmed independently that no such variable appears in `src/`.

## The verification-method question, answered plainly

**The defect was NOT invisible in source.** Driven at the pre-fix SHA `5a428b2`:

    source            crossaudit --lang zh doctor  → invalid choice: 'zh'
    packaged entry    app.main(["--lang","zh",…])  → invalid choice: 'zh'

Identical, because `core_entry.py` calls `crossaudit.app.main` and
`app._dispatch` hands every public command to the same `cli.main.main`. The
bundle reproduced source behaviour. I am saying so because the conclusion drawn
from "invisible in source" — that guards must run against the frozen binary —
does not follow from this defect, and acting on it would spend effort on the
wrong risk.

**What the guards do reach**: `crossaudit.app.main`, the packaged entry point,
which is the grammar and locale resolution the frozen core executes. All 18
tests in the file drive it.

**The honest gap, stated rather than substituted.** No test in the suite runs the
actual PyInstaller binary. `test_product_readiness.py` asserts the build script
*contains* `CrossAuditCore --self-test`; it is a string check on the script, not
an execution of the core. Building the binary takes minutes and is not on the
test path, so **packaging-class failures — a module PyInstaller does not bundle,
a missing data file, an import hook — remain uncovered by the suite.** This
defect was not in that class; a future one could be, and nothing here would
catch it.
