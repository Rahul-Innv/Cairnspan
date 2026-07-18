---
name: cairnspan
description: Coordinate OAuth-backed two-way delegation between local coding agents such as Claude Code and Codex. Use when one agent needs to launch, hand off to, or request a response from another agent using the user's local OAuth-backed agent session rather than raw API keys, especially for Codex $imagegen, Codex MCP servers, Claude Code context, web search, isolated threads, captured logs, or cross-agent verification.
---

# Cairnspan

Use this skill when one local agent needs to delegate a bounded task to another agent and preserve the handoff, logs, result, and return path.

## Core Rules

- When the owner supplies a standing approval policy document, read it before
  proposing or executing a live edge. It may authorize bounded synthetic public-data
  probes without a new message, but it never authorizes its listed owner-
  decision boundaries or weakens any launcher, receipt, containment, or retry
  control.
- Start a fresh target-agent session by default. Resume only when the caller provides a specific target-agent thread/session id.
- Keep cairnspan outputs under a caller-chosen run directory, preferably outside product commits.
- Treat Claude Code and Codex as separate environments. One does not inherit the other's skills, MCP servers, plugins, image generation, auth, thread context, or approval state.
- Prefer the unmodified official target client and its own native authentication for owner-local, ordinary use. Do not impersonate the client or send provider requests directly with captured credentials.
- Do not store, print, copy, export, or replay OAuth tokens. Do not offer provider login or route subscription credentials on behalf of another user. Let each installed target client manage its own authentication.
- Treat public, shared, or commercial automation as a separate provider-policy gate. For Claude, use API-key or managed-provider authentication for shared production automation unless Anthropic explicitly confirms another method for that use case.
- Use Codex for Codex-only capabilities: `$imagegen`, Codex MCP tools, Codex web search, Codex plugins, or Codex-specific review/worktree flows.
- Use Claude Code for Claude-specific repo context, Claude Code skills, and Claude Code extension workflows when a launchable Claude entrypoint exists.
- Use the least sandbox needed. Default to read-only for probes and `workspace-write` only when edits are expected.
- Do not push, delete, reset, or run broad cleanup unless the caller explicitly authorizes that behavior in the prompt.
- Prefer `--prompt-file` over shell-quoted `--prompt` for real handoffs.
- Treat `danger-full-access` and raw Codex argument passthrough as unsafe; they require explicit opt-in and a reason.
- Keep `--max-depth`, `--timeout-seconds`, and `--max-output-bytes` bounded for repeated or two-way runs.
- Claude Code launches default to `--safe-mode`, disabled slash commands, empty setting sources, Chrome integration off, strict MCP isolation, no tools, and no session persistence.
- Treat init capabilities and tool-use counts in current receipts as policy evidence; an empty-tool or strict-empty-MCP contradiction fails closed.
- Raw API-key and alternate-provider environment overrides are removed from child processes by default; OAuth/keychain auth remains the intended path.
- Treat receipts inside a write-enabled target workspace as target-writable evidence. Use a parent-controlled receipt directory for any run whose target can edit the workspace.
- Probe and record the native target CLI version on every run. Use `--expected-cli-version` to pin an inspected version, and let parent routes carry that exact pin across all edges. A mismatch is a stop-before-launch event, not an automatic-upgrade trigger.
- Use the launchers' typed `--model` and `--effort` options when an edge requires
  a reviewed model/effort pair. Effort accepts only `low`, `medium`, `high`,
  `xhigh`, or `max`. Never substitute raw target arguments, a Codex `-c`
  expression, or a profile. Receipts prove what was requested, not what the
  provider honored; require separate observed-usage evidence when that matters.
- Use `scripts\run_two_way_route.py` for the bounded text route. Codex-first is
  live-verified; `--route-order claude-first` is deterministic fake-target
  tested but still requires a separately approved live-provider run. Do not
  emulate either order by letting one target recursively launch the next.
- Do not treat the text route as proof for image or binary handoffs. Follow `docs\artifact-route.md` for isolated staging, typed manifests, byte-level validation, and human approval before integration.
- Write-enabled hostile-workspace probes must use the typed
  `hostile-workspace-write` launcher profile. It owns the nonce prompt and fixed
  result path, requires a native version pin, a fresh parent-controlled receipt
  directory, and a sibling sentinel, and validates strict deltas. Its fake
  matrix passes; no native write-enabled matrix run is authorized by that fact.

## Quick Start

From this skill folder, run:

