# benchmarks/claims — does CrossAudit do what its README says?

A black-box acceptance harness. [`CLAIMS.md`](CLAIMS.md) turns each sentence of
the public README (and SECURITY.md) into a test with a pass criterion; this
directory runs those tests against a git ref of the product and writes one
results file per ref. The product is the thing under test: nothing here
patches it, and every disagreement is recorded rather than worked around.

## Run it

```bash
cd benchmarks/claims
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy \
  python3 run.py --ref main --out records/main
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy \
  python3 run.py --ref ba202d6 --out records/fix-branch
# a subset (dependencies are pulled in automatically), keeping the temp projects:
python3 run.py --ref main --out records/dev --only C06,C07,C14 --keep
```

`--ref` is a git ref of this repository or a local checkout path. Python 3.10+
and the standard library only; the C18 external signature check creates its own
small tooling venv and `pip install cryptography` into it (never into the
product's venv). Run with the proxy variables unset: a local proxy that
intercepts loopback urllib makes the product's provider calls go astray (the
harness also strips them from its own environment). A full run takes about
1.5 minutes per ref.

Outputs:

- `records/<label>/claims.jsonl` — one record per claim: id, verdict, one-line
  observation, every command run (argv, exit code, stdout/stderr tails), details.
- `records/<label>/evidence/<claim>/` — full stdout/stderr of every command
  (`cmd-NN-*.txt`), every request the fake providers received
  (`captures-*/NNN-<vendor>-<role>-<n>.json`, system + user prompt), and
  claim-specific files.
- `RESULTS-<label>.md` — the rendered table and score.

## How it works

1. **Install.** A fresh venv per run, installed exactly as the README's pip
   fallback says, with the GitHub URL replaced by this repository
   (`pip install "crossaudit @ git+file://<repo>@<ref>"`) so the product needs
   no network. Dependency wheels come from the local pip cache.
2. **One project per claim.** Each claim gets its own temp `HOME` (so the keys
   file, if any, lands there), runs the documented
   `crossaudit init <name> --no-console --auditor-vendor openai
   --auditor-model gpt-5.6-terra --generator-vendor anthropic
   --generator-model claude-sonnet-4-6`, with stdin not a terminal, the dummy
   keys in `CROSSAUDIT_AUDITOR_KEY` / `CROSSAUDIT_GENERATOR_KEY`, every proxy and
   unrelated `CROSSAUDIT_*` variable scrubbed, and `BROWSER` pointed at a
   script that only logs (so nothing opens a real browser and C28 can see
   whether anything tried). Claims that CLAIMS.md says build "after C0x" reuse
   that claim's project (C14, C23 after C07; C25 after C08; C29–C31 after C28).
3. **Pointing at the fakes.** The only edit to the generated project is the
   documented one: a `base_url:` line for each role in `crossaudit.yml`
   (`_ALLOWED_ROLE` accepts it) plus `CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT=1` in the
   environment, the README's opt-in for a non-built-in origin. The adapters
   already allow plain HTTP to loopback (`allow_insecure_localhost=True`), so
   no product change was needed. The pair stays `openai` ↔ `anthropic`. Other
   knobs some claims set (all documented in the README's Configuration
   section): `max_rounds`, `checks: science`, `authority.lone_model_blocker`,
   `isolation.minimum.parametric: false`.

## The fake providers (`fakeproviders.py`)

Two stdlib `ThreadingHTTPServer`s on random 127.0.0.1 ports:

- **OpenAI** `POST /v1/chat/completions`, JSON or `stream: true` SSE
  (`data:` chunks with `choices[0].delta.content`, a terminal chunk with
  `finish_reason` and `usage`, then `data: [DONE]`).
- **Anthropic** `POST /v1/messages`, JSON or SSE (`message_start`,
  `content_block_start`, `content_block_delta` text deltas,
  `content_block_stop`, `message_delta` with `stop_reason` and usage,
  `message_stop`).

Both are driven by one **scenario** object. The role of each request is read
from the first words of the system prompt the product sends (generator,
auditor, amend, distil, chat); the "round" is how many requests of that role
came before. Failures are a function of that count only, so the product's
retry/backoff cannot change what the fake does. Scenarios used: clean,
fix-on-2, always-blocked, dcl-fail, escape, overreach, truncated, HTTP-500,
clean-with-lock. Generator replies use the product's raw-file envelope
(`SUMMARY:` / `<<<CROSSAUDIT-OUTPUT-FILE path="…">>>` … `<<<END-…>>>` /
`NOTES:`), and write a complete science increment
(`experiments/2026-10-21-bench/{metadata.yml, results.json, SUMMARY.md,
bench.py}`) that passes both the default `general` checks and the `science`
profile. Auditor replies are the JSON object `auditor/validate.py` accepts,
citing the rule ids the fake reads out of the CONSTITUTION block of the
prompt it was sent. Every request (model, system prompt, user prompt, request
keys, whether an auth header was present — never its value) is captured to
disk.

## What is and is not tested

Tested: C01–C31, and from round 2 C33a (`pair` plan mode, with a logging fake
`gh`) and C34a, C34c–C34g (a local stdio MCP server, `fakemcp.py`, registered
through the console's `/api/mcp` and called by a `build`), as written in
CLAIMS.md, with the deviations each record names.
What the fakes cannot speak to is model *quality*: whether a real auditor
catches real defects, and whether a real generator follows the envelope. The
fakes also make every endpoint a "custom" one, so receipts truthfully record
that model-source (parametric) isolation cannot be asserted; C16/C17/C18 set the
documented `isolation.minimum.parametric: false` so the admission mechanism
can be exercised at all.

Not tested here (C32, C33b, C34b, C35, C36, listed in every results file): the
macOS app and its DMG, the live GitHub two-repository deployment, SSH/Slurm,
Streamable-HTTP MCP and the Skills UI, the published benchmark numbers, and
live-model audit quality.
