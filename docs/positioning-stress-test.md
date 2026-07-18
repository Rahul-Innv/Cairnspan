# Positioning Stress Test (Online Evidence)

Research date: 2026-07-11.

Method: adversarial deep-research pass — 5 search angles, 22 sources fetched,
90 claims extracted, top 25 claims each judged by a 3-vote adversarial panel
(2/3 refutations kill a claim). 22 claims survived, 3 were refuted. This
document records what the surviving evidence does to the positioning in
`docs/positioning.md`, which was written the same day from repo-internal
analysis only.

Time-sensitivity is severe: the provider-policy findings span Jan-Apr 2026 and
were still evolving at research time. Refresh before any public copy.

## Headline

The positioning splits cleanly under stress:

- The **differentiator** ("provable delegation with receipts") **survives and
  is strengthened** — no vendor, community tool, standard, or product ships
  governed local cross-agent handoffs, and the most popular community
  substitute is explicitly ungoverned.
- The **hook** ("use every AI agent you already pay for" via existing
  OAuth/subscription logins) remains unsuitable as public positioning.
  Anthropic documents official `claude -p` scripting and subscription CLI
  authentication, but provider terms and billing remain distribution-specific;
  the OpenAI side is unresolved.
- Bare **"cross-vendor delegation" is commoditized** and must never be
  claimed as novel.

## Finding 1 (critical, primary-source refreshed): Anthropic authentication boundary

The original secondary-source synthesis above this refresh was too broad.
Current Anthropic primary documentation, rechecked 2026-07-11, says:

- `claude -p` is the official programmatic CLI interface for scripts and CI/CD.
- Claude Code authentication explicitly supports subscription OAuth from
  `/login`; it also documents `claude setup-token` for scripts where browser
  login is unavailable.
- OAuth is intended for ordinary use of native Anthropic applications.
  Developers building products or services should use API-key or supported
  cloud authentication, and may not offer Claude.ai login or route Free, Pro,
  or Max credentials on behalf of users.
- As of 2026-07-12, Anthropic documents a separate monthly Agent SDK credit for
  subscription-backed Agent SDK and `claude -p` usage, effective 2026-06-15.
  The amount and billing behavior remain provider-controlled and time-sensitive.

Primary sources:

- <https://code.claude.com/docs/en/headless>
- <https://code.claude.com/docs/en/authentication>
- <https://code.claude.com/docs/en/legal-and-compliance>
- <https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan>

### What this means for Cairnspan — precisely, not maximally

Cairnspan's architecture is materially different from the banned pattern: it
never reads, copies, proxies, or re-uses OAuth tokens, never spoofs client
identity, and launches the **unmodified official client** (`claude -p`,
`codex exec`) with its own native login. The banned pattern is third-party
harnesses consuming subscription OAuth tokens directly.

Four exposures remain real:

1. Cairnspan must never extract, export, replay, or proxy Claude credentials.
2. It must never offer Claude.ai login or route subscription credentials on
   behalf of users; each owner must operate the installed official client and
   its own native login.
3. Anthropic has not specifically approved Cairnspan. Public distribution,
   commercial use, or shared production automation needs a fresh provider-policy
   decision; API-key or managed-provider authentication is the conservative path.
4. The product name and one-liner advertise a time-sensitive provider mechanism.
   "OAuth" remains a public-branding liability even when the implementation
   does not handle credentials.

The owner-local official-client experiment is not blocked by the earlier broad
claim that all noninteractive OAuth CLI use is prohibited; Anthropic documents
that scripting path. Public release still needs a provider-policy gate because
the product/service and on-behalf-of-user boundaries are not specific to Cairnspan.

### Required rework

- Reframe the wedge everywhere: from "OAuth-backed session reuse" to
  "launches the unmodified official vendor client under its own native
  login; Cairnspan never touches credentials and never spoofs client identity."
- Treat provider-policy compliance as a first-class threat-model entry and
  release gate, alongside the technical gates.
- Promote the API-key or managed-provider path from "explicitly a fallback,
  not the product identity" to the conservative mode for shared production
  and commercial automation. Keep native subscription login owner-local and
  ordinary-use only unless Anthropic confirms a broader use case.
- Reconsider the name. `docs/name-check.md` covered collisions; it did not
  cover the name advertising a mechanism under active provider crackdown.
- Scope public copy to personal, local, owner-invoked use until the
  compliance question is resolved; no unattended/commercial claims.
- Run the same ToS analysis for OpenAI/Codex (not covered by any verified
  claim in this pass — open exposure).

## Finding 2: the hook is commoditized; the moat is not

Verified, high confidence (multiple 3-0 votes):

- **PAL MCP Server** (formerly Zen MCP Server; 11.7k stars, ~1k forks) ships
  "clink" (CLI+Link), which spawns external CLIs — Gemini, Codex, Claude
  Code — directly into one workflow using each CLI's own installed auth.
  That is cross-vendor CLI-to-CLI delegation, i.e. Cairnspan's hook, free and
  shipped. It also ships 16 structured multi-step workflows (codereview,
  debug, secaudit, planner, consensus, precommit, ...).
