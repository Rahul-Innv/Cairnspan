# Security Policy

Cairnspan is a prototype and should be treated as private, local tooling until the verification matrix is complete.

## Security Model

- Cairnspan is designed not to broker OAuth tokens.
- It launches local authenticated agent clients and records observable run metadata.
- Raw run logs may contain prompts, local paths, model output, tool output, and sensitive data printed by the target agent.
- Prompt text is redacted from `cairnspan-summary.json`, but prompt hashes and prompt file paths are recorded.
- Use `read-only` sandbox mode for probes. Read-only is a write boundary, not a confidentiality boundary: the target agent may still read workspace files and send relevant context to its model provider or configured tools.
- Use `workspace-write` only when file edits are expected.
- Avoid `danger-full-access`; it requires explicit unsafe opt-in and a reason.
- Treat raw target-agent arguments, configured MCP access, and output directories outside the workspace as safety-sensitive until tested.
- Claude Code launches default to safe mode, strict MCP isolation, no tools, and no session persistence. Allowing project customizations reintroduces hook/plugin/instruction risk.
- Known raw API-key and alternate-provider environment overrides are scrubbed from target processes by default. OAuth/keychain credentials remain owned by the installed client.
- Receipts stored inside a write-enabled target workspace are not tamper-evident. Use a parent-controlled receipt directory outside the target `--cwd` when evidence integrity matters.
- Prompt redaction in the summary does not remove the prompt from the target process command line. Use only secret-free prompts until stdin-based target entrypoints are verified.

## Private Data

Do not publish raw `.cairnspan` run directories without review. Before sharing evidence, redact:

- local user paths
- secrets or tokens
- private prompt text
- account identifiers
- repository names that should remain private
- model outputs that quote private files

## Reporting Issues

While this repository is private, record security issues in
`docs/verification.md` without committing secrets or exploitable private data.

Before public release, enable the canonical Git host's private vulnerability-
reporting channel and record that fact in the release attestation. Do not open a
public issue containing a vulnerability, credential, private receipt, or local
path. If the private reporting channel is unavailable, contact the repository
owner through an established private channel and do not publish the details.
