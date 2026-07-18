# Cairnspan — Phase 1 Adversarial Engineering Review

## 2026-07-11 Maintainer Disposition

The report was reproduced against the referenced code before remediation. The original text below is preserved as the review record; line numbers and present-tense claims refer to the pre-fix snapshot.

### Fixed Before Further Live Artifact Testing

- **P1 receipt forgery:** write-capable launchers now reject any `--out-dir` inside `--cwd`; capture names use an unexported UUID; the parent checks the open-file identity against the path before parsing and publication.
- **P2 PNG inflate bomb:** zlib output is capped at the exact IHDR-derived scanline length before full allocation, followed by EOF/trailing-data/exact-length/filter checks.
- **P2 containment overclaim:** Windows targets start suspended and do not resume when Job Object attachment fails. Summaries record `containment`; authoritative route, critique, mailbox, and artifact closures currently require `job-object`. POSIX `process-group` is recorded but deliberately not accepted as strong containment.
- **P2 PNG chunk policy:** the validator uses a static core allowlist plus fixed-size/value checks for the standard `gAMA`, `pHYs`, and `sRGB` display chunks required by the live encoder. It rejects APNG unconditionally, rejects undeclared ancillary chunks unless explicitly allowed, and validates core order plus `PLTE` structure.
- **P2 raw short flags:** attached `-s`, `-c`, and `-C` forms are normalized and rejected as conflicts.
- **Artifact prompt binding:** closure regenerates the canonical producer prompt from the validated design spec and manifest relative path and requires exact text equality.
- **Mailbox consistency:** request/response bytes are read, parsed, validated, and hashed from one handle with identity checks; closure no longer re-reads or embeds raw prompt/final content.

### Also Fixed

- Resume-failure Job handle double-close and reader-thread startup cleanup gaps.
- One-frame `acTL` acceptance, dead mailbox time helper, and short inherited-stdin test timeouts.
- Post-remediation verification: 198 tests passed in 345.156 seconds with 2 expected Windows symlink-privilege skips; compile and both skill validations passed; scans of docs, canonical skill, shim, and README each returned 0 findings.
- A second offline pass closed the scanner/tracked-snapshot/design-prompt/human-attestation coverage gaps and passed 206 tests in 404.547 seconds with the same 2 expected Windows symlink-privilege skips.

### Deferred, Still Gating Broader Claims

- Strong POSIX containment plus live forgery pressure, target-CLI version drift canaries, and behavioral prompt-injection probes remain Phase 1 release work. The deterministic scanner/tracked-snapshot adversarial matrix is now covered.
- Parent-owned fresh receipt writers still assume a trusted single closer. General multi-writer tamper-evident publication, receipt signing/digest chaining, and a formal human-invoker trust model remain required before enterprise auditability claims.
- These fixes do not make Cairnspan production-ready, enterprise-ready, or three-agent capable. A fresh live typed-artifact repetition is required because the validator and closure contract changed after the prior image evidence.
- **Date:** 2026-07-10
- **Type:** Independent read-only adversarial engineering review (pre Claude-first full-route profile / broader use)
- **Reviewer:** Claude (Opus 4.8, 1M) + a 28-subagent adversarial workflow (7 finders → per-finding skeptic verification), with findings re-verified by hand against the code.
- **Constraints honored:** No files modified during the review itself; no live provider invoked (`codex`/`claude` never executed); no `.env`/credentials/token/cookie/keychain/session stores read.

> This report is a point-in-time review artifact. It was **written after** the read-only review, at the owner's request, and is the only file the review process added.

---

## Verdict

**Ready for continued private real-world use of the currently-exercised flows — and ready only after the listed fixes for broadening.**

- The **parent-orchestrated routes** (two-way text, mailbox, artifact) and **read-only probes** on **Windows** are safe to keep using privately. Every route error path traced fails closed; receipts sit outside both workspaces; the target agent cannot forge the route's trusted-CLI-authored evidence (the one attempt to show otherwise was **refuted**); workspaces are independently manifest-checked. No P0 is reachable in normal Windows use, so this is **not** "unsafe to continue."
- Before the **Claude-first full-route profile** or "using Cairnspan more broadly," fix the **P1** (predictable-temp receipt forgery) and the three **P2** artifact/containment items. These specifically gate any **POSIX** use and any workflow that trusts a **bare write-capable launcher's own summary**.

