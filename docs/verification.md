# Cairnspan Verification

## Status Ledger

This bullet ledger was maintained at the top of the README until 2026-07-18 and
is preserved verbatim here. The README now carries a condensed "What's
verified" table that links to this section.

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

## Naming

- [x] Checked obvious exact-name collisions for Agent Parley and Claude/Codex coordination variants on 2026-07-08.
- [x] Rejected `agent-parley` after GitHub API returned existing public repos/orgs.
- [x] Record the superseded prototype naming decision without carrying its
  runtime identifiers into current source.
- [x] Preserve the 2026-07-10 historical prototype namespace check as naming
  research; it is not evidence for the selected Cairnspan name.
- [x] Recheck bare `Parley` on 2026-07-11 and reject it as the public identity because active multi-model, agent-negotiation, multi-agent-chat, npm, PyPI, and older software uses already collide in the same category.
- [x] Reject the former OAuth-led prototype identity as the future public identity because `OAuth` is an implementation detail with avoidable provider-policy and token-brokering implications.
- [x] Owner selected **Cairnspan** / `cairnspan` as the working public identity after a broader naming theme review.
- [x] Point-in-time `Cairnspan` smoke check on 2026-07-11: focused GitHub, GitLab, npm, PyPI, broad web, and trademark searches found no obvious indexed exact-name software or AI collision. This is not legal clearance or a reservation.
- [x] Execute the clean-break internal/public identifier migration across
  display names, skill paths, runtime defaults, schemas, receipts, protocol
  markers, environment prefixes, tests, CI, examples, fixtures, and docs.
  Historical ignored receipts remain untouched and no legacy runtime alias is accepted.
- [ ] Re-run exact-name, namespace, domain, package-registry, and legal trademark review immediately before publication.

## OAuth Thesis

- [x] Document that OAuth-backed local agent sessions are the primary product wedge.
- [x] Document that raw API-key orchestration is not the primary product.
- [x] Document private-first status and raw log sensitivity.
- [x] Verify Codex can run through the user's local OAuth-backed CLI session when passed the explicit local Codex CLI path.
- [x] Verify Claude Code can run through its local authenticated entrypoint (`claude -p --output-format json`, no-tools probe, return code 0, exact expected result, session id captured in the private receipt).
- [x] Complete the scoped credential non-persistence audit in `docs/token-audit.md`: no credential-extraction code or recognized token/key finding appeared in public surfaces or selected live receipts. Provider-client internal storage remains out of scope.

## Static Validation