- Crucially, clink is the **opposite of governed**: it launches targets with
  bypass flags (Gemini `--yolo`, Codex
  `--dangerously-bypass-approvals-and-sandbox`, Claude
  `--permission-mode acceptEdits`) and documents no sandboxing, receipts,
  manifests, containment, or verification.
- **Claude Code Router** (35.7k stars, 2.9k forks) commoditizes "cross-vendor"
  at the model-routing layer: a local proxy routing Claude Code/Codex/ZCode
  requests to a dozen providers, with a dashboard, request logs, and usage
  stats — but it is API-key model routing, not agent delegation, and has none
  of Cairnspan's governance primitives.
- OpenHands (~75.8k stars) and Aider (~45.8k stars) show no cross-agent
  delegation features at all.

Consequences:

- Never claim cross-vendor delegation as novel. The honest claim is: the
  delegation everyone already does is ungoverned; Cairnspan is the governed
  version.
- PAL/clink is simultaneously the strongest demand proof for the hook
  (people demonstrably want Claude/Codex/Gemini working together through
  local CLIs) and the strongest evidence that governance is the vacant slot.
- Concrete positioning artifact to build: a side-by-side — clink-style
  bypass-flag handoff vs. a Cairnspan route — showing exactly what each can and
  cannot prove afterward.

## Finding 3: the receipts niche is real, unoccupied, and incentive-starved

Verified, high confidence:

- The "Notarized Agents" paper (arXiv:2606.04193) defines five properties for
  trustworthy agent action records — unforgeable, independently verifiable,
  confidential, attributable, retrievable — and states no surveyed system
  (Signet, AgentROA, Agent Passport System, draft-farley-acta, SCITT)
  delivers all five. The gap Cairnspan targets is academically validated.
- The same authors concede against interest: in 2026 no service has an
  incentive to emit such receipts — "adoption is zero" — absent regulation
  (EU AI Act Art. 12/26), payment-coupling, or a trust premium.
- Escape hatch that fits Cairnspan exactly: the cold-start problem applies to
  **multi-party** notarization where *other services* must emit receipts.
  Cairnspan's receipts are **single-owner and self-issued**: the same user owns
  origin, target, and verifier, so the adoption incentive problem largely
  does not apply. Position as self-verification for your own delegations,
  not third-party notarization infrastructure.
- Two broader claims were REFUTED (1-2 each) and must not appear in copy:
  "no production-ready protocol cryptographically verifies multi-hop
  delegation chains" and "IETF AIMS is the most advanced relevant standards
  effort." Claim the *local cross-agent handoff receipt* gap narrowly, not a
  total delegation-verification void.

## Finding 4: enterprise agent governance has an incumbent — in a different plane

Verified, high confidence:

- Microsoft Entra Agent ID (GA April 2026) gives agents first-class auditable
  identities, supports OAuth 2.0/MCP/A2A, works across non-Microsoft
  platforms (AWS Bedrock, n8n), and logs all agent authentication and
  activity for compliance.
- It is a **cloud identity-plane** product: IdP-issued identities and
  centralized logs. It does not do local-first, zero-server, cross-vendor
  local-CLI handoffs with per-run workspace manifests and closure receipts.

