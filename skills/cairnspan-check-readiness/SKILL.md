---
name: cairnspan-check-readiness
description: Diagnose local Cairnspan executable, workspace, and output readiness without launching a provider. Use for setup checks only; do not use for release qualification or live capability probes.
---

# Cairnspan Check Readiness

## Outcome

Diagnose local Cairnspan setup readiness without launching a provider edge.

## Trigger

Use when the user asks whether the machine, Codex/Claude executable, target workspace, or output root is ready for Cairnspan.

Do not use for source/public-alpha/production release readiness or a live capability qualification.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Run `<CAIRNSPAN_RUNTIME_ROOT>/scripts/doctor.py` against the exact target workspace and optional output root.
2. Use bounded, credential-scrubbed native CLI version probes. Do not request login or inspect tokens.
3. Report each check, the observed safe metadata, and the precise local remediation.
4. Stop before any provider launch, installation, authentication change, or lifecycle action.

The CLI-version probe is an internal primitive, not a public skill.

## Non-goals

Do not execute a live probe, evaluate repository release profiles, install software, change PATH/authentication, or claim that setup readiness proves provider capability.
