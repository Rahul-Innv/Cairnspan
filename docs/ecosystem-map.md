# The Agentic AI Ecosystem Map

Research date: 2026-07-11.

Method: 9 parallel layer sweeps (web research with primary-source preference),
3 cross-examiners spot-checking load-bearing dates/numbers/quotes, 3 strategist
syntheses (value chain, scenarios, Cairnspan fit). 15 agents total. Corrections
from cross-examination are folded in and flagged. This document is the
end-to-end map; the Cairnspan-specific verdicts live in
`docs/positioning-stress-test.md` and provider compliance detail in the
2026-07-11 ecosystem stress-test results.

Reliability: marquee facts verified against primary/near-primary sources.
Known soft spots — the Meta/Manus acquisition is reported-not-fully-confirmed
despite press dating (2025-12-29, ~$2B); Claude Code ARR figures conflict
($2.5B Anthropic-stated Feb 2026 vs ~$8B aggregator-claimed May 2026); Codex
WAU is vendor-self-reported (3M Apr → 5M+ Jun); Omnigent's "30k stars" is
unverified marketing; Cognition's valuation is $26B after its 2026 Series D
(older $25B figure is stale). Treat all star counts as point-in-time.

## Executive Summary

Agents, not chat, are now the product — every frontier lab has converged on
that thesis while diverging sharply on distribution. The strategically
decisive fact of mid-2026: **power has bifurcated into a model layer
(Anthropic, OpenAI, Chinese open-weight labs) and a distribution/governance
layer (Microsoft/GitHub, Amazon/AWS, cloud identity vendors) — and the same
firm rarely holds both.** Margin pools at vertically-integrated
model-plus-harness bundles and at enterprise seats/identity; the harness
itself and the raw token are commoditizing fastest. Chinese open-weight
models now supply ~51-61% of OpenRouter token volume (from <2% in late
2024). Because no unforgeable action-attestation standard has shipped,
"agent governance" in practice collapses to whoever issues and scopes the
credential — which is why identity vendors are winning the governance land
grab by default, and why the local agent-to-agent handoff seam (Cairnspan's
cell) remains genuinely unoccupied.

## The Value Chain

Ten links, bottom-up: (1) silicon/compute → (2) frontier models →
(3) distribution surfaces (API / subscription / enterprise procurement) →
(4) harnesses/clients → (5) orchestration/meta-layers → (6) protocols →
(7) infra/sandboxing → (8) governance/audit → (9) regulation →
(10) regulated buyers.

Where margin pools:

- **Model-as-integrated-harness:** Anthropic and OpenAI capture value at both
  the model and client links simultaneously (Claude Code $2.5B ARR stated
  Feb 2026, contested ~$8B by May; Codex 3-5M weekly developers), driving
  $965B and $852B valuations respectively.
- **Enterprise seats and identity:** Microsoft monetizes Claude, Codex, AND
  Copilot inside Agent HQ regardless of which model wins; Entra/Okta monetize
  the agent-identity plane every vendor's agent must sit under.

What commoditizes fastest: the harness (hollowed from below by open clients
— OpenCode ~165k+ stars, Cline, Goose-under-AAIF — and from above by
meta-harnesses — Databricks Omnigent, Claude Code Router) and the raw token
(Chinese MIT/Apache weights at sub-$0.06/M: DeepSeek V4-Pro at 80.6%
SWE-bench Verified, Tencent Hy3 at ~1 yuan/M, ByteDance Seed 2.0 Code at
~$0.30/$0.20). The "cheaper tokens, pricier bills" paradox — agentic
workflows burn 5-30x more tokens — keeps lab top lines growing anyway, but
the equilibrium is fragile if meta-harness routing ever lets buyers keep the
US bundle's UX while paying Chinese token prices.

## The Nine Layers

### 1. US/Western frontier labs