```powershell
python scripts\start_codex_session.py --cwd "C:\path\to\target" --out-dir "C:\path\to\private-receipts\fresh-run" --allow-outside-workspace-out-dir --prompt-file "C:\path\to\request.txt" --sandbox workspace-write --execute
```

Dry-run first when validating setup:

```powershell
python scripts\start_codex_session.py --cwd "C:\path\to\target" --prompt-file "C:\path\to\request.txt" --dry-run
```

The launcher writes:

- `events.jsonl`: Codex `--json` event stream.
- `transcript.log`: Codex stderr/progress output.
- `final.md`: best-effort final agent message.
- `cairnspan-summary.json`: redacted command, run id, paths, return code,
  requested model/effort, target version evidence, thread id, usage, and
  classified error when available.

Write-capable runs are rejected when `--out-dir` is inside `--cwd`. Their authoritative receipts must be in a fresh parent-controlled directory outside the target workspace.

Typed hostile-workspace write dry runs use these additional fields:

```powershell
python scripts\start_codex_session.py --cwd "C:\path\to\fresh-codex-case" --out-dir "C:\path\to\fresh-receipts" --allow-outside-workspace-out-dir --codex-bin "C:\absolute\path\to\codex.exe" --expected-cli-version "<exact inspected version>" --execution-profile hostile-workspace-write --hostile-write-nonce "<32-128 lowercase hex>" --protected-sentinel "C:\path\to\codex-sentinel.txt" --dry-run
```

The Claude form uses `start_claude_session.py`, `--claude-bin`, the same typed
profile inputs, and `--max-budget-usd 0.05`. Do not replace the typed prompt
with `--prompt`, enable raw arguments, use shell wrappers, or add tools/MCP.

For the parent lifecycle and exact owner-gated boundary, follow
`docs\hostile-write-matrix.md`. Prepare and inspect the case plan first. The
helper records launcher commands but never executes them. A live
`execute_command` requires authority for that one synthetic case and native
client under the active owner policy. Schema `0.4` binds `dry_run_command` and `execute_command` to
separate absent receipt roots, pins the launcher and parent Python runtime
identities, and forbids overwrite flags. The dry root must contain only its
no-execution summary; a dry-run lifecycle failure is preserved and cannot be
retried or merged into a replacement case. Close evidence with the exact
approved plan SHA-256 and an owner approval reference before cleanup; cleanup
removes only the marked direct-child workspace and preserves both receipt roots
plus the sibling sentinel. Current parent closure requires both launcher argv
digests, launcher/runtime hashes, the dry-run no-execution summary,
timeout/output limits, explicit parent/depth fields, native version, and typed
live-profile receipts to match the immutable case plan.

Useful support scripts:

- `scripts\doctor.py`: non-destructive setup checks, including separate bounded
  version and typed model/effort capability results for each selected client.
- `scripts\cli_version.py`: bounded, credential-scrubbed native CLI version probing used by both launchers and route plans.
- `scripts\scan_artifacts.py`: scan proposed public evidence or fixtures.
- `scripts\release_readiness.py`: evaluate source, public two-agent alpha, or
  production release gates without creating a commit, remote, tag, release,
  attestation, or provider run.
- `scripts\mailbox.py`: validate fallback request and response files.
- `scripts\mailbox_route_receipt.py`: close a shared-folder Codex-to-Claude-to-Codex exchange only after linked-message, identity, cleanup, prompt-hash, and exact-change checks pass.
- `scripts\workspace_manifest.py`: create and compare origin-side before/after manifests for no-edit probes.
- `scripts\hostile_write_case.py`: prepare one immutable synthetic hostile-write case with distinct dry/live receipt roots, close both command-specific summaries against an exact approval reference and plan hash, and guard parent-owned workspace cleanup; it never launches a provider.
- `scripts\synthetic_probe_case.py`: prepare and close one immutable,
  owner-policy-gated Codex effort, image-generation, or image-view
  proposal with distinct dry/live receipts, a pinned native identity, exact
  command hashes, independent event parsing, and strict workspace evidence; it
  never launches Codex itself.
- `scripts\synthetic_image_pilot.py`: require re-verified image capabilities,
  prepare exactly three immutable public-data image items, and enforce a
  plan-hash-approved, concurrency-1, zero-retry, daily-ledger-backed fail-stop
  controller; preparation and verification do not launch a provider.
