# Synthetic Capability Proposal Contract

Status: offline proposal preparation and parent-owned closure are implemented.
No prepared proposal authorizes its dry-run or execute command, and the helper
never launches Codex.

Execution authority is supplied separately by the active owner policy. Under
the owner's active standing approval policy, an exact bounded synthetic
public-data proposal may proceed without another owner message only when it
matches the policy envelope. This does not mutate the prepared
`approval_state=not-granted`; closure records the active standing approval
reference and the exact plan hash. Proposals outside that envelope stop for a
fresh owner decision.

`synthetic_probe_case.py` prepares one immutable, synthetic public-data Codex
proposal at a time for:

- `codex-effort`: native acceptance of the reviewed `gpt-5.6-sol` / `xhigh`
  typed request under strict no-tool isolation;
- `image-generation`: one required `$imagegen` tool event and one declared PNG
  in a fresh writable staging workspace;
- `image-view`: one required `view_image` tool event against a deterministic
  parent-created PNG in a read-only workspace.

Each schema `0.2` proposal has its own fresh case root, workspace, distinct
absent `dry-run-receipts` and live `receipts` roots, prompt, strict prepared
manifest, native executable path/version/SHA-256, bounded runtime and output
policy, zero retries, depth/fan-out 1, exact dry/live commands, and command
SHA-256 values. `approval_state` is always `not-granted` at preparation. The
parent helper performs only a bounded local `--version` probe and file hashing;
it does not authenticate or launch a model.

Schema `0.1` proposals used one receipt directory for both commands. A
successful dry run would make the live command reject that now-nonempty path.
Those preserved proposals are superseded and must not be run or rewritten.

Prepare one case:

```powershell
python skills\cairnspan\scripts\synthetic_probe_case.py prepare `
  --case-root "C:\path\to\fresh-proposal" `
  --probe codex-effort `
  --codex-bin "C:\absolute\path\to\codex.exe" `
  --expected-cli-version "<exact inspected version>"
```

Replace `codex-effort` with `image-generation` or `image-view` only to prepare a
separate case root. Inspect `proposal-plan.json`, its prompt/input, prepared
manifest, native identity, commands, and hashes. Do not run either stored
command until the active owner policy authorizes that exact proposal id, case
root, native executable identity, and command digest.

After the active owner policy authorizes that exact proposal, run its stored dry
command and live command without modification and with no retry. The separate
receipt roots prevent the dry receipt from weakening or blocking the live
receipt. Close only after both roots exist:

```powershell
python skills\cairnspan\scripts\synthetic_probe_case.py close `
  --case-root "C:\path\to\prepared-proposal" `
  --approval-reference "<owner-decision-reference>" `
  --approved-plan-sha256 "<exact-proposal-plan-sha256>"
```

The approval reference is an operator-supplied attestation, not independently
verifiable proof of human intent. The approved plan SHA-256 prevents that
attestation from being replayed after plan mutation. The closer rechecks the immutable marker,
plan, prompt, prepared manifest, native binary hash/version, exact dry/live
commands, separate receipt roots, and launcher-command digests. It independently
parses the live JSONL, requires one terminal thread, strong Windows containment,
verified cleanup, exact final markers, and strict workspace deltas. It rejects
extra receipts, plan or binary drift, missing tool events, no-edit mutations,
and repeated closure.

Downstream consumers must re-verify rather than trust a stored closure:

```powershell
python skills\cairnspan\scripts\synthetic_probe_case.py verify `
  --case-root "C:\path\to\closed-proposal"
```

Verification replays plan, native identity, dry/live receipts, JSONL, workspace,
artifact, and closure claims and rejects any post-closure drift.

The typed-effort probe can establish that the pinned native CLI accepted the
launcher-owned `model_reasoning_effort` mapping and completed the exact bounded
task. Its Cairnspan request receipt still does not prove the provider honored
the requested model or effort. Record independent provider-observed usage only
if the native client exposes it; otherwise keep that claim unknown.

Image-generation and image-view are distinct gates. Native image attachment is
not a substitute for either tool event. Each approved run needs fresh receipts,
one terminal identity, `job-object` containment, verified descendant cleanup,
the required capability result, and an exact workspace delta. Generation also
requires parent validation of the declared PNG before any visual approval.
The closer performs bounded static-PNG validation and records the artifact hash;
it does not grant visual approval or authorize integration.

These proposals do not authorize the existing hostile-write case, private
source reads or provider work, product data/repository access, the three-item image
pilot, integration, installation, authentication changes, commits, pushes,
deployment, publication, or remote visibility changes.

## Current Typed-Effort Evidence

The schema `0.2` `codex-effort` proposal
`e0ffb104618d4c8aa0246702b68ceb4f` closed on 2026-07-12 under the owner's active
standing approval reference and independently verified.
The plan SHA-256 is
`5c126205ed3e55d0a97ca41dd3a0fa6c3bfa983bd8fc006665e53a3c6d41f9c8`;
the closure SHA-256 is
`e9df8bb864a05a197e6fb8270170b54f863108efeab28eb951ae13354572e939`.
The pinned native `codex-cli 0.144.0-alpha.4` accepted the requested
`gpt-5.6-sol` / `xhigh` typed pair, returned the exact marker with zero tools,
and changed no workspace paths. The receipt does not independently establish
provider honoring, so that claim remains `unknown`. This evidence does not
authorize any downstream program phase.
