# Cairnspan Strengthening Plan

This plan turns the product, safety, installation, and competitive research into
build work. It is additive to `docs/plan.md`: the existing plan tracks the core
two-way launcher; this document tracks the surrounding product strength needed
before Cairnspan is easy, defensible, and safe to share.

## Core Position

Primary one-liner:

> Let the right AI agent handle the right subtask, without sharing keys or
> running another server.

Technical version:

> Cairnspan is a zero-runtime multi-agent capability router: it launches the
> real locally logged-in agent best suited to a bounded subtask, scopes the run,
> captures the receipt, and exits.

The north star is multi-agent interaction across different models and clients.
Claude Code and Codex are Phase 1 because they prove the control, safety, and
receipt contract. The product direction is broader: use each agent's individual
strengths, account-scoped capabilities, model behavior, tools, skills, MCP
setup, context window, cost profile, and workspace affordances without merging
their credentials or pretending they share one runtime.

Do not position Cairnspan as an easier clone of Hermes, OpenClaw, MCP, A2A,
Cursor, Perplexity, or a general agent runtime. The stronger category is
narrower:

- local-first cross-agent handoffs
- capability-aware routing across different models and clients
- no token broker
- no always-on daemon
- no extra hosted backend
- structured receipts for agent work
- account-backed capabilities from tools the user already has installed

The Cursor/Perplexity cross-analysis lives in
`docs/cursor-perplexity-cross-analysis.md`. Current conclusion: Cursor is both
the closest adjacent competitor and the strongest next adapter candidate;
Perplexity is primarily an optional research/search/API tool layer unless it
exposes a safe local authenticated client interface.

## Product Claim Ladder

Only make public claims when the corresponding proof gate is complete.

| Claim | Public wording | Required proof gate |
| --- | --- | --- |
| Local authenticated clients | "Uses your already logged-in local agents." | Live Codex and Claude Code probes pass without API-key fallback. |
| No token broker | "Cairnspan never copies or stores OAuth tokens." | Static audit plus runtime artifact review shows no token/keychain/cookie capture. |
| Zero persistent runtime | "No server or daemon to run for the core handoff." | Architecture docs and installer docs show launch-and-exit behavior; process observation during probes confirms no persistent Cairnspan service. |
| Official-client owner-local path | "Cairnspan launches your installed official client without handling its credentials." | Codex and Claude probes run through native clients; docs state provider-specific limits still apply and keep public/shared use behind provider-policy review. |
| Permission-scoped handoffs | "Read-only and workspace-write are verified, not just prompted." | Before/after manifests for read-only and workspace-write probes remain in `docs/verification.md`. |
| Two-way delegation | "Claude Code and Codex can hand work to each other." | A full two-way loop passes, not just two independent one-way probes. |
| Website/image routing | "Claude can design and Codex can generate a validated image handoff." | The typed artifact route in `docs/artifact-route.md` passes with isolated staging, byte-level validation, human integration approval, and no API-key fallback. |
| Portable beyond Claude/Codex | "The adapter contract can support more local agents." | At least one third adapter feasibility spike, currently Cursor or Gemini, proves the contract is not pair-specific. |

## Installation Paths To Build

### Path 1: Repo-Scoped Skill

This should be the first usable public path.

User flow:

1. Clone or download the repository from GitHub/GitLab.
2. Inspect `SKILL.md`, `SECURITY.md`, and launcher scripts.
3. Use the skill from the checkout or copy it into the repo-scoped skills
   directory for the target project.
4. Run `--dry-run`.
5. Run a read-only probe.
6. Run workspace-write only for real edit tasks.

Target setup time:

- 5-15 minutes if Claude Code/Codex are already installed and authenticated.
- 30-60 minutes if the user still needs to install or authenticate target
  agents.
- Windows path issues must be diagnosed by docs or a checker, not by trial and
  error.

Required work:

- Keep `docs/install-skill.md` current as launcher flags change.
- Keep `doctor.py` current as setup blockers are discovered.
- Document the WindowsApps Codex path issue and explicit `--codex-bin` fix.
- Provide a one-command dry-run example and one read-only live probe example.

