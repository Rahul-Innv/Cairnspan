# Contributing

Cairnspan is currently a private alpha. The bounded two-agent text route is verified; treat contributions as design and hardening work until pressure, artifact-routing, clean-install, and public-redaction gates pass.

## Development Rules

- Keep the launcher stdlib-only unless there is a clear reason to add packaging.
- Do not copy, print, or persist OAuth tokens.
- Prefer prompt files over shell-quoted prompt text.
- Add tests for launcher behavior before relying on manual probes.
- Keep runtime artifacts out of commits unless they are sanitized fixtures.
- Update `docs/verification.md` and `docs/learnings.md` when changing behavior or discovering blockers.
- Treat read-only as write protection, not confidentiality protection.
- Add tests for unsafe flags, raw target-agent args, output-directory behavior, and artifact redaction when touching launchers.

## Test Command

```powershell
python -m unittest discover -s tests -v
```

Release candidates must also pass the exact source gate documented in
`docs/release-readiness.md`. A clean source gate is not permission to publish,
tag, run a provider, or transfer product data.

## Public Release Rule

Public claims may describe the verified bounded two-agent text route exactly as recorded in `docs/verification.md`. Do not generalize that result to production readiness, arbitrary artifacts, recursive loops, three-agent support, or enterprise safety; raw evidence must still be redacted before publication.