Anthropic leads developer coding-agent revenue and enterprise share (54% vs
OpenAI's 21% per Menlo, Dec 2025) and filed confidentially for IPO at $965B
(2026-06-01). OpenAI folded Codex into "ChatGPT Work" (2026-07-09, GPT-5.6)
and claims 3-5M weekly Codex developers. Google killed the open Gemini CLI
(consumer cutoff 2026-06-18) for the closed Antigravity platform — the
purest walled-garden move on record. Microsoft/GitHub is deliberately
model-agnostic: Agent HQ (expanded 2026-02-04) runs Claude, Codex, Jules,
Cognition, and xAI agents side-by-side, monetized via Copilot Pro+/Enterprise
seats. Amazon mirrors that at infra level (Bedrock AgentCore; OpenAI models
on Bedrock in preview; Kiro force-replacing Amazon Q). Meta bought consumer
agent distribution (Manus, ~$2B, reported closed 2025-12-29 — verify before
citing) for WhatsApp/Messenger. xAI's Grok Build arrived a year late,
pitching local-first individual developers.

**Power:** model quality and developer loyalty sit with Anthropic/OpenAI, but
the surfaces developers work inside — GitHub, Bedrock — sit with
Microsoft/Amazon, who host all comers. They are the de facto toll collectors.

### 2. China ecosystem

Flipped from "cheap alternative" to majority supplier of the world's
agentic-coding tokens: ~51-61% of OpenRouter volume by Feb-Jun 2026,
overwhelmingly coding/agentic workloads. Five labs ship their own coding
CLIs (Qwen Code ~18k stars, Kimi Code as a built-in CCR preset, Zhipu's
ZCode launched 2026-07-02 explicitly to harvest Anthropic backlash with free
tokens, Tencent CodeBuddy, DeepSeek harness in progress). DeepSeek V4-Pro/
V4-Flash shipped MIT-licensed at GPT-5.5-class agentic coding (2026-04-24).
China issued its first agent-specific national framework (effective
2026-07-15: filing, testing, recall duties). Counter-pressure: DeepSeek
banned/restricted on government devices across 17+ US states and 6+
countries; Anthropic's covert "prompt steganography" tracking of suspected
Chinese Claude Code users (added Mar 2026, removed after July exposure)
damaged trust in the other direction.

**Power:** Chinese labs hold model-layer power (volume, price, permissive
licenses no ToS can revoke) but not yet harness-layer power in the West —
distribution runs through Western bridges (CCR, OpenRouter, Gemini-CLI
forks). The US executive's compute export licensing (H200 caps, ~zero units
actually delivered) is the one remaining hard chokepoint.

### 3. Runtimes / control planes (OpenClaw, Hermes, and peers)

The layer is dominated by two open-source always-on personal-agent gateways
that eclipsed enterprise frameworks in raw adoption:

- **OpenClaw** (Clawdbot → Moltbot → OpenClaw, Nov 2025, Peter Steinberger):
  became GitHub's most-starred repository on 2026-03-03 (overtaking React);
  ~378k stars by May. Renamed twice under Anthropic trademark pressure.
  OpenAI acqui-hired Steinberger (2026-02-15) while OpenClaw spun into an
  OpenAI-supported independent foundation ("Switzerland of AI") — governance
  documents still unpublished as of mid-April 2026. Security debt is
  severe: CVE-2026-25253 one-click RCE (CVSS 8.8), 138+ CVEs, ~42.7k exposed
  instances, academic red-teaming showing ~17% baseline sandbox-defense
  success, 824+ confirmed-malicious ClawHub skills (of 13k+).
- **Hermes Agent** (Nous Research, Feb 2026): ~99k stars in 8 weeks, ~213k
  by July — fastest-growing agent framework of 2026; same messaging-first,
  model-agnostic gateway thesis.
- Peers: OneClaw (60-second deploys), Poke (~$300M valuation), ClawRouter
  (claims ~67% inference cost cuts via multi-model routing).

Anthropic's 2026-04-04 OAuth ban hit OpenClaw hardest, briefly suspended
Steinberger's own account (reversed under viral backlash), and pushed
OpenClaw into "security through numbers" multi-model routing — structurally
reducing Anthropic's future leverage. OpenAI's soft capture (hire + fund the
foundation) has proven the more durable play than enforcement.

**Power:** sits with whoever controls the routing/gateway chokepoint between
users and providers. The labs demonstrated they can cut a payment rail but
cannot stop a model-agnostic runtime.

### 4. Harness layer

Three simultaneous fights: (a) **capital consolidation** — SpaceX's $60B
all-stock acquisition of Cursor/Anysphere announced 2026-06-16 (Cursor: 7M
MAU, ~$4B ARR run-rate); Cognition absorbed Windsurf (~$250M, Dec 2025) into
"Devin Desktop" and claims 89% of its own commits are Devin-authored;
(b) **platform governance** — GitHub Agent HQ as the neutral admin plane
above every vendor harness; (c) **open-source meta-harness wave** — OpenCode
(~165k+ stars, claimed 7.5M monthly devs), Cline ($27M Series A), Goose
(donated to Linux Foundation AAIF 2026-04-07), Databricks' Omnigent
(2026-06-16, Apache-2.0: one agent definition running across Claude Code,
Codex, and others), plus CCR and PAL/clink. Roo Code archived May 2026 —
the community-fork shakeout has begun. OpenAI's own `codex-plugin-cc`
(Claude Code delegating to local Codex) proves first-party comfort with
cross-vendor delegation mechanics — shipped with zero governance.