- `scripts\run_two_way_route.py`: execute the fixed two-edge Codex-to-Claude text route with parent-controlled policy and closure receipts.
- `scripts\prepare_tracked_snapshot.py`: export a clean, tracked-HEAD-only, secret-guarded review workspace with a parent manifest.
- `scripts\prepare_critique_handoff.py`: validate Codex critique JSON and create a text-only Claude synthesis prompt.
- `scripts\critique_route_receipt.py`: prepare the immutable Codex-to-Claude critique plan and close it only after exact Claude policy, schema, cost, identity, and manifest checks pass.
- `scripts\prepare_artifact_handoff.py`: validate a bounded Claude design spec and render the minimized Codex image prompt.
- `scripts\artifact_manifest.py`: validate one static PNG and create the parent-owned typed artifact manifest.
- `scripts\artifact_route_receipt.py`: close the synthetic design-to-image route while keeping product integration behind a separate human approval.

## Delegation Workflow

1. Confirm the caller's goal, target workspace, permissions, and output directory.
2. Decide which agent should own the next turn. If the task does not require the other agent's unique capabilities, do the work locally instead.
3. Run the launcher in dry-run mode and inspect the command.
4. Run with `--execute` only after the command is scoped correctly.
5. Read `cairnspan-summary.json`, `final.md`, and relevant logs.
6. Report what the target agent did, where artifacts were saved, and any environment blockers.

## Two-Way Pattern

- Claude Code to Codex: run `scripts\start_codex_session.py` when Claude needs Codex capabilities.
- Codex to Claude Code: use the same handoff contract in reverse through Claude Code's verified `claude -p` noninteractive entrypoint and `scripts\start_claude_session.py`.
- Parent-orchestrated text closure: use `scripts\run_two_way_route.py` with fresh, non-overlapping disposable workspaces, a fresh protected receipt root, explicit native target executables, and dry-run inspection first. The default is `--route-order codex-first`; Claude-first remains local-test-only until its live gate is approved and closed.
- If the reverse entrypoint is unavailable in a given environment, write a handoff request file instead of pretending a live Claude response occurred.
- Preserve both sides' artifacts: request, command, stdout/stderr or transcript, final response, thread/session id, and changed-file summary.
- The bounded text route, one fresh repetition, shared-mailbox round trip, and typed synthetic image route are live-verified. Broader crash/quota/canary pressure and three-agent routing remain separate gates.

## Capability Probes

Use these small prompts before relying on Cairnspan runs overnight or unattended:

- Basic Codex: `Reply with cairnspan-ok and no other text.`
- Image generation: `Use $imagegen to generate a 512x512 simple test image and save it under .cairnspan/probe-image.png.`
- Image viewing: use `docs\probes\image-view.txt` with a synthetic
  `synthetic-view-probe.png` workspace input and
  `--require-image-capability image-view`.
- MCP: `List the Codex MCP servers/tools visible in this session and say whether the required tool is available.`
- Commit path: `Create one harmless probe file, commit it locally, and do not push.`
- Reverse handoff: `Create a Claude handoff request file and verify Claude Code can read and respond to it through the configured entrypoint.`

For Codex-owned image-tool probes, pass
`--require-image-capability image-generation` or `image-view`. Native
`--image` attachment/description is a separate capability and remains valid
under strict no-tool isolation. A final message that says the code-mode host or
image viewer failed is classified as `image_tool_unavailable`, even when Codex
exits zero.

## Claude Code Handoff Pattern

When Claude Code uses this skill, it should:

1. Locate this skill folder.
2. Run `scripts\start_codex_session.py`.
3. Pass a prompt file that names any required Codex capability, such as `$imagegen` or a named MCP server.
4. Inspect the summary and logs instead of assuming the Codex run succeeded.
5. Keep the Codex thread id if follow-up work is needed.

For a ready-to-paste Claude Code handoff prompt, read `references/claude-code-handoff.md`.
For the product plan, Claude launcher spec, and verification matrix, read `docs\plan.md`, `docs\claude-launcher.md`, and `docs\verification.md` from the Cairnspan project root.
For the current Codex effort and image proposal boundary, read
`docs\synthetic-probe-proposals.md`.

## Failure Classification

- Missing `codex` executable: local install/path issue.
- `WinError 5` or `Access is denied` for `codex.exe`: WindowsApps/package execution issue. Install or configure a Codex CLI executable that can be launched from PowerShell/Python, then pass it with `--codex-bin`.
- Authentication error: Codex CLI auth issue, not Claude Code auth.
- Skill missing: Codex skill install/discovery issue.
- MCP missing: Codex `config.toml` or plugin setup issue.
- Image generation unavailable: Codex account/model/skill capability issue.
- Permission denied in target repo: sandbox, worktree, or filesystem issue.
