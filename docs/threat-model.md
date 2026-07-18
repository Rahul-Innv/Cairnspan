# Cairnspan Threat Model

This document records what Cairnspan is trying to protect, what it is not trying to protect, and which tests must pass before the project is suitable for broader sharing.

## Assets

- Local OAuth-backed agent sessions for Codex and Claude Code.
- Target workspaces and source files.
- Prompts, model responses, tool outputs, and generated artifacts.
- Runtime receipts: `cairnspan-summary.json`, `events.jsonl`, `transcript.log`, and `final.md`.
- User identity signals in paths, session ids, account metadata, costs, and rate-limit events.
- Local configuration that can alter agent behavior, including skills, plugins, MCP configuration, hooks, and project instruction files.

## Trust Boundaries

- Cairnspan launches installed local clients. It should not copy, scrape, print, or broker OAuth tokens.
- Claude Code and Codex remain separate trust domains. One agent's tools, MCP servers, skills, auth, approval state, memory, and thread context do not automatically transfer to the other.
- A target agent may read the workspace it is launched in. A read-only run is a write-safety boundary, not a confidentiality boundary.
- Model providers and configured target-agent tools may receive readable prompt and workspace context. Cairnspan must not claim to prevent that exposure.
- Runtime artifacts are private by default. Public fixtures require explicit redaction and scanning.
- In a future three-agent topology, the orchestrator becomes a policy decision point. It must not allow one target agent to indirectly gain another target agent's broader tools, files, memory, or auth.

## Non-Goals

- Cairnspan is not a sandbox implementation.
- Cairnspan is not a secrets manager.
- Cairnspan is not a token broker.
- Cairnspan is not a long-running agent runtime, daemon, queue, or hosted control plane.
- Cairnspan does not make untrusted repositories safe to read with a cloud-backed agent.

## Primary Threats

### Workspace Prompt Injection

Project files such as `AGENTS.md`, `CLAUDE.md`, `.codex`, `.mcp.json`, hooks, scripts, or README content can instruct a target agent to ignore scope, reveal secrets, request broader tools, or write outside the intended path.

Required defenses:

- Launch only in workspaces the caller trusts.
- Keep default probes no-edit and minimal-tool.
- Launch Claude Code with safe mode by default so project/user hooks, plugins, and customizations are not loaded into unattended probes.
- Add malicious-workspace probes with poisoned instruction files and canary secrets.
- Record whether the target agent loaded project instructions, skills, hooks, MCP servers, or plugins.

### Read-Only Confidentiality Confusion

`read-only` prevents writes. It does not prevent the target agent from reading files and sending relevant context to the model provider or configured tools.

Required defenses:

- Public docs must say read-only is not a confidentiality boundary.
- No public demo should use a private production repo unless its readable contents are safe for the target model/provider.
- Add a canary-secret probe that verifies artifacts do not accidentally publish secrets, while documenting that a target agent may have read them.

### Later Write-Enabled Hostile-Workspace Matrix

The typed launcher profiles and deterministic fake-target cases are
implemented. This matrix still does not authorize a live run. Request owner
approval separately for each native-client edge.

Fixed setup:

- use one fresh disposable public-data workspace per case and one distinct
  native client edge; never use a product checkout or private product data;
- place authoritative receipts in a fresh parent-controlled directory outside
  every writable workspace and pin the explicit native executable path and
  exact inspected CLI version;
- pre-create only the hostile instruction fixtures, `allowed/`, a hashed
  outside-workspace sibling sentinel, and any case-specific link/reparse
  fixture; record strict before manifests for the workspace, sibling sentinel,
  and receipt root;
- permit exactly one declared regular-file result:
  `allowed/codex-result.txt` or `allowed/claude-result.txt`, containing one exact
  parent nonce and no other bytes;
- Codex must use the typed hostile-write profile that ignores user/project
  rules and ambient MCP/apps/plugins while enabling only the minimum reviewed
  write mechanism. Raw `--codex-arg` overrides are not an acceptable profile;
- Claude must retain safe mode, empty setting sources, disabled slash commands
  and Chrome, strict-empty MCP, no session persistence, a bounded budget, and
  an explicit minimal write-tool allowlist. Broad tools and
  `bypassPermissions` remain forbidden.

Implemented typed profile:

- both launchers accept `--execution-profile hostile-workspace-write` only with
  a 32-128 character lowercase hexadecimal `--hostile-write-nonce`, an exact
  `--expected-cli-version`, a fresh parent-controlled outside `--out-dir`, and
  a regular hashed sibling `--protected-sentinel`;
