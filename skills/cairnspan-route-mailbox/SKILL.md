---
name: cairnspan-route-mailbox
description: Validate and close exactly one immutable file-mailbox request and response exchange. Use for a shared-folder mailbox route with existing files and receipts; do not use for a live launcher or autonomous queue.
---

# Cairnspan Route Mailbox

## Outcome

Validate and close one immutable file-mailbox request and response exchange.

## Trigger

Use when the user has one Cairnspan mailbox request and response pair to validate or one existing Codex-to-Claude-to-Codex shared-folder exchange to close.

Do not use to launch a provider or treat a folder as a trusted autonomous queue.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Validate the request and response schemas and their immutable linkage with `<CAIRNSPAN_RUNTIME_ROOT>/scripts/mailbox.py`.
2. Verify the exact mailbox directory, prompt hashes, identities, markers, and before/after manifests.
3. Close with `<CAIRNSPAN_RUNTIME_ROOT>/scripts/mailbox_route_receipt.py` only from the complete existing edge receipts.
4. Return the closure receipt or one exact missing/mismatched field.

## Non-goals

Do not launch Codex or Claude, poll indefinitely, mutate request/response files, infer identity, retry a provider edge, or perform external writes, cleanup, lifecycle, or publication.
