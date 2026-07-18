---
name: cairnspan-route-artifact
description: Prepare and validate one bounded design-to-static-PNG handoff and return its typed route receipt. Use for one image artifact route; do not use for text critique or product integration, and require human visual attestation for closure.
---

# Cairnspan Route Artifact

## Outcome

Return one validated design-to-static-PNG handoff receipt; closure requires hash-bound human visual attestation.

## Trigger

Use when one bounded design specification must become one validated static PNG handoff, or when an existing handoff is ready for owner-attested closure.

Do not use for text-only critique/synthesis or copying an artifact into a product repository.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Validate the design specification and build the minimized generation prompt with `<CAIRNSPAN_RUNTIME_ROOT>/scripts/prepare_artifact_handoff.py`.
2. Keep Claude or Codex live generation behind the exact provider gate for that edge.
3. Validate one static PNG and its workspace deltas with `<CAIRNSPAN_RUNTIME_ROOT>/scripts/artifact_manifest.py`.
4. Ask the owner for the exact hash-bound visual decision. Never manufacture or infer it.
5. Close with `<CAIRNSPAN_RUNTIME_ROOT>/scripts/artifact_route_receipt.py` only from matching evidence and the owner's decision; return the receipt or exact blocker.

## Non-goals

Do not claim visual acceptance, integrate or copy the artifact into a product, generate multiple artifacts, bypass structural limits, or perform publication/lifecycle work.
