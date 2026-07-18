---
name: cairnspan
description: Example Codex-facing shim for OAuth-backed delegation between local coding agents such as Claude Code and Codex. Use only after pointing it at the canonical Cairnspan skill folder for this checkout.
---

# Cairnspan Codex Shim

This is an example local shim. The canonical skill and launcher live at:

`skills\cairnspan`

Use this shim when Codex needs to prepare, inspect, or run an Cairnspan handoff. Both canonical launchers and the bounded parent route now exist under `skills\cairnspan\scripts`.

Prefer prompt files over shell-quoted prompt text:

```powershell
python skills\cairnspan\scripts\start_claude_session.py --cwd "<target workspace>" --out-dir "<fresh parent-controlled receipt directory outside the target workspace>" --allow-outside-workspace-out-dir --prompt-file "<request file>" --permission-mode dontAsk --tools= --execute
```

Claude Code runs use `--safe-mode`, disabled slash commands, empty setting sources, Chrome integration off, `--strict-mcp-config`, and no tools by default. Current receipts record init capabilities and tool-use counts. Allow customizations, configured MCP, shell wrappers, or broader tools only after explicit review.

Any write-capable target profile must use a receipt directory outside its writable `--cwd`; the launchers enforce this boundary.

Write-enabled hostile-workspace work uses the canonical typed profile plus
`scripts\hostile_write_case.py` for parent preparation, closure, and guarded
cleanup. The helper never launches a provider. Read
`docs\hostile-write-matrix.md`; no native case is authorized by deterministic
fake-target evidence.

For a full text closure, use `run_two_way_route.py` with fresh disposable workspaces, a fresh parent-controlled receipt directory, and explicit native Codex/Claude executables. Dry-run first. The route is fixed Codex-to-Claude, depth/fan-out 1, zero retries, exact nonce artifacts, no tools, strict manifests, and aggregate limits.

Do not use the text route as an image-safety claim. Website/image workflows follow `docs\artifact-route.md` and require isolated staging plus a parent-generated typed artifact manifest before product integration.

After the run, inspect:

- `cairnspan-summary.json`
- `final.md`
- `events.jsonl`
- `transcript.log`

Report whether Claude Code started, the session id if present, what artifacts were produced, whether the requested handoff completed, and the exact blocker if it failed.

Known Windows constraint: prefer an explicit native `claude.exe`. PATH-selected shell wrappers require acknowledgement and are not used for authoritative live evidence.

For the two-way plan, Claude launcher spec, and verification matrix, read `docs\plan.md`, `docs\claude-launcher.md`, `docs\verification.md`, and `docs\learnings.md` from the Cairnspan project root.
