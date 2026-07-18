---
name: cairnspan-run-two-way
description: Prepare or run one bounded two-edge Codex and Claude nonce route in exactly one selected order. Use for two-way closure only; do not use for a single edge, critique synthesis, or transferring approval between route orders.
---

# Cairnspan Run Two Way

## Outcome

Return one bounded two-edge nonce-route receipt for exactly one selected order, without transferring authority between orders.

## Trigger

Use when the user requests the bounded two-agent text closure with aggregate limits, fresh workspaces, and one explicit route order.

Do not use for one launcher edge, critique/synthesis routing, or an artifact route.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Confirm two fresh, non-overlapping disposable workspaces, two distinct fresh parent-controlled receipt roots (`<DRY_RUN_ROOT>` and `<EXECUTION_ROOT>`), explicit native executables, version pins, aggregate time/output/cost ceilings, and one route order. Neither receipt root may already exist.
2. Use `<CAIRNSPAN_RUNTIME_ROOT>/scripts/run_two_way_route.py --out-dir <DRY_RUN_ROOT> --dry-run` first. Treat its route ID, nonce, plan, and receipts only as a non-binding configuration rehearsal; they do not authorize or identify a later execution.
3. Treat Codex-first and Claude-first live execution as distinct gates. Authority for one order never authorizes the other.
4. Execute only with exact provider authority for the selected order, using `<CAIRNSPAN_RUNTIME_ROOT>/scripts/run_two_way_route.py --out-dir <EXECUTION_ROOT> --execute`. Execution must create a new route ID, nonce, and plan in the distinct fresh root and independently revalidate executable versions, workspace policy, manifests, and route limits.
5. Preserve the rehearsal receipt separately from both execution edge receipts and the parent closure. Never reuse either root for another invocation.
6. Return one execution route receipt or one exact fail-closed blocker; a dry-run receipt alone is never a live execution receipt.

## Non-goals

Do not use test shell wrappers or unsafe overrides, recurse from one child into the next, retry a failed edge, route images/binaries, add a third agent, or transfer authority between orders. Do not perform cleanup, lifecycle, publication, or product integration.