### Path 2: Plugin Package

This is the better distribution path after the repo-scoped path is stable.

User flow:

1. Install Cairnspan as a Codex plugin or equivalent distribution package.
2. Start a new thread/session so the skill is discovered.
3. Run the same dry-run and read-only probes.

Target setup time:

- 2-5 minutes when target agents are already installed and authenticated.
- Longer only when target app auth or CLI installation is missing.

Required work:

- Package the skill, scripts, and metadata as a plugin.
- Keep the launcher scripts stdlib-only or vendor dependencies deliberately.
- Add plugin uninstall/disable instructions.
- Keep approvals and sandbox behavior explicit; plugin install must not imply
  broad runtime permission.

### Path 3: Guided Installer

This is the path that makes the product feel easy instead of merely possible.

User flow:

1. Run one setup/check command.
2. It checks Python, Codex, Claude Code, auth status, executable paths,
   workspace validity, sandbox support, and output directories.
3. It writes local config only after showing what it found.
4. It runs dry-run and optional read-only probes.

Target setup time:

- 1-3 minutes in the ideal case.
- Under 10 minutes for common path/auth issues.

Required work:

- Implement a non-destructive environment checker.
- Print exact next actions for missing auth, missing CLI, unsafe PATH, or
  network-blocked live probes.
- Never ask the user to paste tokens.

## Safety Workstream

Safety has to be part of install and runtime, not a separate disclaimer.

The canonical threat model lives in `docs/threat-model.md`. Treat it as a
release gate document, not background reading.

### Download Safety

- Prefer signed releases or pinned commit SHAs for public instructions.
- Tell users not to install from random branch HEAD unless they trust the repo.
- Keep `SKILL.md`, launcher scripts, and dependency files small enough to audit.
- Keep dependencies minimal; every dependency adds supply-chain review.

### Runtime Safety

- Default probes to read-only.
- Document clearly that read-only is a write boundary, not a confidentiality
  boundary. A target agent can still read workspace files and may send relevant
  context to its model provider or configured tools.
- Require explicit opt-in and reason for `danger-full-access`, raw target-agent
  args, broad Claude tools, or permission bypass modes.
- Require an existing target workspace; never create a missing `--cwd`.
- Resolve target executables before changing directories.
- Keep output under `.cairnspan/` or caller-chosen run directories.
- Refuse existing non-empty output directories unless an explicit overwrite
  flag is added.
- Require explicit opt-in for output directories outside the resolved target
  workspace.
- Add recursion guards before promoting two-way loops: max depth, max runtime,
  max output bytes, and no broader target permissions than the origin run
  without explicit approval.
- Make uninstall/disable instructions obvious.

### Credential Safety