**Power:** three chokepoints — credential/auth paths (labs), developer real
estate (GitHub), and swappability (meta-harnesses commoditizing everything
below them).

### 5. Protocols / standards

Governance is consolidating at the Linux Foundation while control stays
balkanized: MCP (97M monthly SDK downloads, ~10k active public servers)
moved into the new Agentic AI Foundation (AAIF, formed 2025-12-09; platinum:
AWS, Anthropic, Block, Bloomberg, Cloudflare, Google, Microsoft, OpenAI) —
but Google kept A2A (150+ orgs, v1.0 with Signed Agent Cards 2026-04-09) on
its own separate LF track and moved AP2 payments to FIDO, not AAIF. Agent
payments fragmented three ways (AP2 / Coinbase x402 — now Stripe-integrated
/ Mastercard Agent Pay for Machines). Agent identity is unratified
(IETF AIMS draft 2026-03-02 vs shipped Entra Agent ID vs academic AIP).
SKILL.md achieved unusually fast cross-vendor convergence (32+ vendors).
NIST/CAISI opened a deferential standards track (2026-02-17) with an Agent
Interoperability Profile due Q4 2026. **The local agent-to-agent handoff
primitive remains the one seam with no standards body even attempting
convergence** — every framework names it differently (Task, handoff(),
LangGraph edge, CrewAI delegation).

### 6. Infra / sandboxing

