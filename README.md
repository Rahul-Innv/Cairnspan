# Cairnspan

Cairnspan is a local coordination layer for multi-agent, OAuth-backed delegation between coding agents such as Claude Code, Codex, Cursor, Gemini, and future local AI clients.

It is meant to let different agents use their individual strengths and capabilities through the user's already-authenticated local clients. It is designed not to broker OAuth tokens, wrap raw model APIs as the primary path, or pretend that different agents share tools, context, approvals, auth, or runtime state.

## Status

Private alpha preparing for `0.1.0-alpha.1`. The core two-agent paths now have repeated live evidence, sanitized fixtures, and a copied-skill install proof. Keep the repository private until the public-alpha gate in `docs/release-readiness.md` passes against one clean tagged commit.

**Cairnspan** is the owner-selected working public name and the current source
identity. Display text, skill paths, runtime defaults, schemas, tests, receipt
names, protocol markers, and environment prefixes use `Cairnspan`,
`cairnspan`, `.cairnspan`, and `CAIRNSPAN_*`. The private-alpha migration is a
clean break: historical pre-Cairnspan runtime receipts stay untouched and
ignored, and no legacy runtime alias is accepted.

Current state:

- Implemented: hardened Codex and Claude Code launchers with structured receipts, fail-closed protocol parsing, receipt-path isolation for write-capable runs, fail-closed Windows Job Object containment, bounded output/runtime, and deny-by-default unattended profiles.
- Verified: Claude Code to Codex probes for basic text, read-only, workspace-write, MCP visibility, and built-in image generation.
- Verified: Codex to Claude Code basic and strict-MCP/no-tools/no-edit probes.
- Verified: the parent-orchestrated Codex-to-Claude text route closed live on 2026-07-10 in 27.375 seconds with two exact nonce artifacts, two terminal receipts, zero tool/MCP calls, unchanged strict workspace manifests, no surviving descendants, linked receipt hashes, and `$0.019557` reported Claude cost. Codex cost was not reported by its CLI and is recorded as unknown, not zero.
- Verified: a fresh hardened repetition closed in 15.86 seconds for `$0.019726` reported Claude cost; a network-denied attempt failed before Claude launch and left both workspaces unchanged.
- Verified: the shared-folder Codex-to-Claude-to-Codex mailbox route closed on synthetic public data with exact request/response linkage, one terminal response, scoped writes, read-only consumption, and parent-owned manifests.
- Verified: the typed Claude-design-to-Codex-image route produced one 512x512 static PNG and closed with no product integration. A hardened live repetition also closed after owner visual approval, with bounded decompression, strict core/display-chunk policy, APNG denial, exact design-spec-to-generation-prompt binding, `job-object` containment, and exact manifests.
- Compatibility warning: that image-generation evidence predates the current
  `codex-cli 0.144.0-alpha.4` image-tool report. A Fable run reported native
  image attachments still working while `$imagegen` said its code-mode host was
  missing and `view_image` failed to start. Offline feature inspection shows
  both flags enabled but cannot prove runtime startup. Current image-tool probes
  must use `--require-image-capability` and close only on observed tool events.
- Verified: live hostile-workspace probes against both native clients ignored synthetic poisoned project instructions under strict isolation. Both returned exact markers with zero tools/MCP/web use, unchanged strict manifests, no canary disclosure or outside write, one terminal identity, and verified Job Object cleanup.
- Deterministic only: both launchers now expose a typed
  `hostile-workspace-write` profile with canonical nonce prompts, fixed result
  paths, native version pins, protected sibling sentinels, parent-controlled
  receipts, narrow write-tool allowlists, and strict before/after manifests.
  Six fake-target cases pass; no write-enabled native-client matrix case has
  been authorized or live-run.
- Deterministic only: `hostile_write_case.py` prepares an immutable single-case
  plan with separate dry-run/live receipt roots, closes both command-specific
  summaries plus exact success or authoritative denial evidence, and performs
  guarded parent-owned cleanup of only the disposable workspace. The closer
  independently recomputes workspace deltas, exact output bytes, sentinel
  state, and case-specific denial evidence instead of trusting the target
  summary alone. Seventeen parent-case tests pass; the helper never launches a
  provider itself.