- Never copy, print, store, scrape, or broker OAuth tokens.
- Never require `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for the core OAuth-backed
  path.
- Treat API-key or `--bare` modes as explicit fallback modes, not the product
  identity.
- Add an artifact scan that checks summaries, transcripts, and events for
  common token/key patterns before public examples are committed.
- Include canary secrets in scanner tests so the scanner is proven, not just
  assumed.

### Artifact Safety

- Raw run directories are private by default.
- Public fixtures must redact local paths, prompt text, account identifiers,
  private repository names, private model output, and any tool output that quotes
  private files.
- Redacted fixtures should still prove the important behavior: command shape,
  sandbox, status, thread/session id shape, final result, and failure class.
- Run `skills/cairnspan/scripts/scan_artifacts.py` on any proposed public
  fixture. A clean scan is necessary but not sufficient; the fixture still needs
  human review for private model output and project-specific context.

### Prompt-Injection Safety

- Treat target workspaces as potentially instruction-bearing. `AGENTS.md`,
  `CLAUDE.md`, `.codex`, MCP config, hooks, local skills, and repository docs
  can alter target-agent behavior.
- Add malicious-workspace probes before broader sharing: poisoned instruction
  files, canary secrets, fake local executables, configured MCP exposure,
  attempted outside writes, and attempted secret disclosure.
- Receipts should record visible target-agent tools/MCP servers when possible,
  so unexpected tool exposure is discoverable.

### Raw-Argument Safety

- Prefer typed launcher options over raw passthrough.
- Raw target-agent args should require explicit unsafe opt-in and a reason.
- Add bypass tests for duplicate sandbox/permission flags, `--permission-mode`
  variants, broad Claude tools, `--bare`, alternate MCP config, and danger flags.

### Output-Path Safety

- Do not silently overwrite prior receipts.
- Add tests for reused output directories, parent traversal, `.git/hooks`,
  symlink targets, and Windows junction/reparse-point escapes.
- If outside-workspace output is supported, make it a conscious audited choice.

## Adapter Expansion Plan

Do not build pairwise bridges for every agent pair. Build one run contract and
one adapter per target agent.

Every adapter must answer:

- Can it launch noninteractively from a local installed client?
- Can it use the user's existing authenticated account without copying tokens?
- Can it accept a prompt file or otherwise avoid fragile shell quoting?
- Can it set or emulate a target workspace?
- Can it expose structured output or a parseable transcript?
- Can it report a session/thread id?
- Can it limit tools, permissions, cost, or sandbox behavior?
- Can it run no-edit probes safely?
- Can it produce artifacts that fit `cairnspan-summary.json`, `events.jsonl`,
  `transcript.log`, and `final.md`?

Current adapter priority:

1. **Codex**: keep hardening the existing `codex exec --json` path.
2. **Claude Code**: keep the verified strict-MCP and full text route reproducible while adding pressure coverage.
3. **Cursor feasibility**: evaluate as a serious host/target candidate because
   it supports Agent Skills, MCP, browser-login CLI auth, and noninteractive
   execution. Add only after a fake-Cursor target and no-edit live probe satisfy
   the adapter contract.
4. **Gemini CLI feasibility**: evaluate alongside or after Cursor; add only if
   it satisfies the adapter contract and policy gates.
5. **Perplexity integration research**: treat Perplexity as an optional
   research/search/API tool layer, not a native OAuth-backed adapter, unless it
   exposes a safe local authenticated client interface.
6. **Hermes/OpenClaw integration research**: treat these as runtimes/control
   planes to compare against or potentially launch, not as the first adapter
   targets.
7. **Future robots**: require the adapter contract before committing support.

## Three-Agent Orchestrator Plan

The user's capability roadmap is:

1. **Phase 1:** make Claude Code and Codex work two-way with strong receipts and
   safety gates.
2. **Phase 2:** add a third adapter, likely Gemini CLI, and introduce an
   orchestrator that can route bounded tasks to two or more target agents.

Phase 2 must not become an unconstrained group chat between models, and it must
not begin as "Claude/Codex plus Gemini." It should begin as a governed routing
layer, with Gemini admitted only after adapter and policy gates pass.

- A route plan is created before execution: origin, target chain, allowed
  agents, denied agents, allowed tools, workspace scope, data labels, max depth,
  max fan-out, max cost, and approval state.
- Each adapter declares capabilities, constraints, and caveats.
- Each request declares allowed targets, data classification, write scope,
  allowed tools/MCP, max cost, max runtime, max depth, expected artifacts, and
  whether cross-provider sharing is allowed.
- A central policy engine decides allowed adapters, sandbox level, raw args,
  tools/MCP, output path, provider, data class, budget, and whether approval is
  required.
- The orchestrator records why each target was selected or rejected.
- Unknown targets, unknown tools, unknown data classes, outside-workspace writes,
  and recursive delegation are denied by default.
- A lower-permission origin cannot escalate through a higher-permission target
  without explicit user approval.
- Agent output is untrusted input to the orchestrator unless backed by a valid
  receipt.

Additional Phase 2 tests:

- route-plan schema tests,
- routing-denial tests for disallowed providers and data classes,
- transitive-permission escalation tests,
- graph cycle tests for paths such as `Claude -> Codex -> Gemini -> Claude`,
- concurrent edit conflict tests,
- multi-target manifest comparison tests,
- per-provider artifact redaction tests,
- provider-specific rate-limit and quota tests,
- audit-graph export tests,
- adapter capability drift tests,
- and a three-agent loop-stop test.

Do not claim enterprise-ready orchestration until these tests exist.

## Enterprise Safety Controls

Enterprise-grade use requires explicit governance layers beyond the current MVP:

- **Policy as data:** store policy version, adapter versions, allowed targets,
  allowed tools, data classifications, and approval requirements in a structured
  config.
- **Data classification:** every request should declare whether it contains
  public, internal, confidential, secret, regulated, or customer data.
- **Provider boundaries:** every target adapter is a vendor/data-egress boundary.
  Receipts should show which provider saw what class of data.
- **Prompt minimization:** send the least context needed to the selected target,
  especially across provider boundaries.
- **Approval gates:** write-capable, cross-provider, multi-target, recursive,
  configured-MCP, broad-tool, outside-workspace, and raw-arg runs require
  explicit approval.
- **Audit receipts:** include policy version, command hash, prompt hash, artifact
  hashes, target versions, visible tools/MCP, changed-file manifests, and
  denial reasons.
- **Retention:** define how long raw logs live, where redacted receipts live, and
  how to purge local run artifacts.
- **Tamper evidence:** add receipt digests and optional receipt chaining before
  enterprise positioning.
- **Least privilege:** no target gets broader workspace, tools, MCP, network, or
  write access than the request policy allows.
- **Operational controls:** quotas, timeouts, max output bytes, max run depth,
  concurrency limits, and disk usage caps.
- **Enterprise deployment:** signed releases, pinned versions, SBOM, allowlisted
  binaries, proxy/egress support, SIEM-compatible audit export, centrally
  managed policy, and a kill switch.
- **Incident handling:** document how to disable adapters, revoke copied skills
  or plugins, quarantine artifacts, and report suspected leaks.

## Competitive Claim Workstream

Keep competitor claims in a research file until verified against current docs.
The positioning should survive even if a competitor improves installation.

Claims to validate before public copy:

- Does Hermes require a long-running service, server, daemon, or local runtime
  for the comparable workflow?
- Does OpenClaw require a gateway/server/runtime or provider setup for the
  comparable workflow?
- What RAM/process overhead exists for each comparable path?
- Can either reuse existing Claude/Codex/Gemini app subscriptions without raw
  API keys?
- Do they provide equivalent receipts: scoped command, permissions, artifacts,
  logs, final result, and failure classification?

The durable contrast should be:

> Agent runtimes help you run agents. Cairnspan helps your existing local
> AI apps ask each other for bounded help with receipts.

## UX And Demo Plan

The first demo should be concrete, not abstract interoperability.

Primary demo:

1. Claude Code receives a request requiring Codex-only image generation.
2. Claude Code writes a prompt file.
3. Cairnspan launches Codex with workspace-write only for a scratch output
   directory.
4. Codex uses its built-in image generation capability.
5. Cairnspan captures the result and receipt.
6. Claude Code reports the image path and evidence.

Secondary demos:

- read-only no-edit proof
- workspace-write boundary proof
- Codex MCP visibility proof
- Codex to Claude Code no-tools proof
- full two-way handoff proof

## Maintenance And Cost Model

The cost advantage is operational, not magical.

What should stay cheap:

- no hosted Cairnspan backend
- no always-on Cairnspan daemon
- no database for the core local handoff
- stdlib-only launchers where practical
- fake-agent tests for most CI coverage

What still costs time or quota:

- live probes consume provider-specific subscription or API quota; Anthropic documents a separate monthly Agent SDK credit for subscription-backed `claude -p` usage as of 2026-07-12, but the amount and billing behavior remain provider-controlled
- image generation can take longer and consume included limits
- CLI flags and output schemas can drift
- OS-specific path/auth behavior needs regression coverage
- each new adapter needs its own fake target, live smoke test, and docs

Maintenance rule:

> Add one adapter at a time behind the same run contract. Do not create N x N
> bridge logic between every origin and target pair.

## Build Sequence

### Phase 0: Finish The Verified Core

- [x] Keep the passing Claude strict-MCP/no-tools/no-edit probe reproducible with `docs/live-test-runbook.md` as the launcher evolves.
- [x] Add the aggregate route budget and bounded parent harness in `docs/two-way-loop.md`.
- [x] Add fake-target route failure and closure-receipt tests.
- [x] Run the first complete parent-orchestrated two-way text handoff loop.
- [x] Run strict no-tool hostile-workspace probes against both pinned native
  clients with synthetic canaries and parent-controlled receipts.
- [x] Complete deterministic reverse-order, crash, quota, rate-limit, cleanup,
  and concurrent-mailbox coverage without provider usage.
- [x] Specify the write-enabled hostile-workspace matrix in
  `docs/threat-model.md` before any live attempt.
- [x] Implement its typed minimal-write profiles and deterministic fake-target
  cases before requesting live-provider approval.
- [x] Add a parent-owned hostile-write case plan, authoritative success/denial
  closure, and guarded cleanup receipt without launching providers.
- [x] Audit the exact first native proposal without launching a provider; bind
  closure to the actual launcher-argv digest, timeout/output limits, explicit
  parent/depth fields, pinned Codex version, canonical canary prefix, strict
  manifests, sibling sentinel, and parent-owned cleanup.
- [ ] Request separate owner approval before each native-client
  write-enabled hostile-workspace case; deterministic coverage is not live
  evidence.
- [x] Implement and live-verify the typed website/image artifact route in `docs/artifact-route.md`.
- [x] Reject requested output beneath workspace control directories and keep config-error receipts out of rejected paths.
- [x] Reject raw arguments that conflict with launcher-controlled target flags.
- [x] Complete the scoped credential non-persistence audit in `docs/token-audit.md`.
- [x] Add redacted text, mailbox, and typed-artifact fixtures; scan returns 0 findings.

### Phase 1: Make Manual Install Safe

- Keep `docs/install-skill.md` and `docs/safety-checklist.md` current.
- Extend the `doctor`/environment-check command as new blockers appear.
- Add setup-time expectations and known failure classes.
- Add uninstall/disable instructions.
- Keep the mailbox fallback documented for environments where direct reverse
  launch is blocked or intentionally disabled.
- Keep `doctor` non-destructive by default; optional version/auth hints must not
  ask for tokens or launch model work.

### Phase 2: Package The Experience

- Package as a plugin or equivalent installable bundle.
- Keep repo-scoped install as the fallback.
- Add release checklist with artifact redaction and claim gates.
- Add a minimal public README section only after Phase 0 and Phase 1 gates pass.

### Phase 3: Expand Beyond Claude/Codex Carefully

- Create an adapter interface document.
- Run Gemini CLI feasibility against the adapter contract.
- Run Cursor feasibility against the adapter contract; do not claim support
  until a fake target, no-edit live probe, and receipt parser exist.
- Add a fake-Gemini target before any live Gemini probe.
- Add orchestrator policy tests before Gemini can participate in multi-target
  routing.
- Only then decide whether Gemini support belongs in MVP+1.

### Phase 4: Public Positioning

- Publish only verified claims.
- Keep competitor comparisons specific and dated.
- Lead with the one-liner and the imagegen demo.
- Avoid saying "fully free"; say "no extra Cairnspan server or backend, assuming
  the target app is already installed and authenticated."

## Definition Of Strong Enough

Cairnspan is strong enough to share with friendly users when:

- a new user can follow the repo-scoped install path without private context,
- dry-run and read-only probes catch common setup failures,
- both launchers have fake-target tests and live smoke evidence,
- the bounded two-way loop is repeatable and its route receipt can be explained honestly,
- raw artifacts are excluded from commits,
- public examples are redacted,
- and the product promise is simple: no shared keys, no extra server, real
  receipts.
