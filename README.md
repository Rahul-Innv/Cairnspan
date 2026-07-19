<p align="center">
  <img src="docs/assets/logo.png" alt="Cairnspan logo" width="180">
</p>

# Cairnspan

[![pipeline status](https://gitlab.com/krahul02004/Cairnspan/badges/main/pipeline.svg)](https://gitlab.com/krahul02004/Cairnspan/-/commits/main)
[![PyPI version](https://img.shields.io/pypi/v/cairnspan)](https://pypi.org/project/cairnspan/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Cairnspan is a local coordination layer for multi-agent, OAuth-backed delegation between coding agents such as Claude Code, Codex, Cursor, Gemini, and future local AI clients.

It is meant to let different agents use their individual strengths through the user's already-authenticated local clients. It is designed not to broker OAuth tokens, wrap raw model APIs as the primary path, or pretend that different agents share tools, context, approvals, auth, or runtime state.

## Getting started

- **Prerequisites:** Python 3.11 or newer. Cairnspan is developed and validated on Windows (Linux CI runs the platform-neutral subset).
- **Install:** `pip install cairnspan` for the `cairnspan` console dispatcher, or install from a clone (`git clone https://gitlab.com/krahul02004/Cairnspan.git`, `cd Cairnspan`, `pip install .`) to run the launcher scripts directly. Fuller setup, including the dry-run-first workflow, is under [Quick Start](#quick-start).
- **Check it works:** run `cairnspan doctor`. It runs a local, offline health check and prints one line per check plus an overall status token (for example `cairnspan-doctor-warn` when a local Codex or Claude binary resolves to an npm shell wrapper).

## 30-second demo

Every run (including a dry run) produces a machine-readable receipt before any provider is touched:

```powershell
git clone https://gitlab.com/krahul02004/Cairnspan.git
cd Cairnspan
pip install .

cairnspan launch-codex `
  --cwd "C:\path\to\demo-target" `
  --prompt-file "C:\path\to\demo-request.txt" `
  --sandbox read-only `
  --codex-bin "C:\path\to\codex\codex.exe" `
  --dry-run
```

Real output, trimmed (machine-specific paths replaced with placeholders):

```json
{
  "status": "dry_run",
  "command": [
    "C:\\path\\to\\codex\\codex.exe",
    "exec", "--json", "--sandbox", "read-only",
    "<prompt redacted>"
  ],
  "target_cli_version": "codex-cli 0.144.5",
  "sandbox": "read-only",
  "prompt_sha256": "e5631efcf2cd9cc58d18554fed92a44444e7eaff115613373cac0452e9ae53ba",
  "scrubbed_env": ["ANTHROPIC_BASE_URL"],
  "run_id": "20260718T135356Z-db75d6c9",
  "summary_file": "C:\\path\\to\\demo-target\\.cairnspan\\20260718T135356Z-db75d6c9\\cairnspan-summary.json"
}
```

The prompt is hashed and redacted, known provider environment overrides are scrubbed from the child, and the exact command that would run is recorded. Replace `--dry-run` with `--execute` to launch the real session under the same contract.

## Why It Exists

The long-term goal is governed multi-agent interaction: route each bounded task
to the model or client best suited for it, then bring the result back with proof.

Some agent capabilities live in local authenticated clients rather than raw APIs:

- Codex account/session behavior
- Codex skills such as `$imagegen`
- Codex MCP/plugin configuration
- Claude Code project context and extension workflows
- local approval and sandbox policy
- Cursor workspace/agent UX and skill/MCP ecosystem
- future model-specific strengths such as Gemini long-context or research-heavy flows

Cairnspan makes those handoffs explicit and auditable. A run should answer who asked, which agent ran, what command was used, what permissions were granted, what logs prove the outcome, and what should happen next.

The core path has no Cairnspan server, daemon, database, or hosted backend. It launches a target client, captures receipts, verifies cleanup, and exits. It still consumes provider-specific subscription or API limits, provider network access, local CPU/RAM/disk, and any model-reported cost. As of 2026-07-12, Anthropic documents a separate monthly Agent SDK credit for subscription-backed Agent SDK and `claude -p` usage, effective June 15, 2026. Provider limits and billing can change; recheck the current provider documentation before live or release planning.

## What's Verified

Cairnspan is a source-public alpha preparing for `0.1.0-alpha.1`, hosted at
[gitlab.com/krahul02004/Cairnspan](https://gitlab.com/krahul02004/Cairnspan). The core
two-agent paths have repeated live evidence, sanitized fixtures, and a copied-skill install
proof behind them; the public-alpha gate in `docs/release-readiness.md` must still pass
against one clean tagged commit before any tagged release claim.

| Route / capability | Evidence | Date |
| --- | --- | --- |
| Codex → Claude parent-orchestrated text route | Closed live in 27.375 s with two exact nonce artifacts, linked receipt hashes, zero tool/MCP calls, and `$0.019557` reported Claude cost; a hardened repeat closed in 15.86 s | 2026-07-10 |
| Codex → Claude strict-MCP / no-tools / no-edit probe | Succeeded in 11.484 s for `$0.01832` with exact final text, empty tools/MCP/plugins, and identical external workspace manifests | 2026-07-10 |
| Claude Code → Codex probe family (basic text, read-only, workspace-write scope, MCP visibility, image generation) | A deliberate write under `read-only` was denied with identical before/after manifests; the built-in `$imagegen` path produced a valid-signature PNG | by 2026-07-17 |
| Hostile-workspace probes against both native clients | Synthetic poisoned project instructions were ignored: exact markers, zero tools/MCP/web use, unchanged strict manifests, no planted canary secret disclosed, verified Job Object cleanup | by 2026-07-17 |
| Typed Claude-design → Codex-image artifact route | One 512x512 static PNG accepted after owner visual approval, with bounded decompression, APNG denial, and exact manifests | by 2026-07-17 |

The full bullet-by-bullet ledger (including the shared-folder mailbox route, the
copied-skill install proof, the deterministic-only hostile-write profiles, known caveats,
and the open gates) is preserved in [`docs/verification.md`](docs/verification.md).

Do not describe Cairnspan as production-ready. Do not describe Cairnspan as enterprise-ready or three-agent capable until the adapter contract, routing policy, data-classification gates, provider-boundary receipts, and multi-target pressure tests in `docs/verification.md` are complete; the bounded two-agent routes above are what is verified today.

## Safety Model

- Cairnspan is designed not to copy, store, or expose OAuth tokens.
- It launches local authenticated clients and records observable run metadata.
- The Claude adapter launches Anthropic's unmodified official `claude -p` client. It must not extract or replay Claude credentials, offer Claude.ai login, or route subscription credentials on behalf of another user.
- Anthropic documents `claude -p` for scripts and CI and documents subscription OAuth for its CLI, but recommends API-key or managed-provider authentication for products, services, and shared production automation. Treat provider-policy review as a release gate, not as a claim that Anthropic has approved Cairnspan.
- Prompt bodies are hashed and redacted from summaries by default.
- Zero-exit target processes are not accepted as success without a recognized terminal event and thread/session id; malformed JSONL fails closed.
- Route closure requires exact artifact matches plus linked prompt, final, summary, route-plan, executable, and manifest evidence; a successful model response alone is insufficient.
- Known raw API-key and alternate-provider environment overrides are removed from child processes by default.
- Strict Codex route edges ignore user config/rules, disable apps/plugins/MCP-adjacent and tool features, run ephemerally, and fail on any observed tool use.
- Claude Code customizations are disabled by default with `--safe-mode`, empty setting sources, disabled slash commands, and Chrome integration off; configured MCP and built-in tools remain deny-by-default.
- PATH-selected shell wrappers are rejected unless explicitly acknowledged; prefer pinned native executable paths.
- Every launcher run probes and records the target CLI version. Parent routes freeze the observed version for each edge and fail before target launch if the executable reports a different version; Cairnspan never silently updates provider CLIs.
- Raw logs can still contain sensitive output from the target agent.
- `danger-full-access` requires explicit unsafe opt-in and a reason.
- Raw target-agent argument passthrough requires explicit unsafe opt-in and a reason.
- A target workspace must already exist; Cairnspan will not create it from a typoed `--cwd`.
- Write-capable runs require a fresh receipt directory outside the writable target workspace. Receipt temp files are randomized and identity-checked before publication.
- On Windows, inability to attach the suspended target to a kill-on-close Job Object prevents target execution. Successful summaries record the containment mode, and route closures require it.
- POSIX launchers currently record process-group cleanup, but authoritative route/artifact closure rejects it because a hostile child can create a new session and escape. Stronger POSIX containment and live tests remain release gates.

The deny-by-default posture is visible in the receipts themselves. The reverse edge's dry run records the exact hardened Claude command before anything launches. Real output, trimmed:

```json
{
  "status": "dry_run",
  "target_cli_version": "2.1.201 (Claude Code)",
  "command": [
    "C:\\path\\to\\claude.exe", "-p", "--output-format", "stream-json",
    "--permission-mode", "dontAsk", "--tools", "", "--verbose",
    "--no-session-persistence", "--max-budget-usd", "0.25",
    "--safe-mode", "--disable-slash-commands", "--setting-sources", "",
    "--no-chrome", "--strict-mcp-config", "<prompt redacted>"
  ]
}
```

## Quick Start

Install with `pip install cairnspan`, or from a clone (as in the demo above) to get
the `cairnspan` console dispatcher and run the launcher scripts directly from the checkout.
Each `cairnspan <tool>` subcommand runs the corresponding standalone script in a child
interpreter, so the scripts' documented command-line contracts, receipts, and fail-closed
behavior are unchanged.

The first public target is a pinned, Windows-only, owner-local two-agent source
alpha. Public source availability will not make POSIX closure authoritative,
authorize shared/hosted credential routing, or imply production readiness. See
`docs/release-readiness.md`.

Dry-run first:

```powershell
python skills\cairnspan\scripts\start_codex_session.py `
  --cwd "C:\path\to\target" `
  --prompt-file "C:\path\to\request.txt" `
  --model "<reviewed-model-id>" `
  --effort xhigh `
  --sandbox read-only `
  --dry-run
```

Live run, once `codex` is launchable from PowerShell/Python:

```powershell
python skills\cairnspan\scripts\start_codex_session.py `
  --cwd "C:\path\to\target" `
  --prompt-file "C:\path\to\request.txt" `
  --sandbox read-only `
  --execute
```

Use `--codex-bin "C:\absolute\path\to\codex.exe"` when the PATH entry is not safe or launchable. Two known first-run blockers, both fail-closed by design:

- An npm-installed `codex` or `claude` on PATH resolves to a PowerShell wrapper, and the launcher stops with `Shell-wrapper Codex executables require --allow-shell-wrapper.` (or its Claude equivalent). Pass the native executable with `--codex-bin`/`--claude-bin` instead of acknowledging the wrapper.
- A WindowsApps `codex` cannot be started unattended from PowerShell/Python at all; the same explicit `--codex-bin` path fixes it.

Bounded two-edge text route, after both native executables and disposable workspaces are ready:

```powershell
python skills\cairnspan\scripts\run_two_way_route.py `
  --codex-cwd "C:\path\to\disposable-codex-workspace" `
  --claude-cwd "C:\path\to\disposable-claude-workspace" `
  --out-dir "C:\path\to\private-receipts\fresh-run" `
  --codex-bin "C:\absolute\path\to\codex.exe" `
  --claude-bin "C:\absolute\path\to\claude.exe" `
  --dry-run
```

The dry run writes an immutable `route-plan.json` and a `route-summary.json` that pin both executables and prove both disposable workspaces untouched. Real output, trimmed:

```json
{
  "state": "dry_run",
  "successful_edges": 2,
  "executables": {
    "claude": { "version": "2.1.201 (Claude Code)", "sha256": "fb804ee019bf..." },
    "codex": { "version": "codex-cli 0.144.5", "sha256": "efdb3540ef74..." }
  },
  "manifests": {
    "claude": { "status": "identical", "difference_count": 0 },
    "codex": { "status": "identical", "difference_count": 0 }
  }
}
```

Inspect the dry-run route plan before replacing `--dry-run` with `--execute`.

Run the non-destructive setup checker when diagnosing a local install:

```powershell
python skills\cairnspan\scripts\doctor.py --cwd "C:\path\to\target" --format json
```

The doctor reports bounded version, typed model, typed effort, and `codex_image_tools`
checks separately for the selected clients, and reports `unknown(runtime_unverified)`
rather than claiming support from a filename or feature flag alone.

Both launchers accept the optional typed effort values `low`, `medium`, `high`, `xhigh`,
and `max`. A receipt records the requested model and effort but does not prove the
provider honored either.

For routine local iteration, run the deterministic tier; retain the complete
gate before handoff or release review:

```powershell
python tests\run_tests.py fast
python tests\run_tests.py full
```

## Outputs

Each run writes:

- `cairnspan-summary.json`: redacted command, run id, status, return code,
  failure class, requested model/effort, target version evidence, thread id when
  available, usage when available, and artifact paths.
- `events.jsonl`: Codex `--json` event stream.
- `transcript.log`: Codex stderr/progress output.
- `final.md`: best-effort final agent message.

The bounded route additionally writes an immutable `route-plan.json`, a final `route-summary.json`, per-edge receipt directories, strict before/after workspace manifests, and `closure.json` only after both exact artifacts and all route policy checks pass.

Runtime artifacts may contain prompts, paths, model output, and tool output. Keep them private unless explicitly redacted.

## Platform Support

The session tooling is developed and validated on Windows. Linux CI runs the
platform-neutral subset; suites that depend on Windows-only file-metadata
semantics or Job Object containment are skipped off Windows.

## Project Docs

- `docs/install-skill.md`: repo-scoped install and first-probe path
- `docs/live-test-runbook.md`: reproducible strict-MCP/no-edit live probe
- `docs/safety-checklist.md`: pre-live and pre-public checklist
- `docs/threat-model.md`: confidentiality boundaries, prompt injection, and containment analysis
- `docs/release-readiness.md`: source, public-alpha, and production claim gates
- `docs/verification.md`: proof matrix and the full status ledger
- `skills/cairnspan/SKILL.md`: canonical skill

The remaining design, positioning, and research notes live alongside these in [`docs/`](docs/).

## License

MIT. See `LICENSE`.