- Verified: the repo-scoped copied-skill path validates, compiles, passes `doctor.py` with explicit native clients, and dry-runs both launchers from the clean copy.
- Caveat: default `codex` still resolves to a WindowsApps package path that PowerShell/Python cannot start unattended. Pass an explicit local Codex CLI path with `--codex-bin`.
- Not yet verified: a broader repeated/crash/quota/rate-limit matrix against native clients, live canary egress probes, packaging/signing, or a third adapter.
- Planned: finish the remaining Phase 1 pressure gates, then add an adapter contract and policy engine before choosing the first third adapter, with Cursor and Gemini as current candidates.

Do not describe Cairnspan as production-ready. The bounded two-agent text route is verified; broader artifact workflows and enterprise controls are not.

Do not describe Cairnspan as enterprise-ready or three-agent capable until the adapter contract, routing policy, data-classification gates, provider-boundary receipts, and multi-target pressure tests in `docs/verification.md` are complete.

## Platform support

The session tooling is developed and validated on Windows. Linux CI runs the
platform-neutral subset; suites that depend on Windows-only file-metadata
semantics or Job Object containment are skipped off Windows.

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

## Quick Start

Cairnspan is not packaged yet. Use it from a checkout by running the launcher script directly.

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

Use `--codex-bin "C:\absolute\path\to\codex.exe"` when the PATH entry is not safe or launchable.

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

Inspect the dry-run route plan before replacing `--dry-run` with `--execute`.

Run the non-destructive setup checker when diagnosing a local install:

```powershell
python skills\cairnspan\scripts\doctor.py --cwd "C:\path\to\target" --format json
```

Pass the explicit native Codex path when PATH resolves to WindowsApps. The
doctor reports bounded version, typed model, typed effort, and
`codex_image_tools` checks separately for the selected clients. It reports
`unknown(runtime_unverified)` rather than claiming support from a filename or
feature flag alone.

Both launchers accept the optional typed effort values `low`, `medium`, `high`,
`xhigh`, and `max`. Claude receives exactly one native `--effort` pair. Codex
receives one launcher-owned `model_reasoning_effort` config value; callers
cannot supply the key or a raw config expression. A receipt records the
requested model and effort but does not prove the provider honored either.

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

## Project Docs

- `docs/origin-context.md`: why this project exists
- `docs/name-check.md`: current name-collision evidence and naming caveat
- `docs/plan.md`: architecture and milestones
- `docs/positioning.md`: vision-organized positioning, landscape comparison, and framing options
- `docs/positioning-stress-test.md`: 2026-07-11 adversarially verified online stress test of the positioning, including the provider-ToS risk finding
- `docs/ecosystem-map.md`: 2026-07-11 consultant-grade end-to-end map of the agentic ecosystem (value chain, control points, scenarios, Cairnspan fit)
- `docs/strengthening-plan.md`: installation, safety, packaging, positioning, and expansion plan
- `docs/release-readiness.md`: source, public-alpha, and production claim gates
- `docs/cursor-perplexity-cross-analysis.md`: dated comparison against Cursor and Perplexity
- `docs/install-skill.md`: repo-scoped install and first-probe path
- `docs/safety-checklist.md`: pre-live and pre-public checklist
- `docs/live-test-runbook.md`: reproducible strict-MCP/no-edit live probe
- `docs/hostile-write-matrix.md`: typed write-enabled case lifecycle and owner-gated live boundary
- `docs/synthetic-probe-proposals.md`: immutable offline proposal contract for Codex typed effort, image generation, and image viewing
- `docs/synthetic-image-pilot.md`: finite three-item image pilot, aggregate ceilings, daily ledger, and fail-stop controller
- `docs/two-way-loop.md`: bounded parent-orchestrated full-loop contract
- `docs/artifact-route.md`: separate typed website/image and critique workflow contract
- `docs/token-audit.md`: scoped credential non-persistence audit
- `docs/claude-launcher.md`: verified Claude Code entrypoint and reverse launcher spec
- `docs/mailbox.md`: file-based fallback request/response contract
- `docs/verification.md`: proof matrix
- `docs/learnings.md`: durable lessons from implementation and testing
- `skills/cairnspan/SKILL.md`: canonical skill

## License

MIT. See `LICENSE`.