- the profile constructs the prompt itself and fixes the only output to
  `allowed/codex-result.txt` or `allowed/claude-result.txt`; callers cannot
  substitute a free-form prompt or raw target arguments;
- Codex is forced to `workspace-write`, strict config/rule isolation, disabled
  ambient app/plugin/MCP/web/shell features, and only `file_change` /
  `apply_patch` tool receipts;
- Claude is forced to `acceptEdits`, `Write` only, safe mode, empty setting
  sources, disabled slash commands and Chrome, strict-empty MCP, no session
  persistence, and a budget no greater than `$0.05`;
- both summaries record the profile, declared path, allowed/observed tools,
  nonce hash, sentinel hash/status, strict before/after manifest paths and
  changed paths, receipt-root status, containment, version, and descendant
  cleanup evidence.

Cases, each isolated in a fresh workspace:

1. poisoned `AGENTS.md` / `CLAUDE.md` requests canary disclosure, recursive
   delegation, receipt mutation, and writes outside `allowed/`;
2. parent traversal and absolute sibling writes target the hashed sentinel;
3. `.git`, `.agents`, `.codex`, `.claude`, and `.cairnspan` writes are
   requested explicitly;
4. a declared output path is replaced by a symlink, junction/reparse point,
   hardlink, or NTFS alternate data stream where the host can create that
   fixture;
5. the target exits normally after spawning a persistent descendant; and
6. timeout and output-limit termination occur after a partial declared write.

Deterministic evidence covers exact success for both adapters, poisoned
instruction fixtures, control-directory and sibling-sentinel writes,
parent-controlled receipt-root mutation, unexpected tools, pre-created
hardlinks, NTFS alternate data streams, and partial writes under timeout,
output-limit, and process-leak failures. Existing real-process fake-target
tests continue to prove timeout/output/process-leak descendant termination.

The parent case lifecycle in `hostile_write_case.py` adds an immutable native
executable/version/hash plan, exact dry/live launcher commands, pinned launcher
and parent Python runtime identities, prepared fixture manifest, closure
receipt, and guarded cleanup receipt. The dry root must contain only its
no-execution summary; any extra file fails closed and consumes that no-retry
proposal without authorizing live execution. It rejects plan, command,
launcher, or runtime drift, canaries or extra receipt files, missing forced-cleanup
evidence, cleanup before closure, reparse-backed cleanup targets, and cleanup
changes to the sibling sentinel or target receipt root. It never launches a
provider. Closure binds the live launcher's actual argv digest, timeout, output
ceiling, explicit parent/depth fields, prompt source, sentinel hash, and (for
Claude) budget to the immutable parent plan.
The closer also independently recomputes the strict workspace delta, declared
output bytes, current sentinel state, and exact reported changed paths. A
denial closes only with evidence specific to its selected case; generic target,
provider, authentication, or transport failure is not hostile-case evidence.

Every case fails closed unless all applicable checks pass: one terminal target
identity, pinned version match, strong Windows Job Object containment, verified
descendant cleanup, no recursive edge, no unexpected tool/MCP/web exposure, no
canary in protected receipts, unchanged sibling sentinel and receipt-root
baseline, and a strict workspace delta containing only the exact declared
result. Partial files are failures. Cleanup is parent-owned, occurs only after
receipts and after-manifests are captured, and must remove the disposable
workspace without touching the sibling sentinel or authoritative receipts.

### Tool And MCP Bleed-Through

Configured MCP servers and tools can be visible to a target agent even when the origin agent does not have them. Claude Code already showed configured MCP tool visibility before the launcher default was tightened to `--strict-mcp-config`.

Required defenses:

- Live-verify Claude strict-MCP no-tools behavior.
- Document Codex MCP behavior as observed configuration, not isolation.
- Require explicit opt-in for configured MCP usage.
- Record visible tools/MCP servers in receipts when possible.
- Treat caller-supplied `--mcp-config` as unsafe executable configuration, not as a harmless isolation flag.

### Ambient Credential And Provider Override Leakage

Child processes inherit the launcher's operating-system environment unless it is explicitly filtered. Raw API keys or provider-routing variables can defeat the OAuth-backed claim and can be printed by a hook or tool.

Required defenses:

- Remove known raw API-key and alternate-provider environment overrides from children by default.
- Record only the names of scrubbed variables, never values.
- Require explicit unsafe acknowledgement to inherit those variables.
- Do not remove OAuth/keychain credentials that the installed client legitimately owns.
- Treat broad environment allowlisting as a later enterprise control; the current filter is not a general secrets manager.

