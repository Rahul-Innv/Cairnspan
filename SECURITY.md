# Security Policy

Cairnspan is early-stage local tooling. Treat each capability as verified only to
the extent recorded in the repository's verification matrix.

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

Report a suspected vulnerability through the project's GitLab Service Desk:

`contact-project+krahul02004-cairnspan-84576401-issue-@incoming.gitlab.com`

Emailing that address creates a confidential Service Desk ticket in the
canonical project. Use a clear subject, describe the affected version and impact,
and include the minimum reproduction details needed to start triage. Do not put
credentials, private receipts, sensitive local paths, or other secrets in the
initial message or in a public issue. The project owner will provide a secure
follow-up channel if sensitive evidence is required.

If the Service Desk is unavailable, contact the repository owner through an
established private channel and do not publish the details.
