# Two-Way Loop Contract

The first full loop is a bounded, parent-orchestrated round trip. It does not let a target model recursively launch the next target.

Status: implemented and live-verified on 2026-07-10 for the Codex-to-Claude
text route. The parent harness now also has deterministic fake-target coverage
for `--route-order claude-first`, including success, first-edge rate-limit, and
first-edge crash denial. Claude-first has not been live-run. Neither order
proves write-capable artifact routing, repeated load, or three-agent
orchestration.

## Why

A target-launched child can reset caller-supplied depth fields, consume unbounded aggregate quota, and write or forge receipts that live inside its writable workspace. A trusted parent process can enforce route-wide limits, keep receipts outside both target workspaces, and prove that one target's artifact became the next target's input.

This remains launch-and-exit local tooling. It does not add a daemon, server, token broker, or hosted control plane.

## Route

```text
trusted origin/harness
  -> Codex edge (read-only, nonce challenge)
  -> consume and verify Codex final artifact
  -> Claude Code edge (safe-mode, strict MCP, no tools, verified Codex artifact as input)
  -> consume and verify Claude final artifact
  -> closure receipt
```

The reverse ordering is selected explicitly with `--route-order claude-first`.
It uses the same parent-owned plan, exact linked artifacts, native version
pins, no-tool policies, aggregate limits, manifests, and closure checks. Its
deterministic suite passes; live-provider evidence remains owner-gated.

Typed model/effort selection is an edge contract, not permission to let either
target select or rewrite the next edge. Direct Codex and Claude launchers now
record `requested_model` and `requested_effort`; accepted effort values are
fixed to `low`, `medium`, `high`, `xhigh`, and `max`. A parent using these pins
must freeze them in its plan and validate each child summary. The existing
nonce route does not yet advertise route-level effort switches, so its closure
must not be cited as proof of any specific model/effort pair.

## Challenge Contract

The harness generates an unpredictable nonce locally.

- Codex must return exactly `cairnspan-codex:<nonce>`.
- The harness verifies that exact value before starting Claude Code.
- Claude Code receives the verified Codex value and must return exactly `cairnspan-closed:<nonce>`.
- The closure receipt stores hashes of both prompts and both final artifacts, not raw prompt bodies.

Any mismatch stops the route. No retry occurs in the first live test.

## Required Route Policy

- exactly two target edges;
- allowed targets: Codex, then Claude Code;
- max depth: 1 at the route layer, with no target-initiated child launch;
- max fan-out: 1;
- retry budget: 0;
- explicit per-edge timeouts and output limits;
- explicit Claude `--max-budget-usd` and an aggregate route ceiling;
- Codex read-only sandbox, strict config isolation, ignored user/project rules, ephemeral state, disabled apps/plugins/tool features, and a no-tool-use assertion;
- Claude safe mode, strict MCP, no tools, and no session persistence;
- sensitive auth/provider environment overrides scrubbed;
- native absolute executables, not PATH-selected shell wrappers;
- target workspaces disposable and secret-free;
- receipts and route state stored in a parent-controlled directory outside both target workspaces;
- origin-side before/after manifests for both target workspaces.

## Pass Criteria

- both edge summaries succeed with recognized terminal events and session/thread ids;
- both exact nonce responses match;
- the second prompt hash is derived from the verified first final artifact;
- no tool or MCP event appears on the Claude edge;
- both before/after manifests are identical;
- exactly two target edges ran and no descendant survived normal exit, timeout, or output-limit handling;
- aggregate elapsed time, output bytes, and recorded Claude cost remain within route policy;
- the closure receipt includes parent route id, child run ids, executable paths, policy values, artifact hashes, and final disposition.

## Verified Implementation

`scripts/run_two_way_route.py` implements the route as a stdlib parent harness. Fake-target tests cover successful closure, dry-run, nonce mismatch, first- and second-edge failure, route timeout, per-edge output overflow, aggregate budget denial, stale route-root reuse, Codex tool use, and strict hidden-path workspace mutation.

The first successful live route closed in 27.375 seconds. Both edges returned recognized terminal events and one target identity, the nonce matched across exact Codex and Claude artifacts, tool/MCP counts were zero, both strict manifests were identical, executable identities remained stable, no descendants survived, and every final/summary hash in `closure.json` matched the referenced file. Claude reported `$0.019557`; Codex did not expose a comparable cost, so the aggregate receipt records that edge as unreported.

Two issues were found and fixed during live pressure:

- Historical Windows descendant PIDs were incorrectly combined with the authoritative Job Object list, allowing PID reuse to create false process-leak failures. The launchers now use the Job Object list whenever available and have dedicated recycled-PID regression tests.
- Claude rejected wording that described the nonce as a trusted verification handshake. The second edge now receives a plain, deterministic string transformation over an already validated artifact; the parent still enforces the exact closure value.

Target-recursive nesting remains an explicitly unsafe future pressure topology. Fresh repetitions now pass and non-disposable hostile baselines are denied before launch; Claude-first full routing, deliberate native target crashes, quota/rate-limit behavior, and live canary egress probes remain open pressure work.