### Provider Authentication Policy Drift

Provider documentation can distinguish native application use, programmatic CLI use, third-party products, and credential routing differently over time. A technically functional launch can still cross a provider-policy boundary.

Required defenses:

- Launch only the unmodified official target client; do not impersonate its protocol.
- Never extract, export, replay, proxy, or persist provider OAuth credentials.
- Scrub ambient long-lived script tokens such as `CLAUDE_CODE_OAUTH_TOKEN` by default. Inheriting one requires the existing explicit unsafe environment override.
- Do not offer provider login or route subscription credentials on behalf of another user.
- Keep owner-local native-client use distinct from public, shared, commercial, or hosted automation.
- Recheck primary provider authentication and billing documentation before public release and after target CLI changes.
- Use API-key or managed-provider authentication for shared production automation unless the provider explicitly confirms another method.

### Unsafe Argument Override

Raw target-agent arguments can override safe defaults, enable broad tools, change permission modes, attach alternate MCP config, or bypass sandbox behavior.

Required defenses:

- Treat raw args as unsafe and require an explicit reason.
- Add raw-arg bypass tests for duplicate permission/sandbox flags, `--permission-mode=bypassPermissions`, broad tools, `--bare`, alternate MCP config, and danger flags.
- Prefer typed launcher options over raw passthrough.

### Output Directory Abuse

`--out-dir` writes multiple files and can overwrite existing receipts. If unrestricted, it can become an arbitrary write/truncate primitive.

Required defenses:

- Refuse existing non-empty output directories unless an explicit overwrite flag is added.
- Prefer output directories under `.cairnspan/` only for read-only targets.
- Require an explicit opt-in for output directories outside the target workspace.
- Add parent traversal, symlink, junction, and `.git/hooks` path tests.
- For write-enabled targets, place authoritative receipts outside the target `--cwd`; target-writable receipts are evidence, not tamper-proof audit records.
- Reject write-capable launches whose receipt directory resolves inside `--cwd`; random capture names and file-identity checks remain defense in depth.

### Recursive Delegation And Quota Burn

A two-way bridge can accidentally recurse: Claude launches Codex, Codex launches Claude, and so on. This can burn quota, create many logs, or widen permissions.

Required defenses:

- Add run-depth metadata.
- Add max-depth, max-runtime, max-output-bytes, and max-cost gates.
- In Phase 2, model delegation as a run graph: parent run id, child run ids, visited agents, max edges, max fan-out, retry budget, and cycle detection for paths such as `Claude -> Codex -> Gemini -> Claude`.
- Do not allow the target run to request broader permissions than the origin run without explicit user approval.
- Add a loop probe that proves recursion stops cleanly.
- Use a trusted parent-orchestrated route for the first full loop; do not let targets reset route policy by recursively launching a fresh root run.

### Process Escape And False Process Attribution

Target CLIs can spawn internal helpers. A surviving helper can outlive timeout or output enforcement, while a recycled operating-system PID can make an unrelated process look like a target descendant.

Required defenses:

- Put every Windows target in a kill-on-close Job Object before resume and fail closed without running when attachment is unavailable.
- Use process snapshots only to supplement an attached Job Object, never as a successful fallback containment claim.
- Do not treat a POSIX process group as strong adversarial containment; block authoritative closure until a tested cgroup, namespace, or equivalent host control is available.
- Allow only a short bounded normal-exit grace; terminate the contained job and fail if descendants remain.
- Record descendant image details on failure without broad executable allowlists.
- Pin and hash the target executables before the route and verify their identities again before closure.
- Test persistent descendants, timeout/output cleanup, short-lived helpers, and recycled historical PIDs.

### Binary Artifact And Image Injection

Generated images and other binary artifacts can be malformed, oversized, mislabeled, replayed, or carry instruction-like text, QR codes, URLs, local paths, secrets, or metadata. A target-produced manifest cannot be trusted to describe the bytes accurately.

Required defenses:

- Generate only in a fresh scratch workspace, never directly in a product repository.
- Let the parent compute a typed artifact manifest from the resulting bytes.
- Validate normalized path, count, regular-file status, signatures, decoded format, dimensions, pixel/frame limits, byte limits, and SHA-256.
- Include hidden paths, reparse points, hardlinks, and alternate data streams in unexpected-change checks.
- Treat pixels, OCR text, metadata, URLs, and QR codes as untrusted data, never as executable instructions.
- Strip or explicitly approve metadata before integration.
- Record provenance and rights constraints for public use.
- Require a separate human-approved integration edge with declared destination changes.
- Treat visual-review and approval CLI flags as operator attestations. An agent-authored `passed` value is not human approval and must not authorize closure or integration.

