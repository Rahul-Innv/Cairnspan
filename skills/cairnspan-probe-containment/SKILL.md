---
name: cairnspan-probe-containment
description: Prepare or close exactly one typed hostile-workspace containment case while preserving separate execution and cleanup gates. Use for containment only, not capability qualification or destructive cleanup.
---

# Cairnspan Probe Containment

## Outcome

Prepare and close one typed hostile-workspace containment case while keeping execution and cleanup separately gated.

## Trigger

Use when the user wants to prepare one supported hostile case without executing it, or close one exact approved case from bounded receipts.

Do not use for image/tool capability qualification or deleting a disposable case workspace.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Select exactly one supported agent and hostile case, with fresh distinct dry/live receipt roots, a fresh case workspace, sibling sentinel, native executable, and version pin.
2. Use `<CAIRNSPAN_RUNTIME_ROOT>/scripts/hostile_write_case.py prepare`. The helper records commands but never launches a provider.
3. Keep the dry command and live execution behind the exact policy/provider gate; do not retry failures or weaken containment.
4. Close only with the exact approved plan SHA-256, approval reference, receipts, manifests, sentinel evidence, and typed launcher profile.
5. Return the closed result or exact blocker. Cleanup remains a separately authorized destructive action.

## Non-goals

Do not run cleanup, bypass DLP/sandbox/provider controls, use unsafe launcher variants, qualify a named image capability, read private data, or perform lifecycle, product, or publication work.
