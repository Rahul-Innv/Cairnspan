# Install Cairnspan From A Checkout

Cairnspan is not packaged yet. Use this repo-scoped path first, while the
project remains private.

The planned `0.1.0-alpha.1` public target is a pinned Windows-only source
release. Before treating any checkout as that release, verify the exact tag and
run the source/public-alpha gates in `docs/release-readiness.md`.

## Prerequisites

- Python 3.10 or newer.
- Codex installed and authenticated locally if you want Claude Code -> Codex.
- Claude Code installed and authenticated locally if you want Codex -> Claude
  Code.
- A target workspace that already exists and is safe for the target agent to
  read.

Cairnspan does not ask for OAuth tokens or API keys for the core path.

## Setup Check

From the repository root:

```powershell
python skills\cairnspan\scripts\doctor.py --cwd "C:\path\to\target" --format json
```

Expected outcomes:

- `ok`: the non-destructive checks passed.
- `warn`: review the warning before running live probes. A common Windows
  warning is `codex` resolving to a WindowsApps path that may fail unattended,
  or Claude resolving through a shell wrapper instead of a native executable.
- `fail`: fix the missing workspace, missing executable, or unsafe output path
  before running probes.

If Codex resolves to WindowsApps, pass a launchable binary explicitly:

```powershell
python skills\cairnspan\scripts\start_codex_session.py `
  --codex-bin "C:\path\to\launchable\codex.exe" `
  --cwd "C:\path\to\target" `
  --prompt-file "C:\path\to\request.txt" `
  --sandbox read-only `
  --dry-run
```

## Dry Run

Dry-run first:

```powershell
python skills\cairnspan\scripts\start_codex_session.py `
  --cwd "C:\path\to\target" `
  --prompt-file "C:\path\to\request.txt" `
  --sandbox read-only `
  --dry-run
```

Inspect `cairnspan-summary.json` or stdout. The prompt body should be redacted and
only a prompt hash should appear.

## First Live Probe

Use a text-only read-only probe before any write-capable run:

```powershell
python skills\cairnspan\scripts\start_codex_session.py `
  --cwd "C:\path\to\target" `
  --prompt-file docs\probes\basic-codex.txt `
  --sandbox read-only `
  --execute
```

Then inspect:

- `cairnspan-summary.json`
- `events.jsonl`
- `transcript.log`
- `final.md`

Do not treat a live probe as successful unless the summary status, return code,
thread/session id, and final output match the expected probe.

For the next reverse probe, follow `docs/live-test-runbook.md`; it combines safe mode, strict MCP isolation, no tools, protected receipts, a small Claude budget, and origin-side manifest comparison.

## Safety Defaults

- Prefer `read-only` for probes.
- Use `workspace-write` only for intentional edits.
- Avoid `danger-full-access`.
- Keep raw target-agent args disabled unless there is a specific unsafe reason.
- For no-edit probes, keep output under ignored runtime storage. For write-enabled targets, authoritative receipts should be parent-controlled and outside the target `--cwd`.
- Use explicit native target executables. Shell wrappers require acknowledgement and should not be used for authoritative evidence.
- Keep `--max-depth`, `--timeout-seconds`, and `--max-output-bytes` bounded.

## Before Publishing Evidence

Scan proposed evidence or fixtures:

```powershell
python skills\cairnspan\scripts\scan_artifacts.py docs --format json
```

A clean scan is not enough by itself. Human review is still required for private
model output, repository names, and project-specific context.

## Copied-Skill Verification

The documented path was exercised on 2026-07-10 from a fresh copied skill
folder under ignored runtime storage. Both the canonical and copied skill passed
`quick_validate.py`; copied scripts compiled; `doctor.py` passed with explicit
native Codex and Claude executables; and both launchers produced valid dry-run
receipts from the copy. This proves the copy is self-contained on the current
machine, not that every user's PATH, authentication, or operating system is
already configured.

## Uninstall Or Disable

For the repo-scoped path, there is no global install. To disable Cairnspan:

- stop using the launcher scripts,
- remove copied skill folders from any other project,
- delete local `.cairnspan/` runtime artifacts if they are no longer needed,
- remove any plugin package later if Cairnspan is packaged as a plugin.