---

## Method & environment result

- Direct reading of all 9 in-scope scripts + docs.
- Two offline PoCs against the real modules (PNG decompression bomb; `parse_events` on a forged event line).
- Full offline suite in this environment: **`python -m unittest discover -s tests` → 186 passed, 1 failed, 2 skipped (187 total, 665 s).** The single failure was `test_child_stdin_is_closed_even_when_parent_stdin_is_open` returning `124` (the launcher's own `--timeout-seconds 5` fired under host load) — a load-sensitive test, not a product defect. (`pytest` is not installed; the suite is `unittest`-based. Docs report 187/187 in ~491 s on an unloaded machine.)

---

## 1. Findings (by severity)

### P1 — Forgeable receipts via predictable capture-temp names in a child-writable workspace
*(The workflow verifier rated this **P0** on the strict rubric; calibrated to **P1** for the current Windows-first, docs-flagged, route-avoided reality — see severity note.)*

- **Where:** `start_codex_session.py:178-179` (default_out_dir), `:1159` (run_id → child env), `:1307-1308` (predictable temps `.events.<run_id>.tmp` / `.transcript.<run_id>.tmp`), `:1344` + `:1387-1388` (parse-by-name → `os.replace`-by-name). Identical in `start_claude_session.py:172-173, :1162, :1313-1314, :1350, :1420-1421`.
- **Failure scenario (POSIX):** Bare write-capable launcher — `start_codex_session.py --sandbox workspace-write` (note: `workspace-write` is *not* gated by `--allow-unsafe`; only `danger-full-access` is, `:1106`) or `start_claude_session.py --tools Bash --permission-mode dontAsk` (a specific tool name isn't caught by `has_unsafe_tool_value`, which only flags `default/*/all`). Default out-dir is `cwd/.cairnspan/<run_id>`, inside the child-writable workspace. The child reads `CAIRNSPAN_RUN_ID` and reconstructs the exact temp path; mid-run it `os.rename`s a forged `turn.completed` over `.events.<run_id>.tmp`. On POSIX the name rebinds to the child's inode while the parent writes real stdout to the now-unlinked original; the parent then `parse_events` reads the forged file **by name** and `os.replace`s it into `events.jsonl` — with **no `fstat`/`st_ino`/`samefile` identity check**. Verified offline: `parse_events` on the forged line yields `completion_observed=True, terminal_event_count=1, warnings=[], tool_use_count=0` → the parent authors a genuine-looking `status: "succeeded"` summary.
- **Impact:** The parent-authored summary — the artifact meant to bind an untrusted delegate — is derived from child-forgeable input.
- **Severity note (why P1, not P0):** (1) On **Windows** the parent's open `"x"` handle blocks rename-over → the attack degrades to corruption that trips the terminal-count guards → **fails closed**. (2) The blessed write-capable routes place receipts **outside** both workspaces and cross-check parent-owned strict manifests, so they are unaffected. (3) The docs already state in-workspace receipts are "not tamper-evident" (`SECURITY.md`, `SKILL.md:29`, `threat-model.md:99`). It remains a real, **un-enforced** footgun on POSIX / bare-launcher use and should be **fixed before the Claude-first profile, any POSIX use, or broader adoption**.
- **Minimal fix (cleanest):** Derive the events/transcript temp suffix from a fresh `uuid4().hex` **not exported to the child** (the `final.md`/summary temps already do this and are safe). Belt-and-suspenders: refuse an out-dir inside `cwd` when the sandbox is write-capable, and/or `fstat` the open fd and compare `st_dev/st_ino` before `os.replace`.

### P2 — Unbounded `zlib.decompress` on PNG IDAT → decompression-bomb DoS
- **Where:** `artifact_manifest.py:159-165` (decompress before the length check at `:164`); size gate `:210-212` caps only the compressed input.
- **Confirmed by PoC:** a 58 KB PNG (under the 5 MB `--max-bytes` default) declaring 16×16 carried an IDAT inflating to 60 MB → ~141 MB peak allocation before rejection. At ~1000× zlib ratio a 5 MB input forces multi-GB allocation. The artifact is produced by a semi-trusted delegated agent.
- **Minimal fix:** `zlib.decompressobj().decompress(bytes(idat), max_length=expected_decoded + 1)`; reject if any bytes remain.

### P2 — Windows Job Object attach-failure fails open to a non-authoritative PID-walk while `descendant_cleanup_verified` is reported `True`
- **Where:** `create_windows_kill_job()` returns `None` on failure (`:654-662`); `run_process` resumes/runs anyway (`:982-989`); the `job is None` fallback uses the ppid-BFS snapshot (`:841-846`, `:733-741`) which cannot reach an orphan re-parented after its intermediate parent exits; `descendant_cleanup_verified=True` set unconditionally (`:1322` codex / `:1328` claude); **no receipt field records the containment mode.**
- **Impact:** In the (uncommon on Win8+) attach-failure case a detached grandchild can survive uncleaned and unreported, yet the receipt asserts verification. Low reachability caps it at P2.
- **Minimal fix:** Add `containment: "job-object" | "snapshot-fallback"`, gate `descendant_cleanup_verified` on the Job path (or fail closed when `job is None`), and propagate into route/artifact closure.

### P2 — PNG "no metadata" is a 5-item denylist, not an allowlist
- **Where:** `artifact_manifest.py:26` (`METADATA_CHUNKS` = tEXt/zTXt/iTXt/eXIf/iCCP only), `:139-140`, `:156-157`. An unknown ancillary chunk with a valid CRC passes silently.
- **Impact:** Arbitrary hidden bytes can ride inside an "accepted" PNG past the "no metadata" control.
- **Minimal fix:** Allowlist `{IHDR, PLTE, IDAT, IEND}` (+`tRNS`/`gAMA` if needed); reject anything else unless `--allow-metadata`. Reject `acTL`/`fcTL` outright (also fixes AR-3 below).

### P2 — Reserved raw-flag guard bypassable via clap attached short/config forms
- **Where:** `start_codex_session.py:47-51, :1116-1119` — the check does `raw_arg.split("=",1)[0]`, so `-sworkspace-write`, `-ckey=value`, `-Cdir` are not recognized as reserved `--sandbox`/`--config`/`--cd`.
- **Impact:** With raw passthrough on, a raw arg can contradict a launcher-controlled flag the receipt claims to own. **Mitigant:** triple-gated behind `--allow-raw-codex-arg` + `--allow-unsafe` + `--unsafe-reason`.
- **Minimal fix:** Normalize short-flag prefixes before the check, or allowlist permitted raw args.

### P3 — Robustness / hygiene cluster (all CONFIRMED unless noted)
- **Double `CloseHandle`** on the Job handle when `NtResumeProcess` fails: `:893-907` then `:983-989`. Error-path only. *Fix:* set `job=None` after `stop_process`.
- **Job-handle leak / resumed-child abandonment** if a reader `Thread.start()` raises between resume and `try/finally` (`:983-1010`). Very narrow.
- **Mailbox validate-then-hash TOCTOU + unguarded route re-read:** `mailbox.py:282-315` validates then hashes without pinning bytes; `mailbox_route_receipt.py:141-143, :196-197` re-reads and embeds unpinned `prompt`/`final` into closure. *Fix:* hash the exact validated fd; echo only validated fields.
- **APNG accepted when `acTL` num_frames==1** (`artifact_manifest.py:135-138, :154-155`).
- **`close()` never binds the generation prompt to the approved design spec** (`artifact_route_receipt.py:129, :138-139`).
- **`write_json_atomic` nlink==2 window / fails on hardlink-less FS** (`mailbox.py:206-224`); **`write_json_fresh` `exists()`+`os.replace` race** (`mailbox_route_receipt.py:46-57`). PLAUSIBLE; single-writer scope mitigates.
- **`utc_now_iso()` deprecated `datetime.utcnow()`, dead code** (`mailbox.py:48-49`).
- **Timing-flaky test** `test_child_stdin_is_closed_even_when_parent_stdin_is_open` (rc124 under load). *Fix:* raise its target timeout / split slow tests.

---

## 2. Claims that should be narrowed

The doc set is exceptionally well-hedged. Only these need tightening:

1. `README.md:13` "process-tree containment", `:16` "no surviving descendants", `verification.md:39` "Remove the fast-child containment race" — narrow to "kill-on-close Job Object containment **when available, with snapshot fallback**" (matching the correct hedge already at `threat-model.md:120` / `verification.md:48`) and add the containment-mode receipt field.
2. `README.md:19` "passed signature/CRC/decompression/… checks" — decompression correctness is validated but not resource-bounded (P2 bomb); fix or add the caveat.
3. `README.md:19` "metadata" check is a denylist — narrow to "rejects known metadata chunk types."
4. Tamper-evidence for the **bare write-capable launcher**: the parent-authored summary is itself forgeable there (sharper than "raw receipts are writable"). State explicitly or enforce non-predictable/external capture.
5. "187 tests passed" is load-sensitive (one timeout-bound test flakes under CPU pressure).

---

## 3. Missing tests

**Phase 1 (blockers before an honestly-labeled private beta / public prototype):**
- Decompression-bomb reject for `inspect_png` (+ the bounded-decompress fix).
- Windows Job Object **attach-failure** path: fails closed OR is honestly recorded (both launchers). *(Existing `test_job_object_ignores_recycled_historical_pids` is over-mocked — never exercises the `job is None` fallback.)*
- Forged-temp test: a write-capable child renaming over the predictable `events` temp cannot yield a clean "succeeded" summary (after the random-suffix fix).
- `os.replace` defeats a pre-created **symlink** at a receipt final name (only the hardlink variant is covered).
- *(Already covered: concurrent-writer mailbox (8-writer rounds); config-error receipt cannot land in a control dir; hardlink-break-before-overwrite.)*

**Phase 2 (enterprise, not blockers):**
- POSIX containment parity (`killpg` leak detection; `setsid()` escape) — all containment tests are currently `skipUnless(nt)`.
- Fuzzed PNG corpus (truncated chunks, trailing bytes, APNG frames, interlace, non-8-bit, oversized dims, hardlink/reparse artifact).
- Property-based mailbox concurrency / many interleaved responses.
- Malformed `config.toml` strict-isolation fail-closed (`start_codex_session.py:510-517`).
- `prepare_tracked_snapshot` size/aggregate-limit + submodule(gitlink)-mode reject.
- Signed/notarized receipts + tamper-detection; seccomp/AppContainer/job-memory-limit enforcement.

**Existing controls that are Phase-2 requirements, not Phase-1 blockers (#10):** NTFS ADS capture; hardlink/`file_id` identity; mid-route `executable_identity` re-verification; nested-plugin-MCP enumeration; the `.env/.key/.pem` denylist in `prepare_tracked_snapshot`. Keep them; they don't gate a beta. The full typed-PNG decoder is a legitimate Phase-1 control — only its missing decompression bound is a Phase-1 gap.

---

## 4. Additional considerations (not fully covered by this review)

These are angles this pass either under-weighted or could not exercise. Several are **more important for "broader use" than the code findings above.**

1. **Under-reviewed Phase-1 scripts.** The workflow deep-covered the launchers, mailbox, two-way route, and artifact route, but did **not** run a dedicated adversarial pass on: `scan_artifacts.py`, `prepare_tracked_snapshot.py`, `prepare_critique_handoff.py`, `critique_route_receipt.py`, `doctor.py`. The most important is **`scan_artifacts.py`** — it is the control that gates what becomes public and underwrites the token-audit's "0 findings." If it under-detects (base64/gzipped/line-split secrets, secrets in PNG pixels/metadata, URL- or JSON-escaped forms), the "safe to publish" story is weaker than it reads. `prepare_tracked_snapshot.py` is next: a bug there could leak an untracked `.env` or a tracked secret into a packet sent to a model.
2. **Workspace prompt injection is the biggest untested risk for broader use — and it's behavioral, not a code fix.** A poisoned `AGENTS.md`/`CLAUDE.md`/`.mcp.json` in a real (non-disposable) target workspace can instruct the target to exfiltrate, request broader tools, or write outside scope. The harness defends the *write* boundary and detects tool use, but read-only is not a confidentiality boundary. `verification.md:172` / backlog list "malicious-workspace probes" as **not yet done**; that gate matters most precisely when moving beyond disposable workspaces.
3. **Design-spec → image-prompt injection surface.** `prepare_artifact_handoff.build_prompt` interpolates free-text spec fields (subject/composition/palette/prohibited/provenance) verbatim into the Codex image prompt. The spec is structure/length-validated but its content is free text embedded in an instruction. Blast radius is limited by strict isolation + byte validation, but the design edge (Claude) authoring a malicious spec is a real injection path to name.
4. **Everything verified is Windows; POSIX is entirely unexercised.** All containment tests are `skipUnless(nt)`, and the P1 forgery is *cleanest* on POSIX. "Broader use" on Linux/macOS is essentially unproven — treat cross-platform as a first-class caveat, not a Phase-2 nicety.
5. **Provider-CLI version / schema drift.** Receipts record no target-CLI version. A `codex`/`claude` update can rename JSONL fields or add terminal event types and silently break fail-closed parsing (usually safe-but-broken; occasionally mis-parse-and-pass). Record the target CLI version in receipts and add a canary test against known-good JSONL shapes.
6. **Human-in-the-loop gates are only as strong as "a human, not the agent, invokes the closer."** `--visual-review-status passed` and the integration-approval step are CLI attestations; when an orchestrator drives Cairnspan "more broadly," an agent could supply them. Name this trust assumption explicitly.
7. **Cost is reactive and Codex is unmetered.** The aggregate-cost ceiling effectively bounds only the Claude edge; budgets are post-hoc; there are no per-day/provider caps. The learnings note a Claude `rate_limit_event` at 0.98 utilization. Matters for repeated/broader use (documented as Phase 2).
8. **No git history in this checkout.** `.git` is bare/empty, so "runtime artifacts are ignored" can't be verified against actual commits and there's no history to secret-scan before going public. `.gitignore` is present and correct, but a real history + `git log` secret scan is an operational pre-public step.

### Confidence & limitations of this review
- The P1 forgery rests on standard POSIX `rename(2)`-over-open-name semantics; the end-to-end PoC could **not** be run here because the host is Windows (where it is blocked). Every other link is verified in-repo or reproduced offline.
- Two findings are **PLAUSIBLE** (not fully reproduced): the process-lifecycle orphan-escape corner (F1) and the mailbox validate-then-hash TOCTOU (MBX-1). One verifier agent errored (the symlink-at-receipt-name test item, TC-3), leaving it UNVERIFIED — low value, since `os.replace` at final names is safe by construction.
- The offline suite was run once (186/187, 1 timeout-flake). No live provider path was exercised.

---

## 5. Residual risks (acceptable-by-design, worth naming)

- POSIX containment is untested and weaker (`setsid()` escapes `killpg`; no cgroups).
- Denylist raw-flag filtering: unlisted future dangerous provider flags would pass (all gated behind `--allow-unsafe`).
- Codex edge cost is structurally unmetered (`run_two_way_route.py:716-718`); the aggregate ceiling bounds only Claude.
- Executable-identity TOCTOU: a swap-then-restore across the edge window evades the before/after hash check (requires local write to the out-of-workspace binary dir).
- Trusted-skill-dir assumption: write access to `skills/cairnspan/scripts/` forges all receipts (outside Phase-1 boundary).
- Route/mailbox closers trust operator-supplied manifest JSON (no provenance binding).
- `--allow-outside-workspace-out-dir` only checks sensitivity against `cwd` (could steer into another repo's `.git`).
- By design the child inherits full `os.environ` minus `SENSITIVE_AUTH_ENV_VARS`, so it can reach on-disk OAuth stores — intentional for OAuth-backed delegation.

---

## Appendix A — Updated Codex continuation prompt

See the current handoff prompt maintained alongside this report (chat delivery of 2026-07-10). It implements the validated P1/P2/P3 fixes **and** closes the review-coverage gaps in §4 (adversarial pass on `scan_artifacts.py` / `prepare_tracked_snapshot.py` / `critique_route_receipt.py`; behavioral prompt-injection probes; POSIX containment + forgery tests; target-CLI version + drift canary; human-gate trust-assumption docs).
