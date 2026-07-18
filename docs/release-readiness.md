# Cairnspan Release Readiness

This document separates three claims that must not be collapsed into one.

## 1. Source-Ready

`source` means the checkout has the files, naming, documentation, root release
metadata scans, five existing surface-tree scans, and CI shape required to
prepare a release candidate. It does not mean the repository
has a reproducible commit, a public remote, a version tag, or current human
review.

Run:

```powershell
python skills\cairnspan\scripts\release_readiness.py --profile source --format json
```

## 2. Public Two-Agent Alpha

`public-alpha` is the first publishable target. Its exact claim is:

> Cairnspan is an experimental, owner-local coordination layer with a verified,
> bounded two-agent text route between installed Codex and Claude Code clients
> on Windows. It is not production-ready, enterprise-ready, cross-platform, or
> three-agent capable.

Three-agent work is not a prerequisite for this release. Packaging is also not
required: `0.1.0-alpha.1` may be a pinned source release using the repo-scoped
skill installation path.

Before the alpha is published, all of these must be true:

- the complete deterministic test, compile, skill-validation, scan, and diff
  gate passes against the exact candidate commit;
- the source tree is clean, a canonical remote exists, and tag `v0.1.0-alpha.1`
  points at the reviewed commit;
- the current-facing public docs and fixtures receive human review after the
  scanner passes;
- the exact Cairnspan name, hosting namespace, package namespaces, relevant
  domains, and legal/trademark posture are rechecked immediately before release;
- public copy is reviewed against current provider authentication rules and does
  not present consumer subscription reuse as a Cairnspan product feature;
- the write-enabled hostile-workspace matrix is closed on fresh synthetic data,
  or workspace-write support is removed from the release candidate;
- the release uses Windows as the only authoritative platform; POSIX closure is
  not claimed until stronger containment and live tests exist;
- raw runtime receipts, credentials, local paths, private repositories, and
  product data remain outside the release;
- a private vulnerability-reporting path is enabled on the canonical host; and
- the release notes retain all known limitations, including the explicit Codex
  native path requirement and unverified current image-tool compatibility.

The final human attestations are local release evidence, not committed source.
Create `.cairnspan/release-attestations.json` with this shape:

```json
{
  "schema_version": "0.1",
  "reviewed_commit": "<40-or-64-hex-commit-id>",
  "full_gate_passed": true,
  "public_artifact_human_review_passed": true,
  "name_namespace_legal_review_passed": true,
  "provider_copy_review_passed": true,
  "private_vulnerability_channel_enabled": true
}
```

Then run the final gate from that clean tagged commit:

```powershell
python skills\cairnspan\scripts\release_readiness.py `
  --profile public-alpha `
  --attestations .cairnspan\release-attestations.json `
  --format json
```

The command exits nonzero if any blocker remains. It does not create a remote,
tag, release, package, provider run, or attestation.

After publication, independently verify that the canonical remote exposes the
reviewed commit and tag, repository visibility is actually public, host CI passed
for that commit, the private vulnerability channel works, and the release notes
match the local candidate. A pre-publication gate is not post-publication proof.

## 3. Production-Ready

`production` is a later claim. It additionally requires the broader native
crash, quota, rate-limit, live-canary, and repeated-run pressure matrix;
authoritative containment on every supported operating system; install and
upgrade testing by independent users; signed release artifacts, pinned
dependencies, an SBOM, retention controls, budget enforcement, a kill switch,
and an operational support/security process.

Enterprise readiness is stricter still. The adapter contract, central policy
engine, data classification, provider-boundary receipts, SIEM export, and
multi-target conflict controls belong there.

## Internal Product Gates Are Separate

Publication does not authorize provider spend or product transfer.

- Typed-effort compatibility: the exact typed-effort compatibility proposal
  may run under the owner's active standing approval policy when it matches
  the bounded synthetic envelope; any phased program work remains a fresh
  owner decision per phase.
- Image capabilities: current image-generation and image-view capability
  probes may run under the owner's active standing policy when they match its
  bounded synthetic envelope. Only then may an independently authorized
  three-item synthetic pilot run; only a clean pilot may lead to a
  product-specific finite plan and a separate product-integration approval.

These gates keep an alpha release from silently authorizing live work.

## Current Provider Boundary

OpenAI documents local ChatGPT sign-in and `codex exec` for scripts and CI, while
its automation guidance says API keys are the default and warns against using
account-auth seeding for public or open-source repositories. Anthropic documents
`claude -p` and subscription authentication for native Claude Code use, but its
legal guidance says developers building products or services should use API-key
or supported cloud-provider authentication and must not route Free, Pro, or Max
credentials on behalf of users.

Therefore the source alpha is owner-local: users install and authenticate the
official clients themselves, and Cairnspan never offers provider login, exports
credentials, seeds public CI with account auth, or routes one user's subscription
on behalf of another. Shared, hosted, or on-behalf-of-user automation requires a
separate API-key or managed-provider design and release review.

Primary references:

- <https://developers.openai.com/codex/auth>
- <https://developers.openai.com/codex/noninteractive>
- <https://code.claude.com/docs/en/headless>
- <https://code.claude.com/docs/en/authentication>
- <https://code.claude.com/docs/en/legal-and-compliance>
