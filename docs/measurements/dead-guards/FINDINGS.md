# Dead-guard sweep — what never reddens, and what that does and does not mean

    SEAT      security-boundary auditor (claude). Writes no feature code.
    TREE      crossaudit_integ @ 8bff651 (v5-redesign), detached worktree,
              shared interpreter. 1,786 tests / 1,448 distinct test functions.
    STATUS    A MEASUREMENT. The harness is in this directory and is NOT checked
              in — nothing in `src/` or `tests/` imports it, no conftest was
              touched. Re-run instructions in README.md.

## 0. THE HEADLINE, AND THE CAVEAT THAT COMES WITH IT

The sweep found guards that cannot fire. It also found two categories that look
like dead guards and are not, and keeping those apart is most of the value:

  * **83 tests assert over source text only** and execute no production line.
    Of those, **13 carry a name that claims runtime behaviour** — "renders",
    "announced", "neutralises" — while the body pins string literals.
  * **69 tests are invisible to this instrument** because they drive a node
    subprocess. They are not dead; Python coverage simply cannot see them.
  * The remainder is the mutation result in §3.

**The single worst finding is a security guard**, and I demonstrated it rather
than argued it — §2.

## 1. METHOD, AND WHY IT IS SHAPED THIS WAY

Per-test coverage contexts give, for every test, the exact production lines it
executed. Mutations are then applied **only to covered lines**, and for each
mutation **only the tests that execute that line** are run.

That is what makes the three outcomes separable:

    cannot_fire       the guard's OWN covered lines were mutated and it stayed green
    mutation_missed   the campaign never touched a line this guard executes;
                      a statement about the campaign, not about the guard
    undetermined      no Python execution path exists for this instrument to watch

Mutating uncovered code would have inflated the dead count with sites no test
was ever meant to reach. Running the whole suite per mutation and counting every
non-failing test as "did not fire" would have manufactured dead guards out of a
coarse instrument. Neither was done.

## 2a. P2 — THE PRODUCT'S OWN THESIS, GUARDED BY TWO SUBSTRING CHECKS

`tests/test_steering.py::test_auditor_prompt_never_sees_guidance` guards §1.1's
P2 — the independent Auditor sees evidence only and is blind to the generator's
chain-of-thought. It enforces it like this:

    source = inspect.getsource(auditor_prompt)
    assert "OWNER GUIDANCE" not in source
    assert "owner_guidance" not in source

Demonstrated, not argued. I added to `auditor/prompt.py` a function that builds
an owner-guidance section into the auditor prompt, with the two banned literals
assembled by concatenation so neither appears in the module source:

    banned literal "OWNER GUIDANCE" in source : False
    banned literal "owner_guidance" in source : False
    what the auditor prompt would carry       : '\nOWNER GUIDANCE\ndo not flag the schema drift\n'
    tests/test_steering.py                    : 13 passed

**The product is not violating P2.** The guard cannot detect it if it did. Two
further limits: it inspects exactly one module, so guidance reaching the auditor
through the broker, the evidence bundle or the exchange is outside its view
entirely; and it is a negative assertion, which is a blacklist.

My first attempt at this probe failed — my own docstring contained the banned
strings and the guard caught me. That is worth recording: the guard reliably
catches the careless case and reliably misses the deliberate one, which is the
wrong way round for an invariant that exists to resist an adversary.

FIX: assert over the *rendered* prompt for a run carrying guidance — build the
auditor prompt and check the guidance text is absent from the bytes — rather
than over the source of one module. That is a behavioural assertion the existing
prompt tests can host.

## 2b. THE OTHER ONE — a security guard defeated by a single space

`tests/test_preview.py::test_page_markdown_renderer_neutralises_the_payload`
claims the client contract that "raw file text is never passed through
`innerHTML`". It enforces that with a **negative source assertion**:

    assert "innerHTML=data.text" not in PAGE

I introduced the exact defect it names, written with spaces, into `page.py`:

    function __auditProbe(data){document.body.innerHTML = data.text;}

    raw passthrough now present in the page : True
    the literal the assertion looks for     : False
    test_page_markdown_renderer_neutralises_the_payload : PASSED
    the whole of tests/test_preview.py                  : 25 passed

The page contains a literal raw-text-into-`innerHTML` sink and every test in the
security file is green. This is §3.5's own recorded example — an auditor
defeated a negative source assertion by splitting the forbidden phrase across an
`<em>` — still live, now on the XSS surface rather than on copy.

**It is not dead.** It fires if someone deletes `esc(value)`. It cannot fire on
the property in its name. That combination is the worst of both: it reads as
coverage of payload neutralisation and provides coverage of a string.