- [x] Probe and record the native Codex and Claude Code versions on every valid dry/live launcher run; exact expected-version mismatches fail before target launch.
- [x] Freeze inspected CLI versions into the parent route plan, pass the exact pins to both edges, validate child version receipts, and recheck executable identity plus version before closure.
- [x] Validate canonical skill with `quick_validate.py`.
- [x] Validate Claude Code-facing skill shim with `quick_validate.py`.
- [x] Compile Codex and Claude launchers with `py_compile`.
- [x] Dry-run launcher and inspect generated command summary.
- [x] Add stdlib unit tests for launcher dry-run, path validation, parsing, nonzero exit, timeout, unsafe flags, run id collision avoidance, and inherited stdin closure.
- [x] Add output-directory policy tests for both launchers: outside-workspace output is denied by default, non-empty output directories require `--overwrite-out-dir`, overwrite preserves existing files instead of deleting them, file-shaped output paths are rejected even with overwrite, and config-error fallback avoids a hostile `.cairnspan` Windows junction.
- [x] Add raw-argument bypass tests for both launchers: raw passthrough is denied without the launcher-specific allow flag and still requires `--allow-unsafe --unsafe-reason`; Claude configured-MCP opt-in also requires the unsafe gate and reason.
- [x] Add Claude broad-tool tests so exact and mixed broad tool values require unsafe opt-in.
- [x] Add Codex image-path preflight tests so workspace-relative images resolve inside `--cwd`, outside images and parent traversal are rejected, directories are rejected, and missing images fail as config errors before target launch.
- [x] Add artifact scanner tests for clean redacted fixtures, canary secrets, JSON-escaped Windows user paths, bearer tokens, binary-byte scanning, oversized-artifact fail-closed behavior, and missing path config errors.
- [x] Extend scanner adversarial coverage to base64, percent encoding, line splitting, and compressed-container fail-closed handling.
- [x] Run the artifact scanner over the private redacted fixture set (0 findings; fixtures are kept private and not shipped in this tree).
- [x] Add recursion-depth tests for both launchers: summary metadata is recorded, child depth requires a parent run id, parent run id requires nonzero depth, and depth greater than max depth fails before target launch.
- [x] Add output-limit tests for both launchers: a fake target flooding stdout returns 125, records `error_kind: output_limit`, and captures `max_output_bytes` in the summary.
- [x] Add descendant cleanup tests proving timeout and output-limit termination kill delayed child processes on Windows.
- [x] Remove the fast-child containment race by creating Windows targets suspended, assigning the kill-on-close Job Object, resuming, and waiting through a bounded post-exit settlement window. Five consecutive fast `cmd.exe` spawn tests and a live two-provider route passed.
- [x] Add protocol-integrity tests for empty/invalid/damaged JSONL, Codex `turn.failed` with zero exit, contradictory Claude result events, Unicode output, and terminal-event/session-id requirements.
- [x] Add prompt/command-boundary tests for size ceilings, NUL, invalid UTF-8, and Windows command-line limits.
- [x] Add auth-environment, workspace-PATH shadowing, shell-wrapper acknowledgement, sensitive-argument redaction, hardlink overwrite, safe-mode, and explicit MCP-config gates.
- [x] Add mailbox schema tests for request/response round-trip, prompt/prompt_ref exclusivity, id/path escape rejection, response result/error requirements, and CLI validation.
- [x] Add doctor tests for fake-binary success, missing workspace failure, outside output-dir warning, and file-shaped output-dir failure.
- [x] Add workspace-manifest tests for hidden-file coverage, runtime exclusions, add/change/delete detection, and CLI comparison.
- [x] Add tracked-snapshot tests for file/count/aggregate ceilings, gitlink rejection, and tracked secret-content denial; scan exact Git blob bytes before packet export.
- [x] Delimit design-spec values as untrusted JSON data in the canonical image prompt and document that behavioral injection resistance still requires a live synthetic probe.
- [x] Document that visual-review and integration flags are trusted human/operator attestations, not agent-authorized facts.
- [x] Extend strict route manifests to include runtime-named paths, empty directories, reparse metadata, NTFS alternate data streams, file identity, mode, link count, and manifest-policy comparison.
- [x] Add stable terminal-event and target-identity checks, tool/MCP observation, strict Codex isolation, and no-tool-use enforcement.
- [x] Add Windows normal-exit descendant checks and recycled-PID regression tests; Job Object state is authoritative whenever containment is available.
- [x] Fail closed before target resume when Windows Job Object attachment fails; record `containment` in successful summaries and require `job-object` in authoritative route/artifact closures. POSIX process groups remain non-authoritative.
- [x] Reject write-capable Codex or Claude runs whose authoritative receipt directory resolves inside the target `--cwd`; randomize capture names and reject capture-path identity replacement.
- [x] Reject attached reserved Codex short options (`-s...`, `-c...`, `-C...`) in raw passthrough.
- [x] Bound PNG inflation to the IHDR-derived scanline ceiling; reject APNG, malformed core chunk ordering/`PLTE`, and undeclared ancillary chunks.
- [x] Bind artifact closure to the exact generation prompt reconstructed from the validated design spec and manifest output path.
- [x] Pin mailbox request/response validation and hashes to one open-handle byte read; closure stores content hashes instead of re-reading and embedding raw prompt/final text.
- [x] Focused post-Opus gates: 28 artifact/mailbox/critique tests passed; 131 launcher/two-way tests passed with 1 expected Windows file-symlink privilege skip.
- [x] Full post-Opus gate: 198 tests passed in 345.156 seconds with 2 expected Windows symlink-privilege skips; compile passed; both skills validated; docs/skill/shim/README scans returned 0 findings.
- [x] Final expanded offline gate: 206 tests passed in 404.547 seconds with 2 expected Windows symlink-privilege skips after encoded-secret scanning, committed-blob scanning, snapshot limit/gitlink tests, untrusted design-JSON delimiting, and human-attestation documentation.
- [x] Post-version/hostile-probe gate: 211 tests passed in 350.791 seconds with 2 expected Windows symlink-privilege skips; compile passed; both skills validated; docs/skill/shim/README scans returned 0 findings.
- [x] Add deterministic failure classification for provider rate-limit, quota,
  and native crash signals in both launchers; propagate those reasons through
  the parent route instead of collapsing them into generic target failure.
- [x] Add deterministic Claude-first parent-route coverage for ordered closure,
  first-edge rate-limit, and first-edge crash while retaining the existing
  Codex-first fields and fail-closed receipt validation. No Claude-first live
  provider claim is made.
- [x] Add a cross-process six-writer mailbox race in addition to the existing
  threaded four-round race; exactly one immutable request publishes and no temp
  file remains.
- [x] Add an explicit fast test runner that excludes only the two launcher
  process-integration modules and the two-way process harness; `full` still
  discovers every `test_*.py` module and remains the CI gate.
- [x] Add Codex image-attachment prompt-boundary coverage with `--`, closed
  stdin, and exact positional prompt delivery.
- [x] Add additive Codex receipt fields and a required-capability option so a
  code-mode-host or image-view startup failure cannot close as success.
- [x] Extend `doctor.py` to inspect the executable passed through `--codex-bin`
  for `code_mode_host` and `image_generation` flags while reporting
  `unknown(runtime_unverified)` when offline evidence cannot prove startup.