### High-Volume Unattended Artifact Batches

A downstream product consumer may eventually need bounded image and artifact batches. Repeating a
safe single-item route without an immutable batch contract creates quota burn,
unbounded disk growth, stale retries, partial integration, and hidden queue or
scheduler semantics. Account-backed image generation must not be assumed to
support sustained throughput.

Required defenses:

- Prove the current pinned CLI's image-generation and image-view capabilities
  separately on fresh synthetic public data with `--require-image-capability`
  before any product-shaped input or batch is eligible.
- Represent a batch as a finite immutable ordered item list with a batch id,
  item ids, prompt/input hashes, expected artifact roles, and a closure state.
  The mailbox remains a bounded exchange and cannot supply queue semantics.
- Start at concurrency 1 with zero automatic retries. Every retry, batch-size
  increase, or concurrency increase requires a new parent plan and approval.
- Freeze per-run, per-batch, daily, disk, output-byte, timeout, and private
  retention ceilings before launch. Limits must be enforced during execution,
  not inferred from final artifacts.
- Use fresh per-item staging, receipts outside target-writable roots, parent-
  generated typed manifests, hash-bound visual approval, and a separate
  integration edge. One item's approval never authorizes another item.
- Stop the entire batch before the next item on auth, quota, rate-limit,
  required-capability, containment, unexpected-file, manifest, cleanup, or
  receipt-integrity failure. Preserve the failed item and batch disposition;
  do not skip, retry, or continue automatically.
- Run no more than three synthetic items in the first measured pilot. Use its
  actual latency, disk, output, cleanup, and provider-limit evidence before
  recommending a larger account-backed batch or an API-backed alternative.
- Bind owner approval to both an operator decision reference and the exact
  immutable batch-plan SHA-256. Reject unexpected batch/proposal-root entries,
  reparse points, altered item order, substituted terminal claims, daily-ledger
  races, resume attempts, and any later-item receipt after failure.
- Treat historical product artifact work as engineering evidence only. Its
  product authorization, receipts, visual approval, and integration closure
  cannot be replayed for another product.
- Respect product ownership boundaries. A Cairnspan setup or batch must not
  edit or test a product tree that another active session owns.
- Scheduling or overnight batch supervision belongs to a separately approved
  parent controller profile and must not create a second collector schedule.

### Orchestrator Confusion

In a three-agent setup, one orchestrator may route tasks among Claude Code, Codex, Gemini, and later adapters. That creates new failure modes: wrong-agent routing, conflicting edits, transitive trust, hidden data egress, and policy bypass through a more permissive adapter.

Required defenses:

- Add a route-plan object before execution: origin, target chain, allowed agents, denied agents, allowed tools, workspace scope, data labels, max depth, max fan-out, max cost, and approval state.
- Use a capability registry for each adapter: supported tools, write modes, MCP behavior, network behavior, context handling, output format, cost controls, and known caveats.
- Route by policy and capability, not by free-form model preference alone.
- Require each request to carry data classification, allowed targets, allowed tools, allowed workspace roots, max cost, max depth, max runtime, and expected artifact types.
- Default-deny unknown adapters, unknown tools, unknown data classes, and unknown output paths.
- Each hop needs its own policy decision. Approval for Claude does not imply approval for Codex or Gemini.
- Prevent transitive escalation: a low-permission origin cannot ask an orchestrator to launch a higher-permission target without explicit user approval.
- Add conflict controls for concurrent or multi-target edits: file locks, disjoint write scopes, merge policy, and manifest comparison.
- Add routing receipts that show why a target was chosen and which targets were rejected.
- Add a policy-denial receipt so blocked handoffs are auditable, not silent.
- Treat target-agent output as untrusted input to the orchestrator unless the receipt contract verifies it.

### Cross-Vendor Data Exposure

A three-agent workflow may send the same prompt, source context, or generated artifacts to multiple model providers. That is materially different from a two-agent handoff.

Required defenses:

- Treat each target as a separate vendor boundary and data egress event.
- Add a data-classification field to requests and summaries. Minimum labels: `public`, `internal`, `source-code`, `customer-data`, `secrets`, and `regulated`.
- Support deny lists such as "do not send to Gemini" or "OpenAI-only" for specific files, prompts, or projects.
- Add prompt minimization and redaction before cross-provider hops.
- Keep provider-specific retention, telemetry, and enterprise-policy notes in adapter docs.
- Add probes that confirm redaction and routing policy are applied before a prompt reaches a target agent.

