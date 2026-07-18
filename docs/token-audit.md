# Credential Non-Persistence Audit

Date: 2026-07-10

Scope: Cairnspan-owned source, public fixtures, and selected private route
receipts. This audit does not inspect or make claims about the internal storage
used by the installed Codex or Claude Code clients.

## Result

No OAuth token, cookie, keychain value, raw API key, bearer token, refresh token,
or access token was found in the audited Cairnspan surfaces.

## Evidence

- Static search found no code that opens browser cookie databases, keychain or
  credential-manager stores, OAuth token files, or provider session stores.
- The launcher references to sensitive environment variables are denylist names
  used to remove raw API-key and alternate-provider overrides from child
  environments. Summaries record variable names only, never values.
- Prompt bodies are hashed and command summaries redact them. Unsafe reasons,
  raw target arguments, and explicit MCP configuration are redacted before they
  enter summaries.
- `scan_artifacts.py` reports zero findings for the redacted text route,
  shared-mailbox route, and typed PNG route fixtures (kept private; not
  shipped in this tree).
- A scan of the repeated private two-way receipt found only expected local
  Windows path findings. It found no token/key/bearer/private-key finding kind.
- Live image-generation receipts showed the account-backed built-in capability;
  no raw API-key fallback command was executed.

## Boundary

This proves only that the audited Cairnspan code and artifacts do not intentionally
extract or persist credentials and contained no recognized secret pattern. It
does not prove that provider clients never hold credentials, that arbitrary
model output cannot print a secret it was allowed to read, or that pattern
scanning can recognize every possible secret. Runtime artifacts remain private
by default, and every proposed public fixture still requires scanning and human
review.
