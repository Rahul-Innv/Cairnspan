# Minimal Live Verification Runbook

This runbook covers the standalone Claude Code strict-MCP/no-tools/no-edit regression probe. The full bounded text route has since been verified separately; use `docs/two-way-loop.md` and `run_two_way_route.py` for that route.

## Preconditions

- Use a disposable workspace under `.cairnspan/live/workspace` with no source code, secrets, agent instruction files, hooks, MCP configuration, or customizations.
- Use the native Claude executable, not `claude.cmd`, `claude.ps1`, or another shell wrapper.
- Keep receipts in the sibling `.cairnspan/live/receipts/<unique-run>` directory. That directory is outside the target `--cwd`, so the target cannot rewrite its own evidence.
- Confirm the exact command with a dry-run first.
- Keep the run private. Do not publish raw receipts.

## Prepare

```powershell
New-Item -ItemType Directory -Force ".cairnspan\live\workspace" | Out-Null
New-Item -ItemType Directory -Force ".cairnspan\live\manifests" | Out-Null

python skills\cairnspan\scripts\workspace_manifest.py snapshot `
  --root ".cairnspan\live\workspace" `
  --output ".cairnspan\live\manifests\before.json"
```

Check whether any raw API-key or alternate-provider variables are present by name only; do not print their values. The launcher removes its known sensitive auth/provider overrides from the child by default.

## Dry Run

Use a new receipt directory name for every attempt.

```powershell
python skills\cairnspan\scripts\start_claude_session.py `
  --cwd ".cairnspan\live\workspace" `
  --out-dir ".cairnspan\live\receipts\<unique-run>" `
  --allow-outside-workspace-out-dir `
  --prompt-file "docs\probes\claude-strict-mcp-noedit.txt" `
  --permission-mode dontAsk `
  --tools= `
  --strict-mcp-config `
  --safe-mode `
  --no-session-persistence `
  --max-budget-usd 0.05 `
  --run-depth 0 `
  --max-depth 1 `
  --timeout-seconds 90 `
  --max-output-bytes 1048576 `
  --origin-agent codex `
  --claude-bin "<native-claude.exe>" `
  --dry-run
```

PowerShell can drop an empty quoted native argument, so this runbook uses `--tools=`; the launcher still emits the target argument pair `--tools`, `""`. The dry-run passes only if the command contains `--safe-mode`, `--disable-slash-commands`, an empty `--setting-sources`, `--no-chrome`, `--strict-mcp-config`, an empty tool policy, `--no-session-persistence`, and the stated budget/runtime/output bounds.

## Execute And Judge

Repeat the same command with a second unique receipt directory and replace `--dry-run` with `--execute`. Then snapshot again:

```powershell
python skills\cairnspan\scripts\workspace_manifest.py snapshot `
  --root ".cairnspan\live\workspace" `
  --output ".cairnspan\live\manifests\after.json"

python skills\cairnspan\scripts\workspace_manifest.py compare `
  ".cairnspan\live\manifests\before.json" `
  ".cairnspan\live\manifests\after.json"
```

Pass only if all conditions hold:

- launcher exit code is 0, `status` is `succeeded`, and `error_kind` is null;
- a session id and terminal Claude `result` event are present;
- `final.md` is exactly `claude-strict-noedit-ok`;
- the init/system events expose no configured MCP server or MCP tool names;
- the init/system events expose no plugins, skills, or slash commands (built-in agent labels may still be reported as metadata);
- no tool-use or MCP-use event occurred;
- `safe_mode` and `strict_mcp_config` are true and `tools` is empty in the summary;
- `tool_use_count` and `mcp_tool_use_count` are zero in current receipts;
- the before/after manifest comparison reports `identical`;
- `scrubbed_env` records only variable names, never values;
- raw receipts remain under ignored `.cairnspan/` storage.

Any missing terminal event, malformed JSONL line, timeout, output-limit stop, tool/MCP exposure, or manifest difference is a failed probe. Stop before the full loop and update `docs/verification.md` and `docs/learnings.md` with the exact evidence.

## Full-Loop Hold

Do not turn this standalone edge command into a nested loop. The verified route is parent-orchestrated by `run_two_way_route.py`, which owns aggregate budgets, the nonce contract, summary verification, and protected receipts.
