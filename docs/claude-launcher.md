# Claude Code Launcher Spec

This document records the verified reverse path for Cairnspan: Codex launching Claude Code through the user's local authenticated Claude Code installation.

## Verified Entrypoint

Observed on 2026-07-08:

- `claude --version`: `2.1.201 (Claude Code)`.
- PowerShell resolves `claude` to `<claude-wrapper.ps1>`.
- The wrapper calls `<claude-native.exe>`.
- The native executable is launchable directly.

Claude Code supports noninteractive execution with:

```powershell
claude -p --output-format json "<prompt>"
```

Relevant flags from local `claude --help`:

- `-p`, `--print`: print response and exit.
- `--output-format text|json|stream-json`: machine-readable output for `--print`.
- `--input-format text|stream-json`: prompt input mode for `--print`.
- `--permission-mode acceptEdits|auto|bypassPermissions|manual|dontAsk|plan`: permission behavior for the session.
- `--tools ""`: disable all built-in tools for no-edit probes.
- `--tools "Bash,Edit,Read"` or `--allowedTools` / `--disallowedTools`: explicit tool scoping when edits are expected.
- `--no-session-persistence`: avoid saving/resuming a Claude Code session for one-shot probes.
- `--max-budget-usd <amount>`: cap API spend for `--print`.
- `--safe-mode`: disable customizations while keeping auth, model selection, built-in tools, and permissions. Cairnspan enables this by default and adds `--disable-slash-commands`, empty `--setting-sources`, and `--no-chrome` as defense in depth.
- `--mcp-config` and `--strict-mcp-config`: scope MCP configuration for a run.

Do not use `--bare` for Cairnspan's default path. Local help states that bare mode never reads OAuth/keychain auth and requires `ANTHROPIC_API_KEY` or an API key helper, which defeats the OAuth-backed product thesis.

## Current Provider-Policy Boundary

Rechecked against Anthropic's primary documentation on 2026-07-11:

- Anthropic documents `claude -p` as its programmatic CLI interface for scripts and CI/CD: <https://code.claude.com/docs/en/headless>.
- Anthropic documents subscription OAuth from `/login`, plus a long-lived `CLAUDE_CODE_OAUTH_TOKEN` for scripts where browser login is unavailable: <https://code.claude.com/docs/en/authentication>.
- Cairnspan does not use `setup-token`, read credential files, or receive an OAuth token. It launches the unmodified installed client and lets that client manage authentication.
- Anthropic prohibits third-party developers from offering Claude.ai login or routing Free, Pro, or Max credentials on behalf of users, and recommends API-key or supported-cloud authentication for products and services: <https://code.claude.com/docs/en/legal-and-compliance>.
- As of 2026-07-12, Anthropic documents a separate monthly Agent SDK credit for subscription-backed Agent SDK and `claude -p` usage, effective 2026-06-15. Treat the amount and billing behavior as provider-controlled and recheck before pressure testing: <https://code.claude.com/docs/en/legal-and-compliance>.

Conclusion: the owner-local launcher follows a documented official-CLI scripting path and does not perform the prohibited credential-broker pattern. That is not a provider approval of Cairnspan. Do not extend this conclusion to hosted login, token extraction or replay, multi-user credential routing, resale, pooled usage, or shared production automation. Those uses require API-key or managed-provider authentication unless Anthropic explicitly confirms otherwise.

## Live Probe Evidence

This Codex-origin no-tools probe succeeded with network-enabled execution:

```powershell
cmd /c claude -p --output-format json --permission-mode dontAsk --tools "" --no-session-persistence --max-budget-usd 0.10 "Reply with claude-cairnspan-ok and no other text."
```

Observed result:

- return code: `0`
- JSON `type`: `result`
- JSON `subtype`: `success`
- JSON `is_error`: `false`
- JSON `result`: `claude-cairnspan-ok`
- session id: captured in the private receipt
- total cost: `$0.00735`

A sandboxed run without network had previously returned `ConnectionRefused`, so live reverse probes require network access just like Codex live probes.

The first live run through `start_claude_session.py` succeeded on 2026-07-08:

- return code: `0`
- status: `succeeded`
- final: `claude-cairnspan-ok`
- session id: captured in the private receipt
- total cost: `$0.011209`

The first launcher attempt failed before model work because Claude Code requires `--verbose` with `--output-format stream-json`. The launcher now adds `--verbose` automatically.