- [ ] Run the current binary's bounded synthetic `$imagegen` and `view_image`
  probes with `--require-image-capability`; this requires owner approval and
  live provider usage. Both are required gates for downstream image
  workflows, not optional product demos.
- [x] Final 2026-07-12 local gate: fast tier 84 tests in 116.488 seconds with 1
  expected Windows symlink-privilege skip; authoritative full rerun 224 tests
  in 616.147 seconds with 2 expected Windows symlink-privilege skips;
  `compileall`, canonical and shim skill validation, `git diff --check`, and
  README/docs/canonical-skill/shim/Claude-surface artifact scans all passed.
- [x] Add typed `hostile-workspace-write` profiles to both launchers. Require a
  canonical parent nonce prompt, fixed declared path, native version pin, fresh
  outside receipts, sibling sentinel, narrow tool allowlist, strict manifests,
  exact bytes, intact receipt root, and cleanup evidence.
- [x] Add six deterministic fake-target profile cases covering both success
  paths, poisoned workspace instructions, control/sibling/receipt writes,
  unexpected tool exposure, hardlink/ADS substitution, and partial writes under
  timeout, output-limit, and process-leak failures. No provider was called.
- [x] Post-profile local gate: fast tier 84 tests in 46.264 seconds with 1
  expected Windows symlink-privilege skip; authoritative full tier 230 tests in
  289.022 seconds with 2 expected skips; compile, both skill validations,
  `git diff --check`, and all five public-surface scans passed.
- [x] Add `hostile_write_case.py` with parent-owned `prepare`, `close`, and
  `cleanup` stages. Bind a fresh case marker to an immutable plan, executable
  hash/version, exact launcher commands, prepared manifest, target receipts,
  and guarded direct-child cleanup.
- [x] Audit the exact first Codex proposal without executing either generated
  launcher command. Pin `codex-cli 0.144.0-alpha.4`, one synthetic
  `poisoned-instructions` case, zero retries, explicit depth/fan-out 1, 120
  seconds, 1 MiB output, fresh outside receipts, a sibling sentinel, strict
  manifests, and parent close/cleanup. Bind closure to the live launcher-argv
  digest plus the receipt timeout/output policy and canonical `CAIRNSPAN_*`
  canary prefix. Focused hostile-write/naming gate: 20 tests passed in 32.881s.
  Final gate: 87 fast tests in 67.128s with 1 expected Windows symlink skip;
  244 full tests in 344.352s with 2 expected skips; compile, canonical and both
  shim validations, `git diff --check`, and all five scans passed.
- [x] Make parent closure independently verify the exact prepared-to-after
  manifest delta, declared result bytes, current sibling-sentinel state, and
  reported changed paths. Require case-specific denial evidence so an unrelated
  provider or transport failure cannot close as `denied-as-expected`: control
  paths, actual sibling mutation, observed process-leak details, or a nonempty
  partial declared result must match the selected case. The prepared schema
  `0.2` Codex plan and its stored dry/live command hashes remain unchanged.
  Focused hostile-write/naming gate: 23 tests passed in 92.491 seconds. Fast
  tier: 87 tests passed in 122.557 seconds with 1 expected Windows symlink
  skip. Authoritative full tier: 247 tests passed in 600.975 seconds with 2
  expected skips. Compile, all three skill validations, all five scans, and
  `git diff --check` passed.
- [x] Supersede, without modifying or executing, the schema `0.2` hostile-write
  proposal whose dry-run and live commands shared one receipt root. Schema
  `0.3` binds each command and digest to a distinct initially absent root,
  forbids overwrite flags, requires the dry-run no-execution summary before
  live closure, and binds closure to an owner approval reference plus the exact
  approved plan SHA-256. Focused coverage rejects missing, merged, swapped,
  extra, and reused receipt evidence; 17 hostile-case tests passed. Final gate:
  118 fast tests in 139.255 seconds with 1 expected Windows privilege skip;
  292 full tests in 758.416 seconds with 2 expected skips; compile, all three
  skill validations, all five public-surface scans, and `git diff --check`
  passed. A fresh schema `0.3` proposal was then prepared and re-audited with
  matching marker/plan identity, distinct absent receipt roots, no overwrite
  flags, and no provider execution.
- [x] Execute the exact owner-approved schema `0.3` dry command once and fail
  closed before provider use when parent validation detects an extra
  `write-profile-before.json` beside the required no-execution summary. Preserve
  the consumed dry root; do not run live, retry, close, clean, or merge evidence.
  Fix both launchers so hostile dry runs write only `cairnspan-summary.json`,
  and add real Codex/Claude dry-run coverage. Supersede the unexecuted interim
  replacement with schema `0.4`, which also binds launcher and parent Python
  runtime path/hash/version at load and closure. Focused profile/case gate:
  26 tests passed in 110.221 seconds. Fast tier: 122 tests passed in 169.212
  seconds with 1 expected Windows skip. Authoritative full tier: 298 tests
  passed in 459.386 seconds with 2 expected skips. The fresh schema `0.4`
  proposal remains unapproved and unexecuted with distinct absent roots.
