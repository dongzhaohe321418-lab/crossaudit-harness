# Security policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability, leaked credential, or
exploit. Use GitHub's private vulnerability reporting for this repository. If
that channel is unavailable, contact the maintainers listed in `pyproject.toml`
and include the affected version, reproduction steps, impact, and any proposed
mitigation. Do not include real API keys or user data.

## Supported version

Security fixes are made against the latest `main` release. CrossAudit 4.17.0 is
the current native-app release.

## Desktop trust boundary

The native shell embeds a loopback-only Python core. Every HTTP request must
carry an unguessable process token and an allowed localhost `Host` header. The
browser layer cannot retrieve stored credentials. Provider keys are kept in the
macOS login Keychain and loaded into the environment of the local core process
and of the project workers it starts, which call the providers. Other child
processes (Git, the GitHub CLI, OpenSSH, and the Codex runtime) are started
with provider key variables removed; MCP servers and allowed check commands
receive their own reduced environments. A stdio MCP server gets only the
thirteen variables `mcp._stdio_environment` names (seven POSIX ones such as
`PATH` and `HOME`, and six Windows runtime ones such as `SYSTEMROOT`) that are
set. Each MCP call the Generator makes is recorded in the project's evidence
ledger (`.crossaudit/evidence.jsonl`, mode 600) as its server, tool, argument
and result hashes, status, size and timing; the request text itself, which is
part of the Generator's streamed reply, stays in the project-private run
journal (`.crossaudit/runtime.sqlite3`, mode 600) that the console replays.

The process token is a bearer credential for running code on this Mac as you;
treat it like your account password. Whoever holds it can do anything the web
view can, including registering a local stdio MCP server, which starts the
named executable with the given arguments immediately, and replacing the
project's allowed check commands, whose entries become programs a build may
run. Nothing but the token gates either: the local-code approval on an MCP
registration is a field of the same request. The token travels in the console
URL, so it can appear in browser history, and while the console runs it is
written to the project's state directory (`.crossaudit/console.json` by
default, mode 600). A new token is issued each time the console starts. Do not
share the URL, paste it into an issue or a screenshot, or open it on a shared
account.

OpenAI subscription authentication is delegated to the pinned official Codex
runtime through its documented App Server protocol. CrossAudit never receives,
parses, logs, or serves OAuth tokens. Only allowlisted non-secret account state
is exposed to the UI. Subscription completions run in ephemeral, read-only,
network-disabled threads. Tool requests are refused at the protocol boundary,
and any command, file-change, web, or other tool event in a turn makes the
provider round fail closed: the turn's text is discarded, never used.
Anthropic consumer credentials are never captured or reused; Claude access
remains API/approved-enterprise only.

Project workers are independent processes with separate repositories, tokens,
locks, ledgers, and scoped write directories. Chats inside a Project share that
Project's governed repository but are associated with immutable Git trailers;
pin and title metadata stays local in a mode-600, gitignored state file.
Provider output is data, not a shell program: CrossAudit does not execute
generated commands automatically.

Environment Doctor exposes only tool paths, public version strings, readiness,
and local project paths. Its write API accepts a fixed action allowlist: open
Apple's Git installer, initialize the current project ledger, or save validated
project-local Git identity fields. Environment Doctor itself cannot accept a
command, executable, or arbitrary working directory from the web view; the MCP
and allowed-command settings described above can. Update discovery calls only
the public GitHub latest-release endpoint and sends no project or credential
data.

Closing the main window orders it out without terminating the native shell or
local core. The menu-bar item exposes the background state and an explicit Quit
command. On an unexpected core exit, the shell restores the window, reports the
failure, and requests user attention instead of silently pretending the
background service is healthy.

## Remote compute boundary

CrossAudit delegates authentication and host-key storage to the operating
system OpenSSH client. It does not read private keys or store passphrases.
Connections are non-interactive, disable local commands and forwarding, and
require a saved host key unless the user explicitly approves first-use trust.
A changed key is never replaced in the application.

Remote job scripts execute as the SSH user outside CrossAudit's local sandbox.
Every submission therefore requires explicit UI approval after the script and
resource request are visible. Host aliases, scheduler IDs, resource requests,
input hashes, and remote paths are kept in the project-private state directory;
credentials and file contents are not placed in the job ledger. Slurm and
detached workstation jobs remain remote-owned during local shutdown or network
loss. Cancellation validates scheduler/process IDs. Remote output downloads
validate both the project job identifier and a safe relative path before
streaming through the token-protected loopback endpoint.

## Distribution status

The 4.17.0 community DMG is ad-hoc signed and is not Apple-notarized. Verify the
published SHA-256 checksum before first launch. Organization-wide distribution
should wait for a Developer ID signed, notarized, and stapled artifact.
