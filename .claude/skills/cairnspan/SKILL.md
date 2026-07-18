---
name: cairnspan
description: Example Claude Code-facing shim for OAuth-backed delegation between Claude Code and Codex. Use only after pointing it at the canonical Cairnspan skill folder for this checkout.
---

# Cairnspan Claude Code Shim

This is an example local shim. The canonical skill and launcher live at:

`skills\cairnspan`

Use this shim when Claude Code should delegate a bounded task to Codex through the user's local Codex session.

Prefer prompt files over shell-quoted prompt text:

```powershell
python skills\cairnspan\scripts\start_codex_session.py --cwd "<target workspace>" --prompt-file "<request file>" --sandbox read-only --execute
```

Use `--sandbox workspace-write` only when Codex is allowed to edit files.

After the run, inspect:

- `cairnspan-summary.json`
- `final.md`
- `events.jsonl`
- `transcript.log`

Report whether Codex started, the thread id if present, what artifacts were produced, whether the required Codex capability was available, and the exact blocker if it failed.

Known Windows blocker: if `cairnspan-summary.json` reports `WinError 5` or `Access is denied` for `codex.exe`, the Microsoft Store/WindowsApps Codex package is visible but not launchable from unattended subprocesses. Install or configure a launchable Codex CLI and pass it with `--codex-bin`.

For the two-way plan, Claude launcher spec, and verification matrix, read `docs\plan.md`, `docs\claude-launcher.md`, `docs\verification.md`, and `docs\learnings.md` from the Cairnspan project root.