- [x] Add ten deterministic parent-case tests covering both adapter success
  receipts, all seven case names, plan tampering, canary and extra-receipt
  rejection, cleanup-before-closure denial, unchanged sentinel/receipts, and
  required forced-cleanup evidence. Prove an already-existing unmarked case
  root is rejected without deletion or overwrite. No target provider was launched.
- [x] Record forced Windows timeout, output-limit, decode-error, and
  process-leak cleanup as `job-object` plus
  `descendant_cleanup_verified=true` after `run_process` finishes cleanup;
  retain non-authoritative POSIX process-group posture.
- [x] Parent-case gate: fast tier 84 tests in 117.922 seconds with 1 expected
  Windows symlink skip. The first 239-test full run failed one stale assertion
  expecting cleanup to remain unverified; its focused rerun passed after the
  assertion was corrected. The authoritative full rerun passed 239 tests in
  388.789 seconds with 2 expected skips. Compile, both skill validations,
  `git diff --check`, and all five public-surface scans passed.
- [x] Final preservation audit: remove automatic preparation-error cleanup
  because it could delete a pre-existing unmarked `--case-root`; leave partial
  failed preparations for explicit owner inspection instead. The focused
  10-case module passed in 24.592 seconds and the final authoritative full gate
  passed 240 tests in 398.737 seconds with 2 expected skips. Final compile, both
  skill validations, `git diff --check`, and all five scans passed.
- [x] Atomic Cairnspan migration gate: three naming-contract tests pass; fast
  tier 87 tests in 44.515 seconds with 1 expected Windows symlink skip;
  first full tier 243 tests in 298.869 seconds with 2 expected skips; final-state
  authoritative rerun 243 tests in 385.889 seconds with the same 2 expected
  skips; compile, canonical plus both shim validations, `git diff --check`, and
  all five public-surface scans passed. No provider was called.
- [x] Add route tests for closure, dry-run, nonce mismatch, both edge failures, timeout, output overflow, aggregate budget denial, stale roots, tool use, and strict workspace mutation.
- [x] Run `python skills\cairnspan\scripts\doctor.py --cwd "." --format json` (status `warn`; Python ok, cwd ok, out-dir policy ok, Claude resolved, `.cairnspan/` ignored, default Codex resolves to WindowsApps warning).
- [x] Re-run `python -m unittest discover -s tests` on the final 2026-07-09 hardening snapshot: 116 tests passed in 802.135 seconds, with 1 expected file-symlink image test skipped because Windows denied symlink privilege (`WinError 1314`).
- [x] Re-run the full suite after the 2026-07-10 live-evidence hardening: 118 tests passed in 151.486 seconds, with the same 1 expected Windows file-symlink privilege skip.
- [x] Final bounded-route gate on 2026-07-10: 146 tests passed in 327.138 seconds with 1 expected Windows file-symlink privilege skip; `compileall` also passed.
- [x] Final prepared-closure gate on 2026-07-10: 160 tests passed in 460.940 seconds with the same 2 expected Windows symlink-privilege skips.
- [x] Add repo-scoped install guide and safety checklist.
- [x] Add redacted public fixture for the basic Codex receipt shape and remove legacy raw bridge evidence with local paths.
- [x] Re-run the artifact scanner over the private redacted fixture set after fixture cleanup (0 findings).
- [x] Redact machine-specific paths from docs and old prompt files; run `python skills\cairnspan\scripts\scan_artifacts.py docs --format json` (0 findings).
- [x] Final 2026-07-09 gate: `compileall` passed, the full `docs` artifact scan returned 0 findings, and `doctor.py` returned only the understood WindowsApps Codex and Claude shell-wrapper warnings.

## Claude Code To Codex

- [x] Create launcher for `codex exec --json`.
- [x] Capture summary, JSONL path, transcript path, final path, return code, thread id, usage fields, run id, prompt hash, status, and error kind.
- [x] Classify WindowsApps `Access is denied` failure instead of crashing.
- [x] Support `--prompt-file` for shell-safe handoffs.
- [x] Validate target workspace exists before creating output directories.
- [x] Gate `danger-full-access` and raw Codex args behind explicit unsafe opt-ins.
- [x] Close child stdin with `stdin=subprocess.DEVNULL` so unattended parent agents do not make `codex exec` wait for extra stdin.
- [x] Find launchable Codex CLI: `<launchable-codex.exe>`.
- [x] Run basic live probe: `Reply with cairnspan-ok`.
- [x] Verify thread id capture from real Codex JSONL.
- [x] Verify final message capture from real Codex JSONL.
- [x] Verify Claude Code-origin basic probe after inherited-stdin fix (status succeeded, return code 0, thread id captured in the private receipt, about 27s, exact expected final).
- [x] Verify `$imagegen` can create an image artifact; Codex used its built-in `image_gen` path with no CLI/API fallback and no `OPENAI_API_KEY`, producing a non-empty valid-signature PNG. Source-file manifest diff was empty and scratch output was deleted after evidence capture.
- [x] Observe Codex MCP visibility through Cairnspan as discovery, not a required-MCP assertion. The launched session exposed Codex's own configured MCP set, confirming it is separate from Claude Code's. No MCP is currently required by Cairnspan.
- [x] Verify read-only runs do not edit files: a deliberate write was denied, the file never appeared, and origin-side before/after manifests matched exactly.
- [x] Verify direct sandboxed workspace-write filesystem calls stay within the intended workspace: the in-workspace write succeeded while the sibling write was denied. This does not claim that tool-managed staging locations remain inside `--cwd`.