Rework: position the enterprise ladder as the **execution-plane complement**
to identity-plane governance ("Entra tells you which agent authenticated;
Cairnspan proves what the delegated run actually did to the workspace"), not as
a rival governance stack. This also validates enterprise demand for agent
audit generally.

## Finding 5: standards leave the lane open

Verified, high confidence (with one hedge):

- Academic surveys (arXiv:2604.23280, arXiv:2603.24775) score MCP "identity
  out of scope by design," with no built-in agent identity or standard
  authorization for cross-agent trust boundaries. Proposals (AIP, IBCTs) are
  research, not adopted standards.
- Hedge: A2A does standardize identity "at the edges" (agent-card auth), so
  do not say identity/delegation is wholly out of scope for A2A.
- Nobody is standardizing **local** agent-to-agent handoffs. Cairnspan's adapter
  contract complements rather than conflicts with MCP/A2A, and could aim at
  becoming the de facto local handoff contract once a third adapter proves it
  is not pair-specific.

## Verdict Table

| Positioning claim | Verdict | Evidence |
| --- | --- | --- |
| Hook: "use every AI agent you already pay for" (subscription-auth reuse) | **BREAKS** as public/commercial positioning on the Anthropic side; OpenAI side unresolved | Finding 1 |
| Wedge: "OAuth-backed local clients" as the product identity | **AT SEVERE RISK** — reframe to official-client + native-login + no-credential-handling; compliance is a release gate | Finding 1 |
| "Cross-vendor delegation" as novel | **BREAKS** | Finding 2 (PAL/clink, CCR) |
| Differentiator: "provable delegation with receipts" | **SURVIVES, strengthened** — the popular substitute runs with bypass flags; academia confirms nobody delivers the receipt properties | Findings 2, 3 |
| "Nobody does local cross-agent handoff receipts" | **SURVIVES narrowly** — claim the local gap only; two broader void-claims were refuted | Findings 3, 5 |
| Enterprise ladder: "vendor-boundary governance" | **SURVIVES** — with Entra Agent ID as the identity-plane incumbent to complement, not fight | Finding 4 |
| "No server / no daemon" | Unchallenged | — |
| Name "Cairnspan" | **AT RISK** — foregrounds the policed mechanism | Finding 1 |

## Top 5 Evidence-Backed Opportunities

1. **Govern the commoditized layer.** PAL/clink proved the demand and left
   governance empty. The pitch writes itself: the delegation you already do,
   minus the `--dangerously-bypass` flags, plus proof.
2. **Compliance-as-feature.** In a crackdown era, a delegation layer that is
   demonstrably polite — unmodified official clients, pinned versions, no
   credential handling, no spoofing, bounded cost — can be the one that
   survives. Cairnspan already has version pinning and credential scrubbing;
   make "provider-respectful by construction" an explicit claim once the ToS
   question is resolved.
3. **Self-issued receipts dodge the cold-start.** Target single-owner
   self-verification (prove to yourself/your org what your own delegations
   did), which needs no ecosystem adoption, unlike notarization schemes.
4. **Execution-plane complement to identity-plane governance.** Integrate
   with, rather than compete against, Entra-style agent identity: their logs
   say who; Cairnspan's receipts say what, with manifests.
5. **The open local-handoff standards lane.** After a third adapter, the
   adapter + receipt contract is a candidate de facto standard; MCP/A2A
   explicitly do not cover it.

## Immediate Rework Actions

1. Resolve the provider-ToS question against primary sources (Anthropic
   Commercial Terms / Usage Policy / Claude Code legal page; OpenAI Codex
   terms) and record the analysis in `docs/threat-model.md` as a release
   gate. Until then: personal, local, owner-invoked scope only.
2. Rewrite wedge language in README, `docs/plan.md`,
   `docs/strengthening-plan.md`, `skills/cairnspan/SKILL.md`: official
   client + native login + zero credential handling; drop "OAuth-backed
   session reuse" phrasing.
3. Add an explicit API-key-compatible mode to the roadmap as the ToS-safe
   commercial path; keep subscription-auth as personal-default only where
   terms permit.
4. Open a naming review: keep `cairnspan` for the private repo, but do not
   carry "OAuth" into public branding without the compliance answer.
5. Add PAL/clink and Claude Code Router to the landscape in
   `docs/positioning.md`; delete any implication that cross-vendor is novel.
6. Build the clink-vs-Cairnspan provability side-by-side as the flagship demo
   artifact (replaces imagegen as the lead demo).

## Refuted Claims (do not use in copy)

- "No production-ready protocol exists that cryptographically verifies
  multi-hop agent delegation chains" (1-2).
- "IETF AIMS is the most advanced relevant standards effort" (1-2).
- "Anthropic is actively detecting and terminating accounts using third-party
  harnesses" as stated (1-2) — the policy is real; this enforcement
  characterization came from a blog and did not survive.

## Coverage Caveats

- Q1 (native cross-vendor handoff shipped by Cursor/Codex/Claude
  Code/Gemini/Perplexity) is only indirectly covered: no verified claim shows
  any first-party vendor shipping it, but absence of evidence here is not
  evidence of absence.
- Q6 (concrete enterprise demand: DLP-for-agents, SOC2-for-agents, EU AI Act
  specifics) was not directly evidenced beyond the Entra and Notarized-Agents
  findings.
- OpenAI-side subscription/ToS posture is uncovered — treat as open exposure.
- Policy findings rest mostly on quality secondary press corroborated by
  Anthropic's own compliance page; re-verify against primary terms before
  public claims. Star counts are point-in-time.

## Source List (verified claims only)

- https://code.claude.com/docs/en/legal-and-compliance (primary)
- https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access/
- https://gigazine.net/gsc_news/en/20260220-anthropic-third-party-block/
- https://venturebeat.com/technology/anthropic-cracks-down-on-unauthorized-claude-usage-by-third-party-harnesses
- https://www.axios.com/2026/04/06/anthropic-openclaw-subscription-openai
- https://github.com/BeehiveInnovations/pal-mcp-server (primary)
- https://github.com/musistudio/claude-code-router (primary)
- https://mcpservers.org/servers/jray2123/zen-mcp-server
- https://arxiv.org/pdf/2606.04193 (Notarized Agents; primary)
- https://arxiv.org/pdf/2604.23280 (AI Identity: Standards, Gaps; primary)
- https://arxiv.org/pdf/2603.24775 (Agent Identity Protocol; primary)
- https://learn.microsoft.com/en-us/entra/agent-id/what-is-microsoft-entra-agent-id (primary)
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idp-microsoft.html (primary)
