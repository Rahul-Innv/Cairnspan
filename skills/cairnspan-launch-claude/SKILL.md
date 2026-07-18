---
name: cairnspan-launch-claude
description: Prepare or run exactly one bounded Claude Code launcher edge and return its receipt. Use for a single scoped Claude handoff; do not use for Codex, two-way routing, mailbox exchange, or unsafe launcher overrides.
---

# Cairnspan Launch Claude

## Outcome

Return the bounded receipt for exactly one scoped Claude Code edge; live execution requires exact provider authority.

## Trigger

Use when the user wants one bounded Claude Code handoff, especially with strict MCP isolation, disabled tools, and a fresh receipt root.

Do not use for a Codex edge, a two-agent route, or a shared-folder mailbox exchange.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Read the explicitly supplied owner-policy document when present and verify the exact target workspace, prompt, permission mode, tool/MCP isolation, output root, budget, model/effort pair, executable, and version pin.
2. Use `<CAIRNSPAN_RUNTIME_ROOT>/scripts/start_claude_session.py` with a prompt file, safe mode, empty tools, strict MCP isolation, and no session persistence. Dry run first.
3. Require a fresh parent-controlled receipt directory outside any write-enabled target workspace.
4. Execute only with exact authority for this edge. Inspect the summary, transcript, final response, and session evidence.
5. Return the bounded receipt and exact blocker; do not translate a dry run into execution authority.

The shared CLI-version, hostile-write-policy, and workspace-manifest code remains internal implementation, not public skills.

## Non-goals

Do not enable customizations, configured MCP, broad tools, raw arguments, sensitive auth inheritance, shell wrappers, overwrite, persistence, or bypass permissions. Do not broker authentication, launch Codex, or perform lifecycle or publication work.