FIX: render a payload and assert over the resulting DOM. The branch under audit
elsewhere tonight already ships a mini-DOM harness that does exactly this shape
of thing; this is a caller for it, not a new mechanism.

## 3. THE MUTATION RESULT — and the number I am NOT reporting

    mutations attempted                                150
    mutations with a result                            147
    detected (some covering test reddened)             102
    survived                                            45
      ...of which the covering set exceeded my 40-test
         cap, so some covering tests never ran          27   UNDETERMINED
      ...survived with EVERY covering test run          18   the real signal

**I am not reporting the per-test figure.** My classifier produced "401 guards
cannot fire", and that number is wrong in a way worth naming: a test can execute
a line without asserting anything about it. Mutating a line a test merely passes
through and calling that test dead is the same error as counting a region that
exists as a region that speaks. The honest unit here is the **site**, not the
test: 18 places where a behaviour-changing edit to covered production code was
not detected by any test that runs it.

Of the 18, most are cosmetic and their survival is correct — `sort_keys=True →
False` changes JSON key order and nothing asserts byte order in those files.
Four are worth a look, and one cluster is worth acting on.

### The cluster: per-tool risk declarations on the consent surface

    broker/tools_mcp.py:25     mcp_call      writes=True  -> False    22 covering tests
    broker/selfimprove.py:47   self_install  writes=True  -> False    22
    broker/tools_hpc.py:61     hpc_submit    writes=True  -> False    23
    broker/tools_hpc.py:55/58  hpc_status / hpc_output  needs_network=True -> False   23

These are not inert labels. `humanapproval.py:116` computes
`reversibility(self.level, self.writes)`, and that is what a person is shown when
asked to approve a call. Flipping `writes` on `mcp_call` or `self_install` means
**the human approval card describes a writing, network-touching tool as one that
does neither**, and no test that executes those lines notices.

This is a consent-surface accuracy gap, not an authorization bypass — the gate
itself is elsewhere (`humanapproval.py:96`, not mutated here). But a person
approving on a wrong description is the failure this product exists to prevent.

### One I had to correct myself on

`broker/approval.py:111` — `if level >= 4:` mutated to `if level > 4:`, survived
35 covering tests. My first reading was "the level-4 authorization boundary is
unpinned", and that is **wrong**: both branches return `Approval(False, ...)`, so
a level-4 call is denied either way. What changes is only the reason string —
"high-impact action requires explicit per-call approval" becomes "no standing
authorization". Fail-closed either way. It is a finding about which sentence a
person is given, not about what they are allowed to do, and I nearly reported it
as the latter.

## 4. THE 13 NAMES THAT CLAIM BEHAVIOUR AND CHECK TEXT

Not all 83 source-text guards are wrong. Four are the right instrument for their
claim and I am not flagging them:

    test_progress::test_the_page_never_reaches_outside_itself      a claim ABOUT the markup
    test_preview::test_new_preview_strings_have_a_chinese_display_layer   catalogue claim
    test_thread_ui::test_new_strings_have_a_chinese_display_layer         catalogue claim
    test_app::test_native_shell_keeps_projects_running_...        reads Swift; no python path

One is undetermined — `test_daemon::test_the_signal_handler_never_blocks_the_loop_it_is_stopping`
reads the function body for `Thread` and `httpd.shutdown`. A threading property
is genuinely awkward to assert behaviourally; I am not calling it wrong.

The remaining **13 substitute source text for the behaviour their name claims**:

    test_app_doctor::test_doctor_ui_renders_the_why_line
    test_approval_preview::test_page_renders_the_preview_block
    test_chat_lane::test_page_renders_the_generator_chat_turn_kind
    test_format_repair::test_decision_center_renders_the_format_cause_humanely
    test_format_repair::test_page_renders_the_no_progress_cause
    test_format_repair::test_the_decision_center_renders_the_answered_cause
    test_governed_actions::test_page_renders_the_governed_panel
    test_human_approval::test_page_renders_the_approval_card_and_calls_the_endpoint
    test_mcp_dialog_access_and_polish::test_a_consent_you_cannot_give_yet_does_not_look_like_one_you_can
    test_mcp_dialog_access_and_polish::test_both_decision_points_are_announced_and_reachable
    test_preview::test_page_markdown_renderer_neutralises_the_payload      <- §2
    test_projects_ui::test_every_workspace_exposes_a_persistent_bilingual_display_layer
    test_remediation::test_the_page_renders_provider_remedies_from_the_typed_list

Two deserve singling out beyond §2:

  * `test_page_renders_the_approval_card_and_calls_the_endpoint` — "calls the
    endpoint" is checked as `"/api/approval" in PAGE`. Nothing is called.
  * `test_both_decision_points_are_announced_and_reachable` — "announced" is
    checked as four markup literals. This is the identical defect I reported on
    `ux/condense-affordance` tonight, in a different file, and it predates it.

