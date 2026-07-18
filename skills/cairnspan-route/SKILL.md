---
name: cairnspan-route
description: Select exactly one implemented Cairnspan leaf for a bounded cross-agent task and report its gate without launching anything. Use for route choice only, not for executing an edge or diagnosing local setup.
---

# Cairnspan Route

## Outcome

Recommend exactly one implemented Cairnspan leaf and return its required gate without launching.

## Trigger

Use this candidate when the user asks which Cairnspan path should own a bounded handoff, launch, route, probe, readiness check, or release qualification.

Do not use it when the request already names one exact atomic outcome. Route directly to that leaf instead.

ChoiceGate is the only selection authority. The ten entries below are advisory `routes_to` targets, not runtime dependencies: this selector must not invoke, delegate to, or execute a leaf. A directly named atomic outcome bypasses this router.

## Selection contract

- One Codex edge: `cairnspan-launch-codex`.
- One Claude Code edge: `cairnspan-launch-claude`.
- One selected-order two-edge nonce route: `cairnspan-run-two-way`.
- Text critique then synthesis: `cairnspan-route-critique`.
- Design specification to one static PNG handoff: `cairnspan-route-artifact`.
- Immutable request/response folder exchange: `cairnspan-route-mailbox`.
- Local executable and workspace diagnosis: `cairnspan-check-readiness`.
- One named Codex capability case: `cairnspan-probe-capability`.
- One hostile-workspace containment case: `cairnspan-probe-containment`.
- One non-publishing source, public-alpha, or production verdict: `cairnspan-qualify-release`.

If the request spans outcomes, is ambiguous between two leaves, asks for an unimplemented route, or crosses a closed exclusion, fail closed and ask for one exact outcome or authority. Never infer provider, lifecycle, publication, export, cleanup, or product-integration authority.

## Non-goals

Do not execute, install, enable, publish, export, clean up, integrate an artifact, choose credentials, or claim that an inactive candidate is active. The broad `cairnspan` skill remains the active compatibility surface until the owner authorizes a later cutover.
