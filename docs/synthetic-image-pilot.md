# Finite Synthetic Image Pilot

Status: deterministic prepare, execute, fail-stop, and verify control is
implemented. No real batch is eligible until the separately approved schema
`0.2` image-generation and image-view proposals both close and independently
re-verify. The current real preparation attempt failed before creating a batch
root or daily ledger because those closures are absent.

## Contract

The first pilot is exactly three immutable synthetic public-data items:

1. `paper-boat`;
2. `geometric-sunrise`;
3. `green-leaf`.

Every item has its own schema `0.2` image-generation proposal, fresh workspace,
separate dry/live receipt roots, prompt hash, exact output path, native identity,
command hashes, and parent closure. The batch freezes:

- item count 3 and exact order;
- concurrency 1;
- automatic retries 0;
- no resume or second execution;
- per-item 420-second and 1 MiB launcher ceilings;
- 1,260-3,600 second aggregate runtime ceiling;
- bounded aggregate receipt output and disk ceilings;
- a global UTC-day usage ledger with an exact three-attempt ceiling;
- 1-720 hour private retention policy;
- fail-stop before every later item after any error;
- `product_integration=not-authorized` in the plan and `not-run` in results.

## Preparation

Preparation first re-verifies both individual capability closures, including
their plans, native executable identity, JSONL, tool events, workspace deltas,
artifacts, and closure claims. Both closures must bind the same native Codex
binary/version/hash.

```powershell
python skills\cairnspan\scripts\synthetic_image_pilot.py prepare `
  --batch-root "C:\path\to\fresh-batch" `
  --image-generation-case-root "C:\path\to\closed-image-generation-case" `
  --image-view-case-root "C:\path\to\closed-image-view-case" `
  --daily-ledger "C:\path\to\parent-controlled-daily-ledger.json"
```

Preparation never launches a provider. It leaves every item receipt root absent
and writes `approval_state=not-granted`.

## Execution

Execution requires both an operator-supplied approval reference and the exact
approved `batch-plan.json` SHA-256. The reference is an attestation, not
independent proof of human identity. The plan hash prevents approval for one
plan from being replayed after plan mutation.

```powershell
python skills\cairnspan\scripts\synthetic_image_pilot.py execute `
  --batch-root "C:\path\to\prepared-batch" `
  --approval-reference "<owner-decision-reference>" `
  --approved-plan-sha256 "<exact-batch-plan-sha256>"
```

Before each item the controller checks aggregate wall time and disk, atomically
reserves one daily usage event under a cross-process lock, and records state.
It then runs the exact dry command, exact live command, item closer, and closure
verifier. Any exception, nonzero launcher result, capability failure,
containment/cleanup failure, unexpected file, artifact rejection, receipt
tampering, output/disk/runtime ceiling, or ledger denial terminates the batch.
There is no skip, fallback, retry, or resume path.

## Verification

```powershell
python skills\cairnspan\scripts\synthetic_image_pilot.py verify `
  --batch-root "C:\path\to\terminal-batch"
```

Verification recomputes the batch plan/state/result links, approval-plan hash,
declared-prefix ordering, aggregate fields, daily ledger events, and every
completed item closure/artifact hash. For a failed batch it rejects any dry,
live, closure, or after-manifest evidence for a later item. For a successful
batch it requires all three exact closures and retains product integration as
`not-run`.

The pilot does not authorize product data, a product-specific batch, visual
approval, integration, scheduling, a larger batch, concurrency growth, retries,
API fallback, publication, or deployment.