Safety note: an earlier stream init listed configured Claude MCP tools even though `--tools ""` was set, so the launcher now defaults to `--strict-mcp-config`. The 2026-07-10 strict live probe reported zero tools and zero MCP servers.

## Implemented Script

`skills/cairnspan/scripts/start_claude_session.py` implements the reverse launcher.

The script mirrors `start_codex_session.py` where practical:

- stdlib-only Python
- `--cwd`
- `--out-dir`
- `--prompt-file`
- `--execute` / `--dry-run`
- `--claude-bin`
- `--origin-agent`
- `--timeout-seconds`
- `--permission-mode`
- `--tools`
- `--output-format`
- `--max-budget-usd`
- `--model`
- `--effort {low,medium,high,xhigh,max}`
- `--safe-mode`
- unsafe opt-ins for broad tool access, `bypassPermissions`, `--dangerously-skip-permissions`, or raw Claude args

Recommended command shape for a strict no-edit verification:

```powershell
<claude.exe> -p --output-format stream-json --verbose --permission-mode dontAsk --tools "" --safe-mode --disable-slash-commands --setting-sources "" --no-chrome --strict-mcp-config --no-session-persistence --max-budget-usd 0.05 "<prompt>"
```

When selected, the launcher places exactly one validated `--effort <value>`
pair immediately after the typed model pair. Raw Claude `--effort` and
`--model` arguments are launcher-controlled conflicts. Summary schema `0.12`
records `requested_model` and `requested_effort` on dry runs, configuration
errors, fake/live success, and failure; these are request evidence, not proof
of provider-side honoring.

For edit-capable runs, require explicit tool scope rather than defaulting to all tools.

## Artifact Contract

Write the same artifacts as the Codex launcher:

- `events.jsonl`: one JSON object per Claude output event. For `--output-format stream-json`, copy stdout lines directly. For `json`, wrap the single object as one JSONL event.
- `transcript.log`: stderr and launcher progress.
- `final.md`: best-effort final result from the Claude JSON `result` field or the final stream message.
- `cairnspan-summary.json`: run id, status, error kind, return code, origin agent,
  target agent, cwd, output paths, redacted command, prompt hash, requested
  model/effort, target version evidence, session id, usage/cost fields, init
  capability names, tool-use counts, policy observations, and transcript
  excerpt on failure.

The launcher must pass `stdin=subprocess.DEVNULL` to avoid the inherited-stdin hang class already found in the Codex launcher.

## Safety Defaults

- Default probes should use `--permission-mode dontAsk --tools ""`.
- Default probes should use `--safe-mode`; `--allow-customizations` is an unsafe opt-in because unattended `--print` skips workspace trust and project hooks/plugins can execute before model tool policy is useful.
- Safe-mode probes also disable slash commands, setting sources, and Chrome integration; receipts fail closed if empty-tool or strict-empty-MCP policy is contradicted by init/tool events.
- Default probes should use `--strict-mcp-config` so Claude Code's configured MCP servers are not exposed unless the caller opts in with a scoped MCP config or explicit configured-MCP allowance.
- Require a trusted existing `--cwd`; do not create a typoed workspace.
- Prefer the native `claude.exe` path over shell wrapper scripts when discovered.
- Redact prompt bodies from summaries and store prompt hashes.
- Do not log OAuth tokens or keychain contents.
- Scrub known raw API-key and alternate-provider environment overrides from the child by default; record names only.
- Prefer an explicit native `claude.exe`. PATH-selected `.cmd`, `.bat`, and `.ps1` wrappers are rejected unless explicitly acknowledged because shell wrappers can reparse prompt metacharacters.
- Reject zero-exit output without a terminal `result` event and session id, and fail closed on any malformed JSONL line.
- Do not use `--bare` unless the caller explicitly wants API-key-backed fallback.
- Treat noninteractive mode as trusted-workspace only, because local help says the workspace trust dialog is skipped with `--print`.
- Treat Claude usage as scarce during pressure tests. The separate monthly Agent SDK credit and other provider limits remain finite, and one successful stream probe emitted a seven-day rate-limit utilization warning of `0.98`.

## Mailbox Fallback

The `.cairnspan/requests` and `.cairnspan/responses` mailbox remains useful when live Claude Code launch is unavailable, but it is no longer the primary reverse path on this machine. Keep it as a resilience fallback after the Claude launcher exists.
