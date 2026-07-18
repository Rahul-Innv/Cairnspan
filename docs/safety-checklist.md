# Cairnspan Safety Checklist

Use this checklist before a private demo, public fixture, or live two-way probe.

## Before Any Live Probe

- Target workspace exists and is the intended project.
- `doctor.py` has been run and all `fail` results are fixed.
- Any `warn` result is understood and accepted.
- Prompt is in a prompt file, not fragile shell quoting.
- Sandbox is `read-only` unless edits are expected.
- Output directory is inside the workspace or explicitly approved.
- `--max-depth`, `--timeout-seconds`, and `--max-output-bytes` are bounded.
- Raw target-agent args are not used unless there is an unsafe reason.
- Native absolute target executables are used; PATH-selected shell wrappers are not used.
- The native target version was inspected, recorded, and pinned with `--expected-cli-version`; any mismatch stops before launch and is investigated rather than auto-updated.
- Prompts are secret-free because target CLIs still receive them through process arguments.
- Known sensitive auth/provider environment overrides are scrubbed.
- Claude no-edit probes use safe mode, strict MCP, no tools, and no session persistence.

## Before Workspace-Write

- Expected file changes are named in the prompt.
- A before manifest can be taken by the origin side.
- Authoritative receipts are outside the write-enabled target `--cwd`.
- The prompt tells the target not to modify unrelated files.
- A sibling/outside-workspace write is not expected to succeed.
- Scratch files are cleaned only after evidence is captured.

## Before Two-Way

- Both one-way directions have recent passing evidence.
- The combined Claude strict-MCP/no-tools/no-edit probe has passed using `docs/live-test-runbook.md`.
- The bounded route harness and aggregate budget gate in `docs/two-way-loop.md` exist and have fake-target tests.
- Route receipts are parent-controlled and outside both target workspaces.
- The orchestrator will verify and consume each target artifact before starting the next edge.
- The route root and both disposable target workspaces are fresh and non-overlapping.
- Strict Codex isolation and Claude safe-mode/strict-MCP/no-tools policy are enabled.
- Closure requires exact artifacts, strict manifests, stable executable identities, zero unexpected tool use, and no surviving descendants.

## Before Website Or Image Routing

- The brief contains only public or explicitly approved data.
- Generation uses a fresh scratch workspace, not a product repository.
- Expected artifact count, path, type, byte limit, dimensions, pixel/frame limits, runtime, and cost are declared.
- The parent will compute the artifact manifest and validate bytes independently.
- Hidden files, reparse points, hardlinks, alternate data streams, metadata, URLs, QR codes, and visible instruction-like text are treated as untrusted.
- Provenance and public-use rights are documented.
- A human approval separates generation from product integration.
- The human owner, not a delegated agent, supplies `--visual-review-status passed` and any integration approval after reviewing the hash-identified artifact.
- The integration edge declares exact destination paths and verifies only approved product changes.

## Before Publishing Artifacts

- Raw `.cairnspan/` directories are not committed.
- Local user paths are redacted.
- Prompt bodies are redacted.
- Account identifiers and private repository names are redacted.
- Private model output and quoted private files are removed.
- `scan_artifacts.py` returns 0 findings.
- Compressed containers are rejected for manual review; encoded and line-split findings are included in the scan.
- A human has reviewed the files after the scanner.

## Before Three-Agent Orchestration

- Phase 1 two-way handoff is repeatable.
- Adapter contract exists.
- Capability registry exists.
- Route plan exists.
- Policy engine exists.
- Data classification and allowed-target policy are enforced.
- Cross-provider sharing is explicit.
- Cycle, fan-out, quota, cost, and conflict tests exist.
