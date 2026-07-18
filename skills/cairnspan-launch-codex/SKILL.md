---
name: cairnspan-launch-codex
description: Prepare or run exactly one bounded Codex launcher edge and return its receipt. Use for a single scoped Codex handoff; do not use for two-way routing, capability qualification, or unsafe launcher overrides.
---

# Cairnspan Launch Codex

## Outcome

Return the bounded receipt for exactly one scoped Codex edge; live execution requires exact provider authority.

## Trigger

Use when the user wants one bounded Codex handoff, including a dry-run command and receipt path or an already-authorized standard live edge.

Do not use for a two-agent route, a named capability qualification case, or a design-to-PNG closure.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Read the explicitly supplied owner-policy document when present and verify the exact target workspace, prompt, sandbox, output root, model/effort pair, native executable, and version pin.
2. Use `<CAIRNSPAN_RUNTIME_ROOT>/scripts/start_codex_session.py` with a prompt file and the least sandbox. Dry run first.
3. Require a fresh parent-controlled receipt directory outside any write-enabled target workspace.
4. Execute only with exact authority for this edge. Inspect `cairnspan-summary.json`, `events.jsonl`, `transcript.log`, and `final.md`.
5. Return the bounded receipt and exact blocker; do not translate a dry run into execution authority.

The shared CLI-version, hostile-write-policy, and workspace-manifest code remains internal implementation, not public skills.

## Non-goals

Do not expose raw argument passthrough, sensitive auth inheritance, shell wrappers, overwrite, `danger-full-access`, or other unsafe variants. Do not extract or replay credentials, run a second agent, install a skill, or perform publication or product work.