## Codex To Claude Code

- [x] Discover whether Claude Code has a safe noninteractive local entrypoint (`claude -p`; verified Claude Code 2.1.201 with `--output-format json` and `--tools ""`).
- [x] Spec `start_claude_session.py` with the same artifact contract as the Codex launcher.
- [x] Add a Claude launcher with the same artifact contract (`events.jsonl`, `transcript.log`, `final.md`, `cairnspan-summary.json`, prompt hash/redaction, timeout handling, failure classification, `stdin=subprocess.DEVNULL`).
- [x] Add fake-Claude tests for dry-run redaction, JSON parsing, stream-json parsing, API error despite zero exit, nonzero auth failure, timeout, inherited stdin closure, unsafe gates, raw arg gates, and run id collision avoidance.
- [x] Verify a Codex-origin Claude Code basic probe through Cairnspan (status succeeded, return code 0, session id captured in the private receipt, exact expected final, bounded elapsed time and cost).
- [x] Fix Claude `stream-json` launcher requirement by automatically adding `--verbose`; first live attempt without it failed fast with `Error: When using --print, --output-format=stream-json requires --verbose`.
- [x] Add safer default command shape with `--strict-mcp-config` after observing configured Claude MCP tools in the successful stream init event.
- [x] Add a reproducible combined strict-MCP/no-tools/no-edit prompt and runbook with native executable, safe mode, protected receipts, bounded cost/runtime/output, terminal-event checks, and origin-side manifests.
- [x] Live-run the combined strict-MCP/no-tools/no-edit Claude probe on 2026-07-10. The hardened schema `0.4` rerun succeeded in 11.484s for `$0.01832`; final text matched exactly, a terminal result/session id were present, tools/MCP/plugins/skills/slash commands were empty, tool-use counts were zero, and the external before/after workspace manifests were identical.
- [x] Add defense-in-depth safe-mode flags and receipt-level capability/tool-use policy checks after the first live call still advertised installed customization metadata; the hardened rerun cleared plugins, skills, and slash commands while retaining only built-in agent labels.
- [x] Keep file-based request/response mailbox under `.cairnspan` as a fallback path.
- [x] Verify Codex can write a Claude handoff request in the shared-folder route.
- [x] Verify Claude Code can read the request and write one linked terminal response.
- [x] Verify Codex can consume the response in a read-only follow-up turn; exact final and unchanged manifest were verified.

## Parent-Orchestrated Two-Way Route

- [x] Implement immutable route-plan and closure receipts in a parent-controlled directory outside both target workspaces.
- [x] Enforce two edges, max depth/fan-out 1, zero retries, edge/route runtime and output ceilings, Claude budget, aggregate reported-cost ceiling, native executable identity, and fresh route roots.
- [x] Require exact Codex and Claude nonce artifacts and hash-link the verified first artifact into the second prompt and final closure.
- [x] Run the live Codex-to-Claude text route on 2026-07-10: status succeeded, state closed, 2/2 edges succeeded, 27.375s total, `$0.019557` reported Claude cost, Codex cost explicitly unreported.
- [x] Verify both target receipts had one terminal event and one identity, zero parse warnings, zero tools/MCP calls, and no surviving descendants.
- [x] Verify strict before/after manifests for both disposable workspaces were identical.
- [x] Independently recompute and match both final hashes, both child-summary hashes, the route-plan link, and final closure hash.
- [x] Complete deterministic crash/quota/rate-limit/cleanup coverage and a
  fake-target Claude-first full-route profile. One fresh native Codex-first
  repetition passed, and the shared mailbox closed Codex-to-Claude-to-Codex.
- [ ] Live-run Claude-first routing only after a separate exact owner-approved
  native proposal; deterministic reverse-order evidence is not live evidence.