### Model Or Effort Substitution

A caller can request an expensive or behaviorally distinct model/effort level,
then accidentally or deliberately bypass the reviewed contract through raw
arguments, Codex config expressions, profiles, case mutation, or ambiguous
precedence. A launcher command can also record the request while the provider
uses something else.

Required defenses:

- expose only typed `--model` and the closed effort enum `low`, `medium`,
  `high`, `xhigh`, `max`;
- make Claude emit one native effort pair and Codex emit one launcher-owned
  fixed-key config value;
- reject raw model/effort/config/profile conflicts and reject effort in
  immutable profiles such as `hostile-workspace-write`;
- ensure strict isolation cannot duplicate the Codex effort key;
- record requested model/effort plus expected and observed CLI versions in
  every summary state;
- treat requested values as request evidence only and require independent
  usage/runtime evidence before claiming the provider honored them;
- stop an ordered multi-phase program after every phase until closure is
  validated and the owner separately approves the next phase.

### Enterprise Audit And Governance

Enterprise use needs more than local success. It needs predictable policy, evidence, and revocation.

Required defenses:

- Version the run contract and adapter contract.
- Add a central policy engine before Phase 2. It should decide allowed adapters, sandbox level, raw args, tools/MCP, output path, provider, data class, budget, and whether human approval is required.
- Record an audit graph: correlation id, route plan, policy decisions, approvals, data labels, prompt hashes, transformed prompt hashes, adapter versions, executable paths, tool/MCP visibility, costs, and final disposition.
- Record policy version, launcher version, adapter version, target CLI version, command hash, prompt hash, artifact hashes, and changed-file manifest.
- Add tamper-evident receipt chaining or at least stable receipt digests before enterprise positioning.
- Add role/approval concepts before allowing write-capable or multi-target runs.
- Add budgets at run, route, user, workspace, provider, and day levels. Include concurrency caps, retry caps, fan-out caps, and aggregate cost reporting across providers.
- Add retention controls for raw logs and public fixtures.
- Add deterministic cleanup/uninstall guidance for skills, plugins, launchers, and generated configs.
- Add enterprise deployment controls before enterprise positioning: signed releases, pinned versions, SBOM, centrally managed policy, allowlisted binaries, proxy/egress support, SIEM-compatible audit export, retention/redaction policy, kill switch, and documented uninstall/disable path.

### Artifact Leakage

Raw events and transcripts may contain local paths, prompt text, private model output, account metadata, session ids, costs, tool output, and secrets printed by the target agent.

Required defenses:

- Keep raw `.cairnspan/` outputs ignored.
- Add an artifact scanner for public fixtures.
- Redact local usernames, private paths, prompt bodies, account identifiers, run/session ids where appropriate, secrets, cookies, key material, and private model output.
- Public fixtures should prove behavior with sanitized receipts, not raw logs.

## Release Blockers

Before public release:

- [x] Strict-MCP Claude no-tools behavior is live-verified.
- [x] The combined reverse strict-MCP/no-edit probe passes with origin-side before/after manifests.
- [x] A bounded parent-orchestrated text route passes under `docs/two-way-loop.md`, with aggregate route limits and protected receipts.
- [x] Artifact scanning exists and catches canary secrets.
- [x] Baseline output-directory overwrite/escape and raw-argument gates are tested.
- [x] Public docs consistently avoid overclaiming token, confidentiality, or sandbox guarantees.
- [x] Strict no-tool hostile-workspace probes pass for both native clients with
  pinned versions, exact markers, zero tool/MCP use, clean protected receipts,
  unchanged manifests, and verified cleanup.
- [ ] The separately specified write-enabled hostile-workspace matrix passes;
  no such live run is authorized by the strict no-tool evidence.
- [x] The scoped OAuth token/non-persistence audit is complete without claiming visibility into provider-client internals.
- [x] Redacted text, mailbox, and typed-artifact fixtures pass scanning and manual structure review.
- [x] Clean copied-skill installation is verified; independent-user onboarding remains a product-quality follow-up.

Before Phase 2 / three-agent orchestration:

- Phase 1 full two-way loop is repeatable.
- Adapter contract and capability registry exist.
- Route-plan schema and central policy engine exist.
- Routing policy is explicit and testable.
- Data classification and allowed-target policy are represented in request and summary schemas.
- Transitive permission escalation is blocked by tests.
- Multi-target conflict handling is tested.
- Audit graph and budget enforcement are tested.
- Provider/data egress documentation exists for every adapter.
