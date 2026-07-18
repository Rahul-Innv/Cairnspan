---
name: cairnspan-probe-capability
description: Prepare, close, or verify exactly one named Codex capability case and return its independent receipt. Use for codex-effort, image-generation, or image-view only; do not use for containment or the three-item pilot.
---

# Cairnspan Probe Capability

## Outcome

Qualify exactly one named capability unit and return its independently verified receipt.

## Trigger

Use when the user wants to prepare one immutable named capability case, close one exact approved case from receipts, or independently verify one closed case.

Do not use for hostile-workspace containment, generic Codex use, MCP visibility without a separately qualified typed case, or the three-item image pilot.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Select exactly one supported probe kind and a fresh case root.
2. Use `<CAIRNSPAN_RUNTIME_ROOT>/scripts/synthetic_probe_case.py prepare` with a pinned native Codex executable and exact CLI version. Preparation never launches Codex.
3. Keep the dry command, live command, and live provider execution behind their exact policy and provider gates; never retry a failed command.
4. Close only with the exact approved plan SHA-256, approval reference, and hash-bound receipts.
5. Run the independent `verify` action and return that one receipt or exact fail-closed blocker.

## Non-goals

Do not execute or aggregate the three-item pilot, infer approval from preparation, test containment, support untyped MCP visibility, use private/product data, or change product phases, ledgers, budgets, routing, authentication, lifecycle, or publication.