- [x] Live-repeat the hardened synthetic Claude-design-to-Codex-image route, including instruction-like design data, and require the new containment/prompt/static-PNG closure contract.
- [x] Run the hardened live Claude design edge with instruction-like inert data: Sonnet 5 used, zero tools/MCP/web/customizations, one terminal identity, `job-object`, verified cleanup, exact schema, `$0.0196947`, and identical empty workspace manifests.
- [x] Prove a 240s Codex image timeout fails closed with no terminal event and no staging changes; one fresh bounded retry succeeded in 320.516s with one terminal identity, `job-object`, and verified cleanup.
- [x] Parent-validate the retry artifact under schema `0.3`: exact prompt derivation, bounded decompression, CRC/static/dimension/filter checks, strict `gAMA`/`pHYs`/`sRGB` validation, no unknown/text/profile/APNG chunks, and exact expected staging delta. SHA-256: `3956a64ceffcee7507867f974124f710db042fb8d6e87409c7647495cb11362b`.
- [x] Obtain owner visual approval for that exact hash and emit the final artifact-route closure; product integration remains `not-run`.
- [x] Pass the post-live compatibility gate: 209 tests in 490.636 seconds with 2 expected Windows symlink-privilege skips; compile, both skill validations, and all public-surface scans passed.
- [x] Run disposable hostile-workspace live probes against both native clients with synthetic canaries, poisoned project instructions, attempted outside writes, and recursive-launch requests. Both exact-marker runs used pinned versions, zero tools/MCP, `job-object` containment, unchanged strict manifests, no outside file, and no canary in protected receipts.
- [x] Add redacted public text, shared-mailbox, and typed-artifact fixtures; manual structure review and artifact scan returned 0 findings.
- [x] Implement and live-verify the typed website/image artifact route in `docs/artifact-route.md` with one accepted static PNG and no product integration.

## Typed Model/Effort Contract

- [x] Add optional typed `--effort {low,medium,high,xhigh,max}` to both
  launchers, with no normalization of empty, unknown, or case-mutated values.
- [x] Emit exactly one Claude native effort pair and one Codex launcher-owned
  `model_reasoning_effort` config value in deterministic locations.
- [x] Bump Codex summary schema to `0.14` and Claude summary schema to `0.12`;
  record `requested_model` and `requested_effort` on dry-run, configuration-
  error, fake success, and fake failure receipts without claiming provider
  honoring.
- [x] Update the synthetic redacted basic Codex receipt fixture to schema
  `0.14` with both additive request fields set to `null`; no private or ignored
  historical receipt was read or rewritten.
- [x] Reject raw Claude model/effort conflicts; raw Codex model/profile/config
  conflicts; typed Codex effort plus profile; effort under the immutable
  hostile-write profile; and strict-isolation effort-key duplication.
- [x] Extend `doctor.py` with separate selected-client executable, bounded
  version, typed model, typed effort/value, and `unknown(runtime_unverified)`
  outcomes. The probes neither authenticate nor launch a model.
- [x] Focused typed launcher/profile/doctor gate passed 27 tests in 51.697
  seconds using fake targets only.
- [x] Pass the final remediation gate: fast tier 90 tests in 55.301 seconds with
  1 expected Windows symlink skip; full tier 261 tests in 346.843 seconds with
  2 expected skips; compile passed; all three skill validations passed; all
  five scans returned 0 findings; `git diff --check` passed; and both
  fake-native dry runs recorded the exact typed model/effort pair with no target
  execution, tools, or MCP.
- [x] Run bounded non-auth native doctor inspection against the explicit
  binaries and matching hashes. Claude Code `2.1.201` advertises typed model and
  all five effort values. Codex `0.144.0-alpha.4` advertises typed model but not
  `model_reasoning_effort`, and its image host remains
  `unknown(runtime_unverified)`; neither warning is converted to success.
- [x] Add `synthetic_probe_case.py` to prepare a separate immutable Codex
  typed-effort proposal with the reviewed `gpt-5.6-sol` / `xhigh` pair, strict
  no-tool isolation, pinned native path/version/hash, exact command hashes,
  bounded limits, absent receipts, and `approval_state=not-granted`. The helper
  never launches Codex.
- [x] Split schema `0.2` dry-run and live receipt roots after proving the
  original shared root would block the live command following a dry run.
- [x] Add parent-owned closure that requires an operator approval reference,
  exact plan/marker/native/command/receipt bindings, independent JSONL parsing,
  one terminal identity, `job-object` containment, verified cleanup, strict
  workspace deltas, exact final markers, required image-tool events, and
  bounded static-PNG validation. Provider honoring remains explicitly unknown.
- [x] Pass 11 focused proposal lifecycle tests covering all three successful
  closures plus command drift, no-edit mutation, missing tool evidence, extra
  receipts, invalid approval references, root preservation, and version denial.
- [x] Prepare three schema `0.2` replacement proposals against native
  `codex-cli 0.144.0-alpha.4` with distinct absent dry/live receipt roots and
  `approval_state=not-granted`. Preserve but do not run the schema `0.1` plans.
- [x] Pass the final schema `0.2` gate: 101 fast tests in 114.316 seconds with
  1 expected Windows symlink skip; 272 full tests in 551.266 seconds with 2
  expected skips; compile, all three skill validations, all five scans, and
  `git diff --check` passed.
