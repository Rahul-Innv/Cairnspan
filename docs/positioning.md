# Cairnspan Positioning

Drafted: 2026-07-11.

> **Stress-tested same day against online evidence** — see
> `docs/positioning-stress-test.md`. Verdict summary: the "provable
> delegation" differentiator and the enterprise governance ladder survive
> and are strengthened; the "use your existing subscriptions" hook remains
> unsuitable for public positioning because provider terms and billing can
> change, while bare "cross-vendor delegation" is commoditized
> (PAL/clink 11.7k stars, Claude Code Router 35.7k stars). Frames 1-3 below
> stand; frame 4 must not be used publicly until the provider-policy question
> is cleared for the intended distribution model; the wedge language needs the rework listed in the stress-test
> doc.

This document is the canonical "why / what / against whom" narrative. It
consolidates the product thesis from `docs/plan.md`, the origin story from
`docs/origin-context.md`, the core-position section of
`docs/strengthening-plan.md`, and the competitive findings in
`docs/cursor-perplexity-cross-analysis.md`, then organizes everything by the
vision instead of by build order.

Claims here follow the same rule as everywhere else in the repo: public copy
may only use a claim after its proof gate in `docs/strengthening-plan.md` and
`docs/verification.md` passes.

## The Vision Stack

Everything in the project fits one five-layer stack. Read it top-down for
"why", bottom-up for "how".

| Layer | Statement | Where it lives today |
| --- | --- | --- |
| 1. Vision | Governed multi-agent interaction: route each bounded task to the agent best suited for it, and bring the result back with proof. | `docs/plan.md` product thesis |
| 2. Wedge | OAuth-backed local clients: the user's installed, logged-in agents carry account-scoped capabilities (skills, MCP, imagegen, quotas, workspace policy) that raw API keys do not reproduce. | `docs/origin-context.md` OAuth insight |
| 3. Moat | The receipt and closure contract: fail-closed launchers, scoped sandboxes, containment, strict manifests, prompt hashing, exact-artifact closure, adversarially reviewed. | Launchers, `docs/two-way-loop.md`, `docs/artifact-route.md`, `docs/reviews/` |
| 4. Surface | Portable skills and adapters: one adapter contract per target agent, host-neutral skill packaging, doctor/install paths. | `skills/cairnspan/`, `docs/install-skill.md`, adapter plan |
| 5. Governance ladder | Policy engine, data classification, provider boundaries, enterprise audit. | `docs/strengthening-plan.md`, `docs/threat-model.md` |

The important structural insight: **layers are not equally defensible.**

- Layer 4 (skills, launching a CLI) is commoditized. Claude Code can already
  run `codex exec` through its Bash tool with zero product needed. Cursor
  imports skills from GitHub. The skill is packaging, not product.
- Layer 2 (the wedge) is real but erodes at the edges as clients converge on
  features (Cursor now has image generation too).
- Layer 3 (the moat) is the part nobody else builds: a hardened, fail-closed,
  receipt-backed handoff that survived a 28-subagent adversarial review and
  fixed every confirmed P1/P2. Ad-hoc delegation cannot answer "prove the
  target didn't forge its own success," "prove the workspace is unchanged,"
  or "prove no descendant survived." Cairnspan can.

Positioning should therefore lead with proof, sell with capability, and treat
the skill/launcher mechanics as table stakes.

## What Cairnspan Actually Is

Three separable things get conflated as "the skill":

1. **Delegation mechanics** — launching Codex or Claude Code noninteractively.
   Commodity. Anyone with a Bash tool has this.
2. **Capability routing** — using each agent's account-scoped strengths
   (Codex `$imagegen` and MCP set, Claude Code project context and skills,
   future Cursor/Gemini strengths) through the user's existing logins. The
   wedge; the reason to delegate at all.
3. **Governed verification** — route plans, scoped sandboxes, strict tool/MCP
   denial, containment, before/after manifests, bounded cost/runtime/output,
   forgery-resistant receipts, exact-artifact closure. The moat; the reason
   this is a product and not a shell alias.

## Landscape: Who Does What

Short answer for the two named products: **neither Cursor nor Perplexity does
what Cairnspan does.** Cursor overlaps as an agent host and is
simultaneously the closest strategic competitor and the best next adapter.
Perplexity is adjacent tooling. The full dated analysis is in
`docs/cursor-perplexity-cross-analysis.md`; the summary and the rest of the
field follow.

