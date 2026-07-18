---
name: cairnspan-route-critique
description: Prepare or close one text-only Codex-critique to Claude-synthesis route and return its validated receipt. Use for critique synthesis only, not for generic two-way routing or image artifact production.
---

# Cairnspan Route Critique

## Outcome

Return one validated text-only Codex-critique to Claude-synthesis route receipt.

## Trigger

Use when an existing Codex critique must be validated and handed to Claude for bounded text synthesis, or when existing hash-bound receipts must be closed into the exact route receipt.

Do not use for a static PNG, generic nonce exchange, or direct product integration.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Validate the exact Codex critique and snapshot manifest with `<CAIRNSPAN_RUNTIME_ROOT>/scripts/prepare_critique_handoff.py`.
2. Prepare the immutable route plan with `<CAIRNSPAN_RUNTIME_ROOT>/scripts/critique_route_receipt.py prepare`.
3. Keep any Codex or Claude live launcher edge behind its own provider gate.
4. Close only from the exact existing plan and hash-bound Claude receipts using `critique_route_receipt.py close`.
5. Return the validated route receipt or one exact blocker.

## Non-goals

Do not generate an image, perform a generic two-way route, infer missing receipts, launch a provider without exact authority, or publish/integrate the result.