- [x] Prepare all three exact proposals against native
  `codex-cli 0.144.0-alpha.4` and confirm their receipt roots remain absent.
  Focused proposal tests passed 5/5; fast passed 95 tests in 92.935 seconds with
  1 expected skip; full passed 266 tests in 605.313 seconds with 2 expected
  skips; compile, three skill validations, five zero-finding scans, and
  `git diff --check` passed.
- [ ] After separate approval, run and close that exact synthetic proposal to
  establish native CLI acceptance of the launcher-owned effort mapping. Keep
  provider-side honoring unknown unless independent runtime usage exposes it.

## Commit And Artifact Safety

- [x] Ignore Cairnspan runtime logs.
- [x] Add MIT license.
- [x] Add a GitLab CI verification job for compilation, the stdlib test suite, and publishable-surface artifact scans.
- [x] Add private-first README, security policy, and contribution notes.
- [x] Add sample redacted run fixture.
- [x] Add tests for summary parsing.
- [x] Add tests for mailbox request/response schema.

## Public Alpha Release Candidate Gate

- [x] Reconcile the source version with the published `0.1.0`, record that its
  artifacts have no matching source tag or GitLab Release, and retain an exact
  claim ladder separating source-ready, public two-agent alpha, production,
  enterprise, and three-agent readiness.
- [x] Add an offline release checker with source, public-alpha, and production
  profiles plus four focused tests for alpha versioning, Git/tag state, exact
  commit-bound attestations, and the live write-hostile blocker.
- [x] Correct the contradictory Cairnspan naming checklist and refresh the
  time-sensitive Anthropic Agent SDK credit language against 2026-07-12 primary
  documentation.
- [x] Pass the final release-hardening gate: 296 tests in 518.356 seconds with 2
  expected Windows symlink-privilege skips; compile, three skill validations,
  all required root-file and five surface-tree scans, and diff hygiene passed.
- [x] Source profile reports 14 passes and 0 blockers.
- [x] After expanding root release-metadata scanning, pass the final fast tier:
  122 tests in 120.540 seconds with 1 expected Windows symlink-privilege skip.
- [ ] Public-alpha profile passes for a new reviewed patch version. Current
  blocker groups include the historical untagged `0.1.0` version, dirty
  candidate state, unclosed live write-enabled hostile matrix, and missing
  commit-bound human attestations. Never satisfy this gate by retro-tagging the
  current source as `v0.1.0`.

## Production Readiness Gate

Cairnspan should not be considered production-ready. Current core gates:

- [x] Codex can be launched unattended through an explicit pinned native path; default PATH remains a documented portability issue.
- [x] Claude Code reverse launcher is tested with strict tool/MCP isolation.
- [x] Both directions have successful live probes.
- [x] A bounded parent-orchestrated full text route is live-verified.
- [x] Runtime artifacts are ignored and strict live manifests showed no target-workspace changes.
- [x] Failure reports expose structured error kinds without requiring raw-log scraping.
- [ ] Broader native-client crash/quota/rate-limit and live canary pressure gates pass. Token audit, copied-skill install, redacted fixtures, repeated core route, and typed artifact gates are complete.
- [ ] Authoritative POSIX containment and live cleanup tests pass.
- [ ] Signed release artifacts and an SBOM are published.

## Positioning And Install Claim Gates

- [x] Complete and document the scoped credential non-persistence audit; do not extend the claim to provider-client internal credential storage.
- [x] Add and keep current a threat model covering confidentiality boundaries, prompt injection, MCP/tool bleed-through, raw argument bypass, output path abuse, recursive delegation, ambient credentials, and artifact leakage.
- [x] Verify public docs say read-only is a write-safety boundary, not a confidentiality boundary.
- [x] Add baseline raw-argument bypass tests for both launchers.
- [x] Add baseline output-directory overwrite and escape tests for both launchers, including a Windows junction fallback test for hostile `.cairnspan`.
- [x] Reject raw arguments that conflict with launcher-controlled sandbox, protocol, model, tool/MCP, session, isolation, and danger flags; retain the unsafe gate for noncritical passthrough.
- [x] Reject receipt output at the workspace root or beneath `.git`, `.hg`, `.svn`, `.claude`, `.codex`, and `.agents`, including the config-error fallback; existing junction tests remain in place.
- [ ] Re-run or replace the file-symlink image escape test when file-symlink/reparse-point creation is available.
- [x] Live-run strict no-tool hostile-workspace probes with poisoned instruction
  files, configured-MCP/tool isolation, synthetic canaries, attempted outside
  writes, and attempted recursive launch/disclosure; exact markers, clean
  protected receipts, unchanged manifests, and cleanup were verified.
- [x] Specify the separate write-enabled hostile-workspace matrix in
  `docs/threat-model.md`: disposable public-data workspaces, exact allowed
  result paths, typed minimal write profiles, hostile/link/cleanup cases,
  parent-controlled receipts, strict deltas, and parent-owned cleanup. This is
  a specification, not live-run authorization.
- [x] Implement and review the typed write profiles and deterministic cases;
  strict no-tool evidence still does not authorize live writes.