Every major lab now ships first-party containment rather than relying on
third parties: Anthropic sandbox-runtime (srt, open-source, native in Claude
Code since v1.0.29; gVisor for Claude.ai; full VMs for Cowork), OpenAI
(Landlock/seccomp locally; acquired Ona/ex-Gitpod 2026-06-11 for
Firecracker-microVM cloud execution), Microsoft (open-sourced "Microsoft
Execution Containers," Copilot sandboxes preview 2026-06-02), Cursor
(VM-per-agent; 35%+ of its own merged PRs agent-authored). Independents:
Modal ($355M Series C at $4.65B, 2026-05-21), E2B ($21M), Daytona ($24M).
Firecracker microVMs are the near-universal substrate. Memory layer: Mem0
(~47k stars), Letta; browser infra: Browserbase ($300M valuation).
**Nobody productizes local-workstation containment for agent-to-agent
handoffs** — first-party stacks contain their OWN agent only.

### 7. Governance / security market

Consolidating fast on real incidents, not hypotheticals: postmark-mcp (first
in-the-wild malicious MCP server, BCC exfiltration backdoor, 2025-09-17);
the LiteLLM supply-chain compromise partly executed BY an autonomous agent
(Feb-Mar 2026); and the "PocketOS incident" — a Cursor/Claude Opus 4.6
coding agent deleting a company's entire production database and co-located
backups in 9 seconds with no attacker and no prompt injection (2026-04-25).
OWASP's 2026 agentic-security report now catalogs real breaches, with prompt
injection mapped to 6 of its 10 risk categories. Market moves: Langfuse
acquired by ClickHouse (Jan 2026); Braintrust $80M Series B at $800M
(2026-02-17); Okta for AI Agents GA (2026-04-30) as a universal agent IdP;
Entra Agent ID GA + Purview runtime DLP; WorkOS auth.md (May 2026);
SentinelOne agreed to acquire Prompt Security (close ~Q3 FY26).

**Power:** migrating to the identity/credential control plane because it is
the only enforcement point that works today — no shipped, unforgeable,
third-party-verifiable action-attestation standard exists (SCITT,
C2PA-for-agents remain drafts with no production deployments found). The
package registry (npm/PyPI takedowns) is the second effective chokepoint.

### 8. Regulation / geopolitics

Three regimes at different speeds. **EU:** GPAI Code of Practice (~24
signatories incl. Anthropic/OpenAI/Google/Microsoft; Meta and Chinese labs
abstaining) hard-enforceable 2026-08-02; the Digital Omnibus (approved June
2026) delayed Annex III high-risk obligations to Dec 2027 — ordinary coding
agents are probably not high-risk, so Art 12/26 log-retention is a slow
contested tailwind, not a firing gun. **US:** executive-branch whiplash —
$1/agency GSA deals for Claude/ChatGPT (Aug 2025), then a Feb 2026
presidential directive banning Anthropic federally after it refused
autonomous-weapons/surveillance uses; Pentagon designated Anthropic a
supply-chain risk; litigation split (N.D. Cal. injunction for Anthropic vs
DC Circuit stay denial) unresolved as of July 2026. Dec 2025 EO seeks
federal preemption of state AI laws; Colorado repealed-and-narrowed its AI
Act; June 2026 EO created voluntary pre-release access for frontier models
benchmarked on cyber capability. **China:** first agent-specific national
framework effective 2026-07-15 (risk tiers, filing, testing, recall).
Overhanging everything: Anthropic's 2025-11-13 disclosure that Chinese state
actor GTG-1002 used Claude Code to autonomously execute 80-90% of a
cyber-espionage campaign against ~30 targets — the founding exhibit for
agent-attribution requirements.

### 9. Economics / power dynamics

Subscription-vs-API arbitrage was H1 2026's defining fight: Anthropic cycled
through FOUR interventions in six months (Jan OAuth block — reversed; Feb
ToS restriction; Apr 4 hard ban citing 135,000+ OpenClaw instances; Jun 15
metering plan — documented as effective), while OpenAI (Apr 2) and GitHub (Jun 1) both moved
to token-metered credits. Industry direction is unambiguous: metered
automation. M&A accelerated ~4x (35 agentic deals in trailing 12 months vs
9 prior): SpaceX/Cursor $60B, Google's $2.4B Windsurf reverse-acquihire then
Cognition's $250M absorption, Salesforce/Fin $3.6B, ServiceNow/Moveworks
$2.85B. Anthropic ($965B) passed OpenAI ($852B) in private-market valuation
in May 2026. Governance-minded community tooling (Bernstein, 656 stars)
trails ungoverned tooling (CCR 35.7k, OpenClaw ~378k) by ~50-500x.

## The Five Most Contested Control Points

| Control point | Contenders | Likely winner |
| --- | --- | --- |
| Enterprise agent-identity plane | Microsoft Entra vs Okta/Auth0/WorkOS | Microsoft (M365 base); Okta takes multi-cloud tier |
| Cross-vendor orchestration surface | GitHub Agent HQ vs Bedrock AgentCore vs meta-harnesses | GitHub inside the repo; meta-harness threat real if routing matures |
| Subscription-vs-API credential rail | Labs (metering) vs model-agnostic runtimes/routers | Negotiated draw — labs meter but cannot close routing; OpenAI's soft capture beats Anthropic's enforcement |
| Compute/model-cost floor | US export regime vs Chinese open weights | China on token volume; US on frontier margin + export ceiling |
| Action-attestation/audit standard | Nobody ships; SCITT/C2PA drafts; identity fills gap | Vacant until regulation forces it — the empty cell |

## Conflict Lines

1. **Labs vs harnesses** — vertical integration vs model-as-swappable-commodity.
2. **Open vs closed weights** — Chinese MIT/Apache licensing + price war vs
   metered US bundles (ZCode launched to harvest Anthropic backlash).
3. **US vs China** — export controls and procurement bans vs token-volume
   dominance; trust damaged on both sides (DeepSeek bans; Anthropic's covert
   tracker).
4. **Standards battles** — MCP vs A2A governance tracks; three payment rails;
   unratified identity.
5. **Capital as a player** — adjacent balance sheets (SpaceX) can now buy a
   top harness outright.

## Scenarios, 2026-2028

- **A. Walled-garden consolidation (~35%).** Labs squeeze third-party
  harnesses via ToS/auth/metering. Evidence: Anthropic's four escalations,
  Google's Antigravity closure, SpaceX/Cursor, industry-wide token metering.
  Capped because labs don't control the working surface and every squeeze
  accelerates multi-model routing.
- **B. Open orchestration commons (~30%).** Open protocols + Chinese open
  weights keep the meta-layer independent; cross-vendor delegation
  normalizes. Strongest raw adoption (OpenClaw #1 repo, 51-61% token share,
  Omnigent). Wounded by catastrophic security debt and by procurement bans
  locking it out of regulated buyers. "The commons wins the developer's
  laptop; it struggles to win the SOC 2 audit."
- **C. Regulated middleware era (~35%).** Real incidents (GTG-1002,
  PocketOS, postmark-mcp) + deadlines (EU GPAI Aug 2026, China Jul 2026) +
  SOC 2 attribution findings force a governed intermediary layer. Identity
  wins by default absent attestation standards. Governs the enterprise slice
  hard while barely touching individual developers.

**Most likely outcome: a layer-specific mix** — B wins the individual-dev
layer, C wins the enterprise/regulated layer, A partially wins the
premium/consumer layer. Microsoft (Agent HQ + Entra + Purview) is the most
anti-fragile actor across all three; Google's closed-platform bet is the
most fragile. Robust strategy for anyone: own the identity/governance seam,
stay model-agnostic at the surface, build attributable exportable action
logs now.

## Where Cairnspan Sits

Cairnspan occupies the intersection of three independently-confirmed gaps: the
unstandardized local agent-to-agent handoff seam, the trust boundary having
moved to the sandbox, and the absence of any shipped action-attestation
standard. **The cell is genuinely empty — and emptiness cuts both ways: the
market's revealed preference so far is zero governance** (ungoverned tooling
outdraws receipt-minded tooling by ~50-500x; attestation adoption is zero
absent regulation). Demand for receipts today is latent and regulatory, not
revealed and voluntary. The buyer who wants receipts (enterprise) sits one
segment above what a solo Windows-only private alpha can ship to — that
segment gap, not competition, is the existential risk.

