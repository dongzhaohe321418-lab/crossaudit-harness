# w1 — CLI i18n R4: the two residuals, and two boundaries nobody had drawn

Per D38. Round 3 of 3, so this aims at the boundaries rather than the symptoms.

## F3 residual — the emit boundary is common in fact now

The `ConfigDenial` branch called `print(_render_doctor(...))` and returned,
bypassing `_emit` entirely. With no project configured, `doctor --json` emitted a
Chinese human screen and **no JSON at all** — a parser met prose, and only on the
error route.

**My R3 guards seeded a configured project.** They proved producer fields on the
normal route and never enumerated the error route, so they sat on the happy path
where the defect is not. `error_paths=split` was the finding's own name and it
survived its own repair, which is the second time tonight a guard of mine tested
the wrong side of the thing it was named for.

    doctor --json --lang zh, in a directory with no project
      before   Chinese human screen, no JSON, exit 20
      after    {"ok": false, "checks": [...]}, 0 CJK, exit 20
      human route unchanged: still 8 CJK lines

Two guards, and the second is the boundary rather than the case:

* the error route emits parseable JSON and the human route still speaks Chinese;
* an **AST assertion over the shipped source** that `cmd_doctor` never hands
  `_render_doctor` to `print`. A branch that prints the screen directly cannot
  emit JSON, and that is precisely the shape a reviewer reads past.

## F2 residual — one sentence, where the person is standing

Withdrawing `build --lang zh` prevented a false claim; it did not disclose
anything. **A limitation recorded in a source comment and a findings file is not
disclosed** — the only people who read either are us.

The disclosure is now the line under the action that causes the switch:

    crossaudit build "…"
      此命令目前仍以英文作答          ← rendered only when the locale is not English

And the contradiction is gone: init said *"wave 1: init only"* while doctor said
*"wave 1: init, doctor"*. Both now use one `LANG_HELP` constant, and a guard
fails if the scope is ever written inline again — two copies is how they drifted.
`build`'s own help states that its output is English this wave, because build is
where the language stops.

## The aria-label finding — the mechanism was there, the entries were not

The observation was right that this survived every sweep. The measurement needs
correcting, and I would rather say so than quietly fix a different number:
`page.py`'s `renderLocaleAttributes()` already walks `placeholder`, `title` and
**`aria-label`** through `zhValue()`. Counting English literals in the source
measures the source, which is English by construction; what matters is what
`zhValue` returns.

Driven through the shipped translator:

    static aria-labels                      64
    already rendering in Chinese            59
    reaching a Chinese reader in English     5   ->  0

Four needed entries (`Cancel running task`, `Generated files`, `Toggle context
panel`, `Tools & Skills`). The fifth, `Switch to Chinese`, is set explicitly by
`applyLocale` and is **exempt by name** — with a test asserting the exemption is
real, because an exemption that stops being true is pre-approved English.

So: **74 was the count of literals; 5 was the count of gaps; the gap is closed.**
The finding was sound and the surface is real — a screen-reader user in Chinese
did meet English labels.

## The second boundary — server-side literals

One leak found by observation was indeed a boundary. Swept by walking
`console/*.py` for string constants assigned to user-facing fields:

    server-side user-facing literals found   25   (5 modules)
    reaching a Chinese reader in English     22   ->  0

`chats.py`'s *"Project history"*, *"Recovered chat"* and *"Deleted chat"* are the
reported ones; the rest are in `overview.py`, `projects.py`, `daemon.py` and
`server.py`. Two are **prefixes** carrying a reason after them, so they are
`ZH_PATTERNS` entries — an exact entry would never match the string a person
sees, which is the same trap as a fixed string carrying a count.

The guard sweeps the modules rather than listing the strings, so a new
server-side literal is covered because it was written.

`"/ project"` on `#branch-label` was investigated and withdrawn upstream; it is
clear, not open.

### `Files produced` is a THIRD population, not a second server-side leak

The condition-3 sweep reported it alongside `Project history`, and the two are
not the same category. Checked rather than assumed:

    "Files produced" lives at  page.py:5648 — CLIENT-side, inside a JS template
    reachable by the translator? YES — the MutationObserver at localizeTree(node)
                                 walks dynamically inserted nodes
    had a ZH entry?              no

So the server-side boundary (strings the text-node translator genuinely cannot
reach) is the 25 above. `Files produced` belongs to a different population:
**English built inside JavaScript string concatenation**, which the translator
does reach once inserted, and which was missing only its catalogue entry.

Measured, because two leaks from two instruments is a category with an unknown
population and the count is the answer:

    phrases JS renders between tags   133
    without a ZH entry                  8   ->  0

    Applies to · Dismiss notice · Files produced · Notice dismissed. ·
    Retry task · Stop requested. · Task interrupted safely · Task restarted.

Two failure modes, so two guards: one that every phrase comes back Chinese, and
one that the observer still re-localises inserted nodes — a complete catalogue
renders English if nothing walks the new DOM.

### The aria-label check is one level below the one that matters

The composer measures `unnamed=0` in the DOM tree and `unnamed=1` in the native
accessibility tree. **A screen reader uses the native one**, so a DOM-level pass
answers a question nobody asked — and my check sits lower still: it asserts the
label STRINGS have Chinese forms.

It cannot see whether a control reaches the AX tree with a name at all, and I
have written that limit into the guard itself rather than only here, so nobody
reads the green file as an answer to the accessibility question. The native-tree
check belongs to the accessibility harness and I cannot run it from here.

    what I established   64 static labels, 0 without a Chinese form
    what I did not       whether the native AX tree exposes a name for each one

## Mutations — 5 of 5 red, each anchored

    N1  the error route bypasses _emit again    RED  (2 tests, incl. the AST one)
    N2  the disclosure removed from the screen  RED
    N3  the help contradiction restored         RED
    N4  an aria-label loses its Chinese         RED
    N5  a server-side literal loses its Chinese RED

Each mutation asserts its anchor and fails loudly if the patch does not apply.


---

## S2 from the R4 audit — 25 vs 26 reconciled, and the missing thing was the UNIT

The auditor ran **my own helper** and read 26 where my report said 25. That rules
out "different questions": same predicate, same SHA, same code. So I executed it
rather than explaining it:

    helper returns rows       : 26
    DISTINCT values           : 25
    values appearing twice    :  1   — "Project history"
                                      chats.py:74 and chats.py:362

**Neither number is wrong and neither is the other one's floor.** 26 is
occurrences; 25 is distinct strings. The helper returns occurrences and I
reported distinct without saying which.

The useful part is that **the two units are the two halves of the work**:
**25 is the number of catalogue entries** to write, **26 is the number of code
sites** to key under the provenance ruling. A slice scoped on the wrong one is
short by exactly the number of strings written at more than one site.

Fixed by publishing the predicate where the number is produced: the helper's
docstring now states shape, files, method and unit, and the test pins **both**
numbers, so they cannot diverge unexplained again.

**The general form, which I would apply to every count I have given tonight:**
a count needs shape, files, method, paths — and **unit**. The unit is the one
nobody names, because within a single head it is obvious, and it is exactly what
made two correct measurements look like a contradiction.

That also means my earlier "at least 64" needs its unit stated: it is **distinct
values** (25 distinct + 39 distinct), not occurrences, and the occurrence count
for the 39 is unmeasured.