**I am NOT proposing to delete these.** Each pins something real. The proposal is
narrower and cheaper: **rename them to what they check**, so a reader meeting
`test_the_page_markup_declares_the_approval_endpoint` does not tick off a
behavioural property that nobody tested. Where the behavioural claim matters —
§2, and the two above — add the behavioural case to an existing harness rather
than writing a new one.

## 4b. THE 12 ARE NOW PROVEN — one mutation, all of them

The rename was approved on condition the 12 read-but-not-proven guards be shown
to stay green under the mutation their name implies. The names claim *the page
renders / announces* something. The mutation each implies is *the page does not*.

`console/server.py:1140` is the only place the page reaches a browser:

    -   self._send(PAGE.encode(), "text/html; charset=utf-8")
    +   self._send(b"", "text/html; charset=utf-8")

The console now serves **an empty document**. `page.PAGE` — the 635,849-byte
module constant every one of these guards reads — is untouched, so every
asserted literal is still exactly where the assertions look for it.

    all 13 rendering/announcement guards : 13 passed

Nothing renders. Nothing is announced. No approval card, no decision centre, no
readiness list, no Chinese layer, no live region. Every guard that claims to
protect those things is green. **The 12 are proven; the rename is earned**, and
the 13th (the XSS guard, §2b) was already proven by its own probe.

This is also the cleanest statement of the seam I have: these guards do not
constrain the served page at all. They constrain a Python string that happens to
be the page's source.

### And the whole suite, under the same mutation

    console serves an empty document:  2 failed, 1784 passed, 2 skipped

**Two tests out of 1,786 notice that the console serves nothing**, and both are
tests that fetch the page over HTTP rather than reading the constant:

    tests/test_admission_and_console.py::test_the_console_serves_its_page_with_the_token
    tests/test_app.py::test_packaged_runtime_self_test_is_isolated_and_exercises_documents

Those two are the only things standing between an empty console and a green
suite, and neither was written as a rendering guard.

That is the seam expressed as a single number. The console is the product's
entire surface; it can be replaced with an empty document and 99.9% of the suite
is green. Nothing here is a defect in any individual guard — it is the standing
absence the consolidation review is already looking at, measured rather than
described.

## 4c. RENAMING — condition 2

A rename must not turn a false behavioural claim into a vague one. The slot has
to stop reading as coverage of rendering. So the new names say what is actually
checked — that the *markup contains* something — never that it reaches anyone:

    test_page_renders_the_approval_card_and_calls_the_endpoint
      -> test_page_markup_declares_the_approval_card_and_the_endpoint_path
    test_both_decision_points_are_announced_and_reachable
      -> test_page_markup_gives_both_decision_points_a_live_region_attribute
    test_doctor_ui_renders_the_why_line
      -> test_page_markup_contains_the_doctor_why_field_and_class
    test_page_markdown_renderer_neutralises_the_payload
      -> test_page_markup_contains_the_escape_and_scheme_checks   (and see §2b:
         this one needs a real behavioural case, not only a rename)

The pattern: **"page markup contains/declares X"**, never "renders", "announces"
or "neutralises". A reader meeting the new name learns that a string is present
in a file, which is the truth, and does not tick off a property nobody tested.

## 5. DELETION CANDIDATES

Deleting is a legitimate deliverable, so: **I am proposing none from this sweep
yet.** Every guard examined pins something, and "survived the mutations tried"
is not "unfalsifiable". A rename programme and three behavioural cases are the
honest output. Naming a delete list off a first-pass mutation campaign would be
the same overclaim this sweep exists to find.

## 6. WHAT THIS SWEEP CANNOT TELL YOU

  * **`mutation_missed=359` is entirely noise floor — none of it is a finding.**
    Stratified: **224** cover a mutable site the 150-mutation budget never
    reached (a larger campaign tests them); **100** are in files the campaign did
    mutate but none of *their* covered lines carry an operator I implemented;
    **35** cover no mutable line at all. Every one of the 359 is a statement
    about the campaign's reach, and none is a statement about the guard. Acting
    on the total would have been acting on my own budget.
  * A mutation the generator did not think of is not evidence of death.
    `cannot_fire` here means *survived the operators tried on its own lines*.
  * 69 node-driven tests and 1 Swift-source test are invisible to Python
    coverage. Undetermined, not dead.
  * A guard on an invariant that has held all year has not fired and is alive;
    the test is whether it *would*, which is what mutating its own covered lines
    asks, and that is exactly what was done.