| Player / category | What it is | Does layer 1 mechanics? | Does layer 2 (local-account capability reuse)? | Does layer 3 (receipts/governance)? | Posture for Cairnspan |
| --- | --- | --- | --- | --- | --- |
| Cursor | AI coding workspace: agents, skills, MCP, headless CLI, browser, imagegen, cloud agents | Partially (its own agent, headless CLI) | Only for itself; it does not launch other vendors' logged-in clients | Checkpoints/tool logs, not cross-app route receipts, manifests, or closure | Closest competitor AND top third-adapter candidate |
| Perplexity | Research/search/API platform + Comet browser assistant | No local coding-agent launching | API-key developer path; outside the OAuth-backed thesis | Usage/cost/citations on API responses only | Optional research tool inside routes, behind an explicit API-key-backed-tool policy |
| DIY delegation (PAL MCP Server's clink [11.7k stars] spawning Gemini/Codex/Claude CLIs, Claude Code Bash -> `codex exec`, codex-as-MCP wrappers) | The nearest real substitute — verified shipped and popular | Yes — clink is exactly layer 1, cross-vendor, using each CLI's installed auth | Partially (uses the local client; CCR-style routers are API-key based) | None — clink launches targets with `--yolo` / `--dangerously-bypass-approvals-and-sandbox` / `acceptEdits`; no receipts, manifests, containment, or verification | The thing to position against: "the delegation you already do, minus the bypass flags, plus proof" |
| Claude Code Router (35.7k stars) | Local proxy routing Claude Code/Codex requests across ~12 model providers | Model-API routing, not agent delegation | No — API keys, not installed clients | Dashboard/request logs/usage stats only | Kills any "cross-vendor is novel" claim at the model layer; no governance overlap |
| MCP | Tool protocol: how an agent exposes/consumes tools | No (tools, not agent handoffs) | No | No | Complementary; Cairnspan constrains and records MCP exposure per edge |
| A2A-style agent-interop protocols | Network protocols for hosted agent-to-agent tasks | Server-oriented, not local-process | No; assumes hosted agents, not installed logged-in clients | Message schemas, not local workspace/containment evidence | Conceptual neighbor; Cairnspan is "local-first A2A with proof" |
| API routers (OpenRouter, LiteLLM, etc.) | Multi-provider model routing over API keys | No | No — explicitly the opposite of the wedge | Usage metering only | Out of scope by thesis; do not drift here |
| Agent frameworks (LangGraph, CrewAI, AutoGen) | Build-your-own multi-agent apps on raw APIs | You build it yourself | No — you construct agents rather than reuse installed products | Whatever you build | Different buyer; Cairnspan reuses products, frameworks build them |
| Single-vendor cloud agents (Codex cloud, Claude Code web, Cursor cloud agents, Copilot coding agent) | Hosted execution surfaces per vendor | Within one vendor only | Vendor's own account only | Vendor-internal logs | Reinforces the need for a cross-vendor handoff layer with receipts |
| Hermes / OpenClaw (per `docs/strengthening-plan.md`) | Agent runtimes / control planes | Runtime-centric | Unvalidated | Unvalidated | Keep claims in research until checked against current docs, dated |

Reading of the table: **many players do layer 1, several own a slice of
layer 2 for themselves, and nobody does layer 3 across vendors.** That empty
column is the category.

## Positioning Frames

Five candidate frames, with what each buys and costs. The current public
one-liner ("Let the right AI agent handle the right subtask, without sharing
keys or running another server") is frame 4 with a hint of 1.

### Frame 1: Provable delegation (recommended lead)

> Your AI agents can already call each other. Cairnspan makes the handoff
> provable.

- Category: delegation with receipts. The route plan is a work order; the
  receipt is proof of delivery; closure is the acceptance test.
- Survives the two biggest threats named in the cross-analysis: Cursor
  absorbing workflows (Cursor still cannot notarize a cross-vendor handoff)
  and skill-install commoditization (the moat was never the skill).
- Evidence already exists: the adversarial review, forgery-resistant receipt
  fixes, manifests, Job Object containment, exact-nonce closures.
- Cost: "audit" is a colder first touch than "capability." Fix by pairing
  with frame 4 as the hook.

### Frame 2: Vendor-boundary governance (enterprise ladder)

> Every cross-agent handoff is a data egress event across a vendor boundary.
> Cairnspan is the checkpoint: policy in, receipts out.

- Speaks to data classification, provider boundaries, prompt minimization,
  approval gates — all already specified in `docs/strengthening-plan.md`.
- Validated from live experience: an execution environment's DLP policy
  blocked a product-shaped edge; Cairnspan's
  classification gates are the productized version of exactly that control.
- Cost: enterprise claims are gated behind Phase 2+ tests; this frame is the
  ladder, not the launch copy.

### Frame 3: The subcontract (demo narrative)

> One agent writes a bounded work order. Another agent, with its own login
> and its own tools, does the job in a sealed room. The parent checks the
> work against the order before accepting it.

- Human metaphor that makes route plan / sandbox / manifest / closure legible
  to non-experts in one breath. Best for demos and README storytelling.
- Cost: metaphor, not category; use inside copy, not as the category name.

### Frame 4: Capability arbitrage on subscriptions you already pay for (hook)

> Use every AI agent you already pay for — Claude, Codex, Cursor, Gemini —
> each doing what it is uniquely good at, from wherever you work, without
> sharing keys or running another server.

- The strongest first-touch value statement; matches the origin story
  (Claude Code wanting Codex `$imagegen`).
- Cost: sounds like a model router if left alone, and erodes as clients
  converge on features. Never let this frame stand without frame 1 attached.
- **2026-07-11 primary-source refresh: do not use this frame publicly.**
  Anthropic explicitly documents `claude -p` for scripts and CI and documents
  subscription OAuth for its official CLI. It separately prohibits offering
  Claude.ai login or routing plan credentials on behalf of users and recommends
  API-key authentication for products and services. Cairnspan's owner-local,
  official-client path avoids credential handling, but Anthropic has not
  specifically approved this product. Keep "use your subscriptions" out of
  public copy and require a fresh provider-policy review before release.

### Frame 5: Local-first A2A (standards-adjacent, hold in reserve)

> The agent-to-agent handshake for local clients: no server, no token broker,
> receipts included.

- The adapter contract could become a de facto local handoff contract; this
  frame claims that ambition.
- Cost: protocol positioning invites standardization comparisons and
  overpromises while there are only two verified adapters. Revisit after a
  third adapter passes the contract.

### Recommended composition

Hook with frame 4, differentiate with frame 1, ladder to frame 2:

> Use every AI agent you already pay for, each doing what it is best at —
> no shared keys, no extra server — and get a receipt that proves exactly
> what happened.

One-word category candidates, in preference order: **provable delegation**,
governed handoffs, delegation with receipts.

### Naming note

"Cairnspan" names the mechanism (the wedge), not the value. Keep the name;
translate in copy. Public-facing text should say "your already-logged-in
agents" / "your existing logins," not "OAuth," which reads as a developer
protocol detail and undersells layers 1 and 3.

## What Cairnspan Is Not (unchanged, restated)

- Not an IDE or coding workspace (Cursor's category).
- Not a research/citation engine or multi-provider API gateway (Perplexity's
  and OpenRouter's categories).
- Not an agent framework or runtime (LangGraph/CrewAI/Hermes territory).
- Not a token broker: it never copies, stores, or exposes OAuth tokens.
- Not a hosted service: no Cairnspan daemon, server, or database for the core
  handoff — while still consuming target-agent subscription, provider
  network, and local machine resources.

## Doc Map By Vision Layer

How the existing docs organize under the stack, and the gaps.

| Layer | Docs | Gap |
| --- | --- | --- |
| 1. Vision | `docs/plan.md` (thesis), `docs/origin-context.md` (story) | Was spread across four docs; this file is now the single narrative |
| 2. Wedge | `docs/origin-context.md` (OAuth insight), `docs/token-audit.md` | None significant |
| 3. Moat | `docs/two-way-loop.md`, `docs/artifact-route.md`, `docs/mailbox.md`, `docs/claude-launcher.md`, `docs/threat-model.md`, `docs/reviews/`, `docs/verification.md`, `docs/learnings.md` | POSIX entirely unproven; pressure matrix and behavioral injection probes still open |
| 4. Surface | `skills/cairnspan/SKILL.md`, `docs/install-skill.md`, `docs/live-test-runbook.md`, `docs/safety-checklist.md` | Adapter contract not yet drafted; Cursor feasibility spike not run |
| 5. Governance | `docs/strengthening-plan.md` (enterprise controls, claim ladder), `docs/threat-model.md` | Policy engine, route-plan schema, data-classification fields all Phase 2 |

## Claim Discipline For This Positioning

Every frame above must respect current verified reality:

- Two verified adapters (Codex, Claude Code), Windows only, private alpha.
- The bounded two-agent text, mailbox, and typed-artifact routes are
  live-verified; the broader crash/quota/rate-limit/canary matrix is not.
- "Provable" means the specific closure contract in `docs/two-way-loop.md`
  and `docs/artifact-route.md`, with the trust assumptions named in the
  2026-07-10 review (trusted skill directory, trusted single closer, human
  attestation flags) — not cryptographic attestation. Receipt signing and
  digest chaining remain pre-enterprise gates.
- Frame 4's "every AI agent you already pay for" is aspiration copy; the
  honest present-tense version is "Claude Code and Codex, with Cursor and
  Gemini as the next candidates."
