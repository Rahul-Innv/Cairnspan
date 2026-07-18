# Origin Context

This document preserves the conversation context that led to Cairnspan.

## Starting Point

The work began while building a separate usage-aware overnight Codex runner. That tool was meant to let Codex see usage, stop near thresholds, resume safely, and produce morning reports for overnight work.

During that tool's testing, a related but distinct question emerged: if Claude Code is already available in VS Code, can it trigger Codex directly for work that Claude Code cannot do as well, such as Codex-specific skills, image generation, Codex MCP tools, Codex web search, or isolated Codex threads?

That question became the seed for Cairnspan.

## Why This Is Not An Overnight Runner

The overnight runner answers: can Codex run safely overnight with usage-aware stop, checkpoint, resume, and report behavior?

Cairnspan answers: can one local agent delegate a bounded task to another local agent through that target agent's own authenticated client, then preserve the request, logs, result, thread id, and return path?

The products can work together later, but they solve different problems.

## Core User Need

The user wants Claude Code and Codex to work together without pretending they are the same runtime.

Claude Code might have the active VS Code project context, Claude-specific skills, or existing developer workflow. Codex might have OpenAI-specific capabilities such as `$imagegen`, Codex MCP tools, Codex app/CLI behavior, web search, or different model/account access.

The desired workflow is not just model-to-model chat. It is practical local delegation:

1. One agent decides another agent is better suited for a bounded task.
2. It launches or prepares a handoff to that agent.
3. The target agent runs with its own tools, skills, auth, and sandbox.
4. The run produces durable evidence: command, prompt/request, logs, final response, thread/session id, return code, and blocker classification.
5. The origin agent reads the result and continues.

## The OAuth Insight

A key clarification was that API-key orchestration is already possible. If the only goal is to call OpenAI or Anthropic APIs, Cairnspan is not very differentiated.

The important idea is OAuth-backed local agent access.

Cairnspan should use the installed, authenticated local agent clients whenever possible. That means Codex should run as the user's Codex account/session, and Claude Code should run as the user's Claude Code session if a safe entrypoint exists.

This matters because the target agent may have account-scoped capabilities that an API key call does not automatically reproduce:

- included product limits or subscription behavior
- first-party tools such as Codex image generation
- configured MCP servers
- local skills and plugins
- workspace policy and approvals
- existing local auth/session state
- product-specific thread or project behavior

Cairnspan should not copy, expose, or broker OAuth tokens. It should launch the local authenticated client and record only observable run metadata.

## Two-Way Requirement

The user explicitly wanted this to work both ways:

- Claude Code should be able to launch Codex and inspect the result.
- Codex should be able to ask Claude Code for help or prepare a structured handoff back to Claude Code.

The first direction is implemented through `skills/cairnspan/scripts/start_codex_session.py`, which runs `codex exec --json` and writes structured artifacts. It has been live-verified from a Claude Code origin for basic text, read-only no-edit behavior, workspace-write sandbox scope, Codex MCP visibility, and built-in Codex image generation.

The second direction is implemented and live-verified. Claude Code exposes a noninteractive `claude -p` path, `start_claude_session.py` enforces strict MCP/no-tools/no-edit policy, and the parent-orchestrated Codex-to-Claude route has closed repeatedly with linked receipts. The shared-folder mailbox fallback has also completed a synthetic Codex-to-Claude-to-Codex round trip with parent-owned manifests.

## Naming History

The first prototype was called `claude-codex-bridge` because it started as a one-way Claude Code to Codex launcher.

It was then renamed conceptually to Agent Parley because the product was broader than Claude and Codex. After a direct GitHub/GitLab name check, `agent-parley` was rejected because GitHub already had public usage, including an existing `agent-parley` repo/org result.

The current name is Cairnspan.

`cairnspan` was selected because it names the core differentiator and returned no GitHub repository matches, no GitLab project matches, and no npm/PyPI package match in the checks performed on July 8, 2026.

The exact-name check was repeated against the official GitHub, GitLab, npm, and PyPI endpoints on July 10, 2026 with the same result. See `docs/name-check.md`; this is collision research, not trademark clearance or reservation.

## What Was Proven

The product folder now contains:

- a canonical Codex skill at `skills/cairnspan/SKILL.md`
- a Claude Code-facing shim at `.claude/skills/cairnspan/SKILL.md`
- a Codex launcher at `skills/cairnspan/scripts/start_codex_session.py`
- a Claude Code launcher at `skills/cairnspan/scripts/start_claude_session.py`
- a Claude Code launcher spec at `docs/claude-launcher.md`
- plan, learnings, verification, and preserved evidence

The skill validates, the Codex launcher test suite passes, live Claude Code to Codex probes pass across the current MVP capability set, and a no-tools Codex to Claude Code entrypoint probe returns `claude-cairnspan-ok`.

## Current Caveat

The default `codex` PATH entry still resolves to the Microsoft Store/WindowsApps package path, and unattended subprocess launch returns `Access is denied`.

Cairnspan classifies that as an environment blocker instead of crashing. Successful live Codex runs currently pass the explicit launchable Codex CLI path with `--codex-bin`.

## Product Principle

Cairnspan should always be honest about boundaries.

It should not claim that agents share tools, auth, context, approvals, or windows. It should make the handoff explicit, run the target agent through a verified entrypoint, capture proof, and tell the origin agent exactly what happened and what remains.