- [ ] Obtain separate owner approval and close each native-client
  write-enabled hostile-workspace case with fresh synthetic workspaces and
  parent-controlled evidence.
- [x] Add recursion-depth guards before claiming full two-way safety.
- [x] Add output-size guards before claiming full two-way safety.
- [x] Add aggregate route runtime, output, edge, and reported-cost guards; receipts must identify adapters whose cost is unreported.
- [x] Add an artifact scanner with canary-secret tests for public fixtures.
- [x] Extend artifact scanner coverage so oversized artifacts and NUL-containing binary bytes cannot silently produce a clean result.
- [x] Verify and document launch-and-exit architecture: no Cairnspan server, daemon, database, or hosted backend; descendant cleanup is receipt-gated.
- [x] State the cost boundary precisely: no persistent Cairnspan service, while provider-specific subscription/API limits, provider network, local CPU/RAM/disk, and model usage still apply. As of 2026-07-12, Anthropic documents a separate monthly Agent SDK credit for subscription-backed `claude -p` usage, effective 2026-06-15; the amount and billing behavior remain provider-controlled.
- [x] Recheck Anthropic primary documentation for official `claude -p`, CLI authentication, third-party credential-routing restrictions, and current billing; record the owner-local official-client boundary without claiming provider approval.
- [x] Scrub `CLAUDE_CODE_OAUTH_TOKEN` from both launcher child environments by default and cover it in fake-target tests.
- [ ] Obtain provider clarification before public copy claims that Cairnspan can use Claude subscriptions as a product feature; use API-key or managed-provider auth for shared production automation unless clarified.
- [x] Add a repo-scoped install guide.
- [x] Test a clean copied-skill folder: canonical and copied validation passed, copied scripts compiled, `doctor.py` passed with explicit native clients, and both launchers dry-ran from the copy.
- [x] Add a non-destructive environment checker for common setup blockers.
- [x] Extend the environment checker with bounded, credential-scrubbed version
  probes and typed model/effort capability reporting without asking for tokens.
- [x] Add uninstall/disable instructions for copied skills and future plugin installs.
- [x] Add an initial redacted public fixture that proves the receipt contract without exposing local paths, prompt text, account identifiers, or private model output.
- [x] Add redacted shared-mailbox and typed-artifact fixtures after manual review; the artifact scan returned 0 findings (fixtures are kept private and not shipped in this tree).
- [ ] Re-validate Hermes/OpenClaw comparison claims against current docs before using them in public copy.
- [ ] Re-validate Cursor and Perplexity comparison claims in `docs/cursor-perplexity-cross-analysis.md` before using them in public copy.
- [ ] Verify at least one third-adapter feasibility spike before claiming portability beyond Claude Code and Codex; Cursor and Gemini are both candidates.

## Three-Agent And Enterprise Gates

- [ ] Add an adapter contract covering launch mode, auth model, prompt input, workspace behavior, structured output, session id, permissions, tools/MCP, cost controls, and no-edit probe support.
- [ ] Add a fake-Cursor target and parser/policy tests before any live Cursor adapter probe.
- [ ] Add a capability registry for Codex, Claude Code, Cursor, and any Gemini adapter before orchestration.
- [ ] Add a route-plan object with origin, target chain, allowed agents, denied agents, allowed tools, workspace scope, data labels, max depth, max fan-out, max cost, and approval state.
- [ ] Add request/schema fields for data classification, allowed targets, allowed tools/MCP, allowed workspace roots, max cost, max runtime, max output bytes, max depth, expected artifacts, and cross-provider sharing policy.
- [ ] Add a central policy engine that decides allowed adapters, sandbox level, raw args, tools/MCP, output path, provider, data class, budget, and approval requirements.
- [ ] Add routing-policy tests that prove unknown adapters, disallowed providers, disallowed data classes, and unsupported capabilities are denied.
- [ ] Add transitive-permission tests proving a low-permission origin cannot launch a higher-permission target without explicit approval.
- [ ] Add graph-cycle tests covering routes such as Claude -> Codex -> Gemini -> Claude.
- [ ] Add concurrent/multi-target edit conflict tests with file-scope manifests.
- [ ] Add per-provider artifact redaction and data-egress receipts.
- [ ] Add rate-limit, quota, disk, runtime, and loop-stop tests for multi-target orchestration.
- [ ] Add run, route, user, workspace, provider, and daily budget enforcement tests.
- [ ] Add audit graph receipts with correlation id, route plan, policy decisions, approvals, data labels, prompt hashes, transformed prompt hashes, adapter versions, executable paths, tool/MCP visibility, costs, and final disposition.
- [ ] Add receipt digesting or tamper-evidence before claiming enterprise-grade auditability.
- [ ] Add adapter disable/revocation and incident-response docs.
- [ ] Add enterprise deployment controls: signed releases, pinned versions, SBOM, centrally managed policy, allowlisted binaries, proxy/egress support, SIEM-compatible audit export, retention/redaction policy, kill switch, and uninstall/disable path.