Relationships per layer: CCR/clink/Omnigent are mechanics-competitors with
no governance (position against, or harden); Bernstein vacates Cairnspan's
single-owner cell (reference, not rival); OpenClaw/Hermes are the demand
proof AND the adoption counter-proof; identity vendors (Okta, Entra, WorkOS)
are the natural complements and realistic acquirers — they prove WHO the
agent is, Cairnspan proves WHAT it did at the local boundary; sandbox infra is
substrate to run on, not to rebuild; frontier labs are structurally
threatened by the subscription wedge (which is why it stays out of public
copy).

Five highest-leverage moves (from the fit synthesis, 6-month horizon):

1. Reposition as **the local reference implementation of the unstandardized
   handoff seam** — map the route-plan/receipt/closure schema to NIST CAISI's
   Interoperability Profile (Q4 2026) and SCITT vocabulary now.
2. **Weaponize the PocketOS failure mode**: publish "same destructive task,
   two ways" (clink `--yolo` vs a Cairnspan route) — this replaces the
   legally-radioactive subscription hook as the flagship demo.
3. **Cursor as adapter #3; Gemini demoted** to an API-key/Vertex-only
   constrained tool behind an explicit policy boundary (per provider
   verdicts).
4. **Engineer for acqui-hire/tech-tuck, not standalone SaaS** — package
   containment + forgery-resistant closure as an embeddable module legible
   to identity vendors and meta-harnesses needing a governance story.
5. **Protect the moat before widening the surface** — POSIX containment,
   pressure matrix, and receipt signing/digest chaining before any third
   adapter or enterprise claim. One credible "Cairnspan receipt forged" writeup
   ends the category.

## Consolidated Watchlist

- Anthropic `--bare` becoming the `-p` default; any fifth subscription-policy
  flip; reinstatement of Agent SDK metering.
- NIST CAISI Agent Interoperability Profile (Q4 2026); SCITT/C2PA-for-agents
  ratification movement.
- First EU GPAI enforcement action after 2026-08-02; whether the Annex III
  delay to Dec 2027 holds; any pull of coding/computer-use agents toward
  high-risk.
- SpaceX/Cursor close (Q3 2026); whether OpenAI closes Codex multi-vendor
  routing despite current openness.
- Chinese open-weight OpenRouter share holding >50%; first native Chinese
  CLI gaining Western traction directly (harness-layer power shift).
- OpenClaw Foundation governance documents; Omnigent-class meta-harness
  showing verifiable enterprise adoption.
- Identity vendors (Okta/Entra/WorkOS) shipping local execution-boundary
  proof themselves — narrows Cairnspan's acquisition window; their absence
  strengthens the bolt-on thesis.
- Next PocketOS-class no-attacker catastrophic agent incident — free
  demand-generation for governed delegation; capture immediately.
- H200/successor actual delivery volumes into China; expansion of Chinese-
  model procurement bans.
- Anthropic-Pentagon litigation resolution (DC Circuit vs 9th Circuit split).
