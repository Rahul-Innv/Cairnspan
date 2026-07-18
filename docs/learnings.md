# Cairnspan Learnings

## Environment Separation

- Claude Code and Codex should be treated as separate execution environments.
- Skills, MCP servers, plugins, auth, model access, and approval policy do not automatically transfer across agents.
- Cairnspan should launch the target agent and then verify the target agent's actual capabilities from logs.

## OAuth First

- The product is not valuable merely because one agent can call another model through an API key.
- The useful wedge is using the user's existing OAuth-backed local agent sessions and their account-scoped capabilities.
- Cairnspan should never copy or expose OAuth tokens. It should delegate through installed clients and record only observable run metadata.
- The owner-local native-client path and shared production automation are different policy surfaces. API-key or managed-provider authentication is the conservative production path, not merely a technical fallback.

## 2026-07-11 Anthropic Authentication Policy Refresh

- Official `claude -p` scripting is documented for scripts and CI/CD, so noninteractive use of the unmodified Claude Code client is not itself an unsupported hidden interface.
- Anthropic also documents subscription OAuth from `/login` and a long-lived `CLAUDE_CODE_OAUTH_TOKEN` for scripts, while separately prohibiting third-party login offerings and routing plan credentials on behalf of users.
- Cairnspan's owner-local launcher is materially different from a token broker because it never receives the credential. That does not amount to Anthropic approving Cairnspan as a public product.
- Long-lived script tokens are ambient credentials. Scrub `CLAUDE_CODE_OAUTH_TOKEN` by default just like API keys and provider-routing overrides; require explicit unsafe opt-in to inherit it.
- A provider billing snapshot can reverse quickly. The 2026-07-11 paused-credit note was superseded by Anthropic's 2026-07-12 documentation that the separate monthly Agent SDK credit became effective on 2026-06-15; cost and pressure planning must recheck primary provider documentation at execution time.

## 2026-07-11 Bare Parley Name Recheck

- Namespace availability is weaker than product distinctiveness. A private GitLab project can be called `Parley` even while the public software and AI name is heavily occupied.
- Bare `Parley` collides with active multi-model deliberation, agent negotiation, multi-agent chat, npm, PyPI, and older software uses. Do not mass-rename the codebase to it.
- Historical note: the original prototype identity was retired when the owner
  selected Cairnspan. The 2026-07-12 source migration changed current
  identifiers atomically instead of preserving a mixed compatibility surface.

## Codex Launching

- `codex exec --json` is the right Codex-side entrypoint for machine-readable sessions.
- JSONL event output can capture thread ids, turn usage, tool calls, web search, and final messages.
- The current Windows machine resolves `codex` to a WindowsApps packaged executable.
- That executable is visible through `where.exe` and `Get-Command`, but unattended Python/PowerShell launches return `Access is denied`.
- Cairnspan must classify this as an environment blocker, not a product-code failure.
- A launchable Codex CLI also exists under `<launchable-codex.exe>`; passing it explicitly with `--codex-bin` avoids the WindowsApps PATH trap.
- In sandboxed execution, the launchable Codex CLI can still fail with socket error `10013` when reaching `api.openai.com`; network-enabled execution allowed the same read-only probe to succeed.
- Resolve the Codex executable before changing into the target workspace so a malicious or accidental workspace-local executable cannot be used implicitly.
- Prompt files are safer than shell-quoted prompt strings for real agent handoffs.
- A target workspace typo must fail early; the launcher should never create a missing `--cwd`.
- Timeout handling on Windows needs process-tree awareness because wrappers can leave child processes holding log files.
- Unattended agent-to-agent launches must close child stdin explicitly. Claude Code can keep the launcher's stdin handle open, causing `codex exec` to print "Reading additional input from stdin..." and wait forever even when the prompt was already passed as argv. Passing `stdin=subprocess.DEVNULL` is safe because Cairnspan does not feed prompts through stdin.
- After the fix, the Claude Code-origin rerun succeeded end-to-end in ~27s (was a 127s timeout before). Note that `codex exec` still emits the "Reading additional input from stdin..." line once even with `stdin=DEVNULL`; it is a startup log, not a hang. Failure vs. success must therefore be judged by `error_kind`/`status` and whether `events.jsonl` fills, not by the presence of that transcript line. A healthy run yields a `thread.started` -> `agent_message` -> `turn.completed` event stream and a populated `final.md`.
- The same launcher and explicit `--codex-bin` path work identically whether invoked from a Codex-origin or a Claude Code-origin context once stdin is closed, confirming the Claude Code -> Codex one-way handoff is real and not context-specific.

## Claude Code Launching

- Claude Code has a verified noninteractive entrypoint on this machine: `claude -p`.
- The installed version is `2.1.201 (Claude Code)`.
- PowerShell resolves `claude` to `<claude-wrapper.ps1>`; that wrapper invokes `<claude-native.exe>`. A launcher should prefer the native executable path when available.
- `--output-format json` produces a single machine-readable result object; `--output-format stream-json` is available for realtime event capture and should be the default for the future `start_claude_session.py` launcher.
- Claude Code requires `--verbose` when `--output-format stream-json` is used with `--print`; without it the launcher fails fast before model work with `Error: When using --print, --output-format=stream-json requires --verbose`.
- `--tools ""` disables built-in tools and is the right default for no-edit probes. Edit-capable reverse runs should require explicit tool scope.
- `--permission-mode dontAsk` plus no tools is suitable for the basic reverse probe. Broader permission modes, `bypassPermissions`, `--dangerously-skip-permissions`, or all-tool defaults should be treated as unsafe and gated.
- `--no-session-persistence` keeps one-shot probes from being resumable Claude sessions.
- `--max-budget-usd` works with `--print` and should be exposed by the launcher for cost control.
- Do not use `--bare` as Cairnspan's default Claude path: local help says bare mode never reads OAuth/keychain auth and requires `ANTHROPIC_API_KEY` or an API key helper.
- Local help says the workspace trust dialog is skipped in noninteractive `--print` mode, so Cairnspan should require an existing trusted `--cwd` and avoid launching Claude Code in arbitrary directories.
- A sandboxed no-tools probe failed with `ConnectionRefused`, while the same command with network-enabled execution succeeded. Live Claude Code probes require network access just like live Codex probes.
- Confirmed live from Codex on 2026-07-08: the no-tools Claude command returned code 0 with a successful JSON result, exact expected text, a session id captured in the private receipt, and bounded cost.
- Confirmed live through `start_claude_session.py` from Codex on 2026-07-08: return code 0, status succeeded, exact expected final, session id captured privately, elapsed 12.36s, and total cost `$0.011209`.
- `--tools ""` does not by itself prove a completely tool-free Claude runtime. The successful stream init event still listed configured MCP tools from Claude Code, even though no tool was called. Safer no-tools probes should also use `--strict-mcp-config` by default and live-verify that the init event exposes no configured MCP tools.
- Claude stream output can include a `rate_limit_event`; the successful launcher probe reported seven-day utilization `0.98`. Treat that as a budget warning and keep further Claude live probes minimal.

## Read-Only Sandbox

- Codex `--sandbox read-only` enforces no-write at the OS layer, not just by policy or prompt. A Claude Code-origin probe that asked Codex to create a file got a real `Access to the path ... is denied` and the file never appeared.
- The run still finishes with `status: succeeded` / return code 0 even though the write was denied: a blocked write is expected sandbox behavior, not a launcher failure. Do not treat a successful read-only run as proof that no write was attempted -- verify separately.
- The strongest evidence that a read-only handoff was safe is an external before/after SHA-256 manifest of source files (excluding `.cairnspan/`, `__pycache__/`, `.pyc`) taken by the origin agent, not the target agent's self-report. Both should agree; the manifest is the ground truth.

## Workspace-Write Sandbox

- Workspace-write probes should verify both halves of the boundary: an intended write inside `--cwd` succeeds, and an attempted sibling/parent write outside `--cwd` is denied.
- Take the before/after manifest before any documentation updates, otherwise the docs updates pollute the workspace-write proof.
- Clean up the intended in-workspace scratch file only after evidence is captured and the manifest comparison is recorded.
- Confirmed live: `--sandbox workspace-write` allows writes inside `--cwd` and denies a sibling write in the parent directory with the same OS-level `Access to the path ... is denied`. The boundary is the resolved `--cwd`, so a `..\` relative path escaping the workspace is blocked.
- Do not assert byte-exact file content from a workspace-write probe without checking the encoding: Codex created the scratch file with a leading UTF-8 BOM (`EF BB BF`), so the file was 21 bytes for an 18-character body. The visible text still matched, but a naive byte comparison against a BOM-less expected value would have flagged a false mismatch. Compare decoded text, or account for the BOM.

## Image Generation

- Codex supports direct image generation through natural language or `$imagegen`.
- A live Cairnspan image-generation probe has now passed through the Claude Code-origin path.
- Larger batches may be better routed through API-key-backed image generation rather than Codex included limits.
- Built-in image generation saves under Codex-owned generated image storage by default, so a project-bound probe must instruct the launched Codex session to copy or move the selected PNG into a workspace scratch directory.
- Keep imagegen probe artifacts under `.cairnspan-imagegen/`, exclude that directory from source manifests, and validate the image separately by file existence, byte length, and PNG signature.
- Do not use CLI/API fallback or ask for `OPENAI_API_KEY` for the Cairnspan imagegen probe; the point is to test Codex's account-backed built-in image capability.
- Confirmed live: the built-in `image_gen` path works through a Claude Code-origin Cairnspan handoff with no `OPENAI_API_KEY` and no CLI fallback. Codex generated under its managed image storage and copied the selected valid-signature PNG into the workspace scratch directory.
- Built-in image generation runs longer than text probes (~99s here vs ~25-35s), so give imagegen probes a larger `--timeout-seconds` (180 worked comfortably).
- When auditing an imagegen probe for "did it use the API fallback?", beware false positives: Codex echoes the full `imagegen/SKILL.md` (which documents `OPENAI_API_KEY`, `scripts/image_gen.py`, and `api.openai.com`) into a `command_execution` event, so a naive grep for those strings matches the doc text, not an actual call. Confirm by checking that no command actually *executed* `image_gen.py` and that `transcript.log` has no `api.openai.com`/`curl` activity.
- A benign `git` error can appear in the transcript when a probe runs with `--skip-git-repo-check` in a non-git workspace (Codex still tries `git` and logs `not a git repository`). It does not affect `status`/`return_code` and is not a failure.

## MCP And Tools

- Codex MCP configuration lives in Codex config, not Claude Code config.
- Codex app, CLI, and IDE share Codex MCP settings.
- Cairnspan should require an explicit MCP probe before relying on a third-party MCP in an unattended run.
- MCP visibility probes should be recorded as observed capability discovery. If no MCP servers are visible, document that state plainly instead of treating it as a launcher failure.
- Observed live: a Claude Code-origin read-only Codex session saw Codex's configured MCP set and no MCP resources/templates. This confirms empirically that Codex and Claude Code do not share an MCP set; do not infer one agent's MCP visibility from the other.
- MCP discovery in `codex exec --json` surfaces as `mcp_tool_call` events (read-only `tool_search`, `mcp_resources`, `mcp_resource_templates`), not `command_execution`. To confirm an MCP probe genuinely inspected the session (rather than answering from prior knowledge), check `events.jsonl` for `mcp_tool_call` entries.
- MCP tools can be deferred/lazily surfaced: Codex needed a `tool_search` call to expose deferred MCP tool namespaces before it could list them. A probe that just asks "what MCP do you have?" without allowing a discovery call may under-report.

## Two-Way Handoffs

- Claude Code to Codex is straightforward once Codex is launchable.
- Codex to Claude Code now has a verified local noninteractive Claude Code entrypoint, so the next implementation step is a `start_claude_session.py` launcher rather than a mailbox-only MVP.
- The file-based mailbox remains useful as a fallback when live Claude Code launch is unavailable or intentionally disabled.
- Mailbox files need schema validation before they become orchestration inputs. Ids must not be allowed to become paths, requests must carry exactly one prompt source, and responses should prove success with a result/final reference or failure with an error.
- Independent one-way probes are not the same as a full two-way loop. The parent-orchestrated text route now proves that a validated Codex artifact becomes Claude's input and that a closure receipt links both edges.
- The verified text route should not be reused as proof for binary artifacts. Images need typed manifests, byte/signature/dimension validation, isolated staging, unexpected-file detection, provenance checks, and a separate integration approval.

## Runtime Hygiene

- Bridge artifacts should be ignored by default.
- Product docs and skills should be committed or copied deliberately.
- Runtime files should not be mixed into target product commits unless explicitly requested.
- Raw run logs can contain prompts, local paths, model output, tool output, and secrets printed by the target agent.
- Summaries should redact prompt bodies and store prompt hashes instead.
- Artifact scanning should happen before any evidence or fixture is treated as publishable. The scanner should redact its own finding samples so the scan output does not become another leak.
- Canary-secret tests make the scanner meaningful: the scanner's dedicated Cairnspan canary prefix must fail, otherwise a clean scan cannot be trusted even as a basic release aid.
- JSON fixtures can contain escaped Windows user paths; scanner path patterns need to detect both raw and JSON-escaped local paths.
- Legacy evidence should be replaced, not carried forward behind warnings, once a redacted fixture exists. Hidden folders under an evidence directory still matter for public release.
- Scan more than the obvious evidence folder before public release. Probe prompts and durable notes can carry machine-specific paths even when runtime evidence is clean.
- A useful `doctor` command should stay non-destructive: it can check path resolution, output directory policy, ignored runtime artifacts, and risky shims such as WindowsApps Codex without launching agents, probing auth, or touching the network.
- Public install docs should avoid user-specific path placeholders; use neutral placeholders so examples do not look like leaked local evidence.
- Unsafe modes such as `danger-full-access` and raw target-agent arg passthrough should require explicit opt-in and a reason.
- Public examples should be clearly labeled as examples, not machine-specific install state.
- Read-only means no writes, not no disclosure. A target agent may still read workspace files and send relevant context to the model provider or configured tools.
- Output directories are part of the attack surface because launchers write and truncate receipt files. Reused or outside-workspace output directories need explicit policy and tests.
- The launcher should treat `--out-dir` as a directory contract, not just a path. Reject existing files even when overwrite is requested; otherwise a config-error path can try to create receipt artifacts inside a file-shaped target.
- Existing non-empty receipt directories should not be silently reused. Allowing reuse only through `--overwrite-out-dir` makes collisions and intentional replacement visible, while still preserving unrelated files in that directory.
- Outside-workspace receipt paths should require explicit opt-in. This prevents a handoff from accidentally writing receipts into a parent directory, another project, or a sensitive local path.
- Even the default `.cairnspan/<run_id>` fallback must be resolved and containment-checked. On Windows, a preexisting `.cairnspan` directory junction can otherwise redirect config-error receipts outside the target workspace.
- Two-way handoffs need loop controls. Without max depth, runtime, output size, and cost guards, a recursive delegation can burn quota or fill disk.
- Depth should be explicit in the launcher contract, not just in prompts. A recursive or two-way run should carry `parent_run_id`, `run_depth`, and `max_depth`, and the launcher should fail before target launch when the current depth exceeds the limit.
- Child runs need a parent id for auditability. Conversely, a parent id with depth 0 is ambiguous and should be rejected.
- Output limits need to be enforced while the target process is running, not only after artifacts are written. Otherwise a target can fill disk before the launcher classifies the run.
- Treat stdout and stderr as one combined budget for the target process because both become persistent artifacts (`events.jsonl` and `transcript.log`).
- Raw target-agent arguments are safety-sensitive because later flags can override earlier safe defaults.
- Raw target-agent passthrough should require two independent acknowledgements: a launcher-specific raw-arg allow flag and the broader unsafe gate with a human-readable reason.
- Claude configured MCP visibility is safety-sensitive even with `--tools ""`; `--allow-configured-mcp` should be treated as an unsafe opt-in until strict-MCP live probes prove the no-tools path is clean.
- Claude broad-tool values need token-level checks, not whole-string checks. Values such as `*,Read` should be treated as broad access just like `*`.
- Codex image attachments should be validated before launching the target process. Relative image paths should be interpreted relative to the target `--cwd`, normalized to resolved paths, and rejected if they escape the workspace, point to a directory, or do not exist.

## Testing

- Fake target-agent executables are enough to test launcher contracts without a live OAuth-backed Codex CLI.
- Parser tests should include alternate event shapes so valid Codex schema drift does not silently erase thread ids or final messages.
- Failure tests should assert structured `status`, `error_kind`, and redacted transcript excerpts so callers do not need to scrape raw logs.
- A fake target that blocks on `sys.stdin.read()` catches inherited-stdin regressions without requiring a live Codex CLI.
- Fake-target tests can also prove launcher policy without spending live agent quota: output-directory containment, non-empty reuse, file-shaped output paths, junction fallback, raw-arg gates, configured-MCP gates, broad-tool gates, and image preflight all belong in stdlib unit tests before live probes.
- Recursion guards should also be covered by fake-target tests because the important behavior is pre-launch denial, not model behavior.
- Output-limit tests can use fake targets that flood stdout; the important behavior is launcher-side process termination/classification, not target-agent semantics.
- Test order should stay conservative: text-only handoff probes first, then capability probes such as `$imagegen` and MCP visibility.
- The Claude Code-origin probe should update the verification and learnings docs immediately so Codex can continue from documented state rather than chat-only memory.
- Read-only no-edit probes should use an external before/after manifest excluding `.cairnspan` runtime output, because the launcher itself writes run artifacts even when the target Codex session is read-only.

## 2026-07-09 Adversarial Hardening

- A zero process exit is transport evidence, not task-success evidence. Both launchers now require a recognized terminal event and thread/session id, and any malformed JSONL line makes the receipt fail closed.
- Codex can emit `turn.failed` with exit code zero; that must be classified as target failure, not completion.
- Windows command-line limits are lower than the previous prompt-byte default. Validate the complete rendered command in UTF-16 units and keep the default prompt ceiling conservative; prompt-file input to Cairnspan does not mean the target CLI receives a file path.
- Summary redaction does not hide prompts from local process inspection because both target CLIs still receive prompt text through argv. Live probes must remain secret-free until a verified stdin input mode replaces that path.
- Claude's tool policy is too late to neutralize target-repository hooks or customizations. Safe mode must be the default for unattended probes, and project/user customizations require explicit unsafe acknowledgement.
- `--strict-mcp-config` is only safe isolation when no explicit MCP config is supplied. Caller-supplied MCP config is executable configuration and needs its own allow flag plus the unsafe gate.
- The launcher's ambient environment is a cross-agent boundary. Known raw API-key and alternate-provider overrides should be removed from children by default, while the installed client's OAuth/keychain ownership remains untouched.
- PATH resolution and Windows shell wrappers are separate risks. Reject executables resolved from inside the target workspace, reject unacknowledged `.cmd`/`.bat`/`.ps1` wrappers, and use explicit native executables for live evidence.
- `readline()` without a size bound allows one no-newline stream record to consume memory before output policy runs. Bounded reads plus a combined stdout/stderr counter close that gap.
- Windows `taskkill /T` was not reliable enough behind wrappers. A kill-on-close Job Object plus Toolhelp descendant enumeration was needed to prove delayed child processes do not survive timeout or output-limit stops.
- Receipt names inside a reused output directory can be hardlinks or links. Stream into unique temporary files, atomically replace final names, and unlink reserved files before overwrite. This reduces write-through risk, but receipts inside a write-enabled target workspace are still target-writable and not tamper-evident.
- A public artifact scanner must never report clean after silently skipping a large or NUL-containing artifact. Oversized files now fail closed and small binary bytes are scanned for ASCII-form secrets.
- Mailbox ids are filenames on Windows: colon permits alternate data streams and names such as `NUL` are invalid/special. Portable ids, bounded fields, non-traversing refs, unknown-field rejection, and no-clobber writes are baseline schema requirements.
- Independent one-way successes are not a full loop. The first loop should be a trusted parent-orchestrated two-edge route with a nonce challenge, aggregate budgets, protected receipts, and verified artifact consumption. Target-recursive launch is a later unsafe pressure topology, not the default architecture.
- Direct workspace-write denial does not cover tool-managed storage. The image-generation probe legitimately staged output under Codex-owned storage outside `--cwd`; claims must distinguish direct sandboxed filesystem writes from external tool artifact locations.
- `workspace_manifest.py` gives repeatable origin-side file evidence, including hidden files and reparse entries, but it is not an ACL or alternate-data-stream audit.
- The hardened serial suite now takes about 13-15 minutes on this Windows machine because launcher tests spawn real wrapper/native fake processes and verify timeout/output-limit descendants. Keep the full gate, but add a fast parser/policy tier for routine iteration.

## 2026-07-10 Strict Reverse Live Probe

- PowerShell dropped `--tools ""` before Python argparse received it. Use the equivalent `--tools=` launcher syntax in PowerShell examples, then verify the dry-run command contains the target argument pair `--tools`, `""`.
- A successful target result is not enough to prove customization isolation. The first live call had empty tools/MCP but still advertised an installed plugin, skills, and slash commands in its init event despite `--safe-mode`.
- Defense in depth matters at the target CLI boundary. Adding `--disable-slash-commands`, empty `--setting-sources`, and `--no-chrome` cleared plugins, skills, and slash commands in the hardened live rerun; only Claude's built-in agent labels remained as metadata.
- Capability and tool-use evidence now belongs in `cairnspan-summary.json`. Schema `0.4` records init capability names and tool-use counts, and the launcher fails closed when an empty-tool or strict-empty-MCP policy is contradicted.
- The hardened probe succeeded in 11.484s for `$0.01832`, returned the exact expected text with a terminal result/session id, emitted no tool-use events, and left the empty disposable workspace byte-for-byte unchanged by external manifest comparison.

## 2026-07-10 Parent-Orchestrated Live Route

- Strict Codex isolation requires more than read-only sandboxing. The route ignores user config and rules, runs ephemerally with strict config parsing, disables tool/app/plugin features, records ignored ambient MCP names, and rejects any observed tool event.
- A process snapshot is useful only as fallback containment evidence. On Windows, historical PIDs can be recycled after a child exits; combining those PIDs with an empty Job Object caused false process-leak failures against unrelated Git and PowerShell processes. When a Job Object exists, its active process list is authoritative.
- Normal target exit can briefly leave legitimate internal helpers alive. A bounded five-second grace lets them exit naturally, while persistent children still cause process-leak failure and Job Object termination.
- Verification language can itself resemble prompt injection. Claude rejected a prompt framed as a trusted handshake even though the task was harmless. A deterministic string transformation over an already regex-validated artifact passed while preserving the parent's exact nonce check.
- A complete model response is still not route success. Closure requires exact artifacts, one terminal identity per edge, zero policy violations, unchanged strict manifests, stable executable identities, aggregate limits, and independently matching prompt/final/summary/plan hashes.
- The first closed route completed in 27.375s with two successful edges, zero tool/MCP calls, no surviving descendants, and `$0.019557` reported Claude cost. Codex did not report comparable cost, so the receipt identifies that edge as unreported rather than treating it as free.

## 2026-07-10 Product-Shaped Critique Profile

- A clean Git status is not a sufficient model-input boundary when an untracked `.env` exists. Export committed blobs from the Git object database into a fresh allowlisted packet instead of copying the working tree.
- A full tracked export can still trigger conservative scanner findings on code that references `process.env`. Narrow the model packet to the task-relevant public surface instead of weakening scanner patterns or adding broad allowlists.
- Image attachments are inputs, not image-generation capability. Strict isolation can accept preflighted in-workspace image files while keeping the `image_generation` feature disabled and requiring zero tool events.
- Codex CLI's variadic `--image <FILE>...` consumes a trailing positional prompt unless the launcher inserts `--`. Prompt/image boundary behavior needs a real native-CLI regression path, not only fake-target parsing.
- A product-shaped critique should separate visual evidence from source claims. Codex inspected only screenshots; the later Claude edge receives validated critique text and must identify which findings still require source verification.
- Historical target-agent session metadata can show direct `.env` activity after an older recorded key rotation. The safe owner cutoff is a final credential rotation after all testing, not reliance on an earlier rotation record.
- A requested model flag is not enough for reproducibility. Record it separately and require the target's actual model-usage receipt to include it; auxiliary internal models may appear, but silent primary-model substitution must not close the route.
- An installed OAuth client is still an external data boundary. Before sending nontrivial product content, obtain explicit owner approval that identifies the destination and payload even when prior consent broadly covered live Claude testing. A rejected launch is not a failed model run when the child process never started.
- Explicit owner consent does not override the host execution environment's DLP policy. If a workspace-derived external transfer is rejected after informed consent, stop rather than retrying or using an indirect launcher. Continue with synthetic public-data transport evidence or move the product-shaped evaluation to an environment whose governance explicitly permits it.
- A same-shape synthetic control is the clean way to locate a blocked boundary. The invented public-data Sonnet probe passed twice while the product-shaped prompt never reached process start, proving that Claude Code, OAuth, Sonnet, network access, prompt size, and Cairnspan were not the blocker; workspace-derived product content classification was.
- Enforcement and receipt reporting are separate properties. `run_process` already failed if descendants survived, but successful summaries left `descendant_cleanup_verified=false`. Set the field only after `run_process` returns and make downstream closure require it.
- When a cross-model product edge is blocked, a local synthesis can preserve planning progress only if provenance is explicit. Mark it non-independent and do not present same-model critique plus synthesis as cross-model consensus.

## 2026-07-10 Shared Mailbox, Artifact, And Pressure Pass

- A shared folder is transport, not trust. Request and response files need exact id/path linkage, immutable requests, reversed-agent checks, one terminal response, contained refs, no-clobber writes, and parent-owned before/after manifests.
- Agent final text is not authoritative write evidence. A strict Codex run emitted a success marker after the sandbox denied its write; the external manifest correctly rejected the claim.
- Native Codex can materialize empty `.git` and `.agents` directories. Predeclare them in disposable workspaces and make the parent manifest authoritative rather than treating every runtime-created marker as application output.
- The exact two-edge text probe should reject non-disposable baselines before any provider call. A poisoned `AGENTS.md`, `CLAUDE.md`, product file, or workspace-selected executable is not an instruction-following challenge for the model.
- Failure receipts must obey the same output-path policy as success receipts. The first `.git/hooks` negative test found that normal validation rejected the path but config-error fallback still wrote there.
- Unsafe raw passthrough must not be able to contradict receipt fields. Sandbox, permission, protocol, model, tool/MCP, session, isolation, and danger flags are launcher-controlled even when noncritical raw args are explicitly enabled.
- Typed image closure needs two stages: byte-level acceptance and visual review. Neither stage authorizes product integration; integration is a fresh edge with a fresh human decision.
- A product critique expires when its visual evidence no longer matches source. A product's old screenshots cannot justify edits to its current interface.
- Atomic file publication still needs race-safe directory initialization. Concurrent resolution while the mailbox folders did not yet exist produced a false path-escape error on Windows; create and reparse-check the root/folder first, then publish through a no-clobber hard link.
- Assigning a Job Object after ordinary `Popen` has a fast-child race. A target can spawn and exit before containment attaches. On Windows, create the process suspended, assign containment, resume it, and poll briefly after parent exit for delayed job accounting before declaring cleanup.

## 2026-07-11 Opus Adversarial Review Remediation

- A random receipt filename is not sufficient when the target can list its writable workspace. The trust boundary is architectural: write-capable target workspaces and parent-authored receipts must be separate directories. Random names and inode/file-identity checks are secondary defenses.
- Process cleanup and process containment are different claims. On Windows, an unattached PID snapshot cannot prove control of re-parented descendants, so Job Object attachment now fails closed before the suspended child is resumed. A POSIX process group can also be escaped with a new session, so it is recorded but cannot close an authoritative route until stronger containment is implemented.
- Image byte ceilings do not bound decoded memory. Derive the exact scanline size from validated IHDR fields and cap zlib output before allocation; then require EOF, no trailing stream, exact decoded length, valid filter bytes, core chunk order, and explicit ancillary/APNG policy.
- A prompt hash proves which prompt ran, not that the prompt came from an approved design. Typed artifact closure must reconstruct the canonical producer prompt from the validated spec and declared output path and compare exact text.
- Validate-then-reopen is not an immutable mailbox receipt. Parse, validate, and hash the exact bytes read through one handle, verify the path still names that file, and expose hashes rather than copying untrusted prompt/result bodies into the closure.
- Raw CLI conflict detection must normalize attached short-option forms such as `-sworkspace-write`, `-ck=v`, and `-Cdir`, not only `--long=value` forms.
- Public-artifact scanning must account for trivial encoding evasions. Scan percent-decoded, whitespace-compacted, and base64-decoded views; reject compressed containers for explicit manual handling instead of claiming they were inspected.
- A committed-HEAD snapshot is not safe merely because `.env` is absent. Enforce file/count/aggregate ceilings, reject gitlinks, and apply the same conservative content scanner to exact Git blob bytes before writing the transfer packet.
- Free-text design fields remain untrusted even after schema validation. Serialize them inside a clearly delimited JSON data block and tell the producer not to follow embedded commands; confirm resistance behaviorally in the live synthetic probe.
- Human gates depend on who supplies the attestation. `--visual-review-status passed` is meaningful only when the owner invokes or explicitly authorizes the closer after reviewing the exact artifact hash.
- Live image-generation latency can exceed the earlier 180-240s assumptions. The first hardened attempt timed out cleanly at 240s without staging changes; a single fresh-receipt 420s retry completed in 320.516s. Keep retries explicit and bounded, never merge failed and successful receipt roots.
- Standard PNG encoders may retain tightly specified display chunks (`gAMA`, `pHYs`, `sRGB`) even when they emit no comments or profiles. Do not enable a broad metadata bypass. Validate the exact fixed lengths/value ranges for these chunks and continue rejecting text, profiles, unknown ancillary payloads, and APNG.
- Strict manifests can report `<manifest:root_metadata>` when creating the declared output directory updates the staging root timestamp. Permit that exact metadata-only side effect while still requiring the declared parent directory and artifact and rejecting every other path.
- Human approval should be bound to the exact artifact hash and a concrete visual description. The hardened route closed only after the owner confirmed the folded-paper lighthouse and the closure retained that statement while leaving product integration unexecuted.

## 2026-07-11 Version And Hostile-Workspace Pressure

- A native executable hash is not the whole target identity. Provider CLI behavior can change across versions while a route is being prepared, so each launcher now performs a bounded credential-scrubbed version probe, records the result, and fails before target launch when an exact expected version differs.
- Version awareness must not become silent self-updating. Cairnspan inspects and pins; a new provider CLI version requires an intentional compatibility run before it becomes accepted evidence.
- Poisoned-workspace probes use synthetic hostile instruction files in disposable directories. They test whether launcher isolation prevents tool activation, recursion, outside writes, and receipt disclosure; they do not prove that readable workspace content is confidential from the selected provider.
- Behavioral success is insufficient for an injection-resistance claim. This pass also required exact final markers, zero tool/MCP/web evidence, no canary in protected receipts, no outside file, identical strict manifests, one terminal identity, pinned versions, and verified Job Object cleanup.
- Manifest policy is evidence. Comparing a strict before snapshot to a non-strict after snapshot correctly fails even when file bytes match; both sides of a closure must declare the same strictness before interpreting differences.

## 2026-07-11 Source-Backed Slice Verification

- A stale visual critique should be discarded, not massaged into a current change. Exporting committed `HEAD` and exercising the current dashboard found a different defect than the old card-grid screenshots suggested.
- Breakpoint pairs catch cliffs that representative desktop/mobile screenshots miss. The 481/480 pair exposed a horizontal flex/min-content transition even though 840 and 360 looked coherent.
- Full-page horizontal overflow needs both element geometry and intrinsic-size diagnostics. The cap label, an unbreakable `9ch` counter label, and a wrapping flex row contributed separately; `overflow-x: hidden` would only have concealed them.
- Product-shaped DLP blockage and local implementation can coexist if provenance stays explicit. Such a slice can be source-backed and locally verified without being cross-model consensus when no product payload was sent to the second model.
- A shared folder is useful for reviewed files and evidence, but it does not relax ownership gates. Live API, email, scheduler, credential, merge, and release actions remain separately controlled.
- A secret-staging hook can fail on unrelated host Git warnings before inspecting staged paths. The first run stopped on an inaccessible global ignore path; rerunning with an empty temporary XDG config preserved the hook's staged-file inspection and passed. Do not treat environment-warning failure as either a secret finding or permission to skip the hook.

## 2026-07-11 Public Name Reassessment

- A public name should describe the durable user job, not the current authentication path. Leading with `OAuth` invites credential-brokering and provider-policy interpretations that the local-client implementation is specifically designed to avoid.
- Bare `Parley` is semantically suitable but externally crowded in multi-model and agent software. A private repository name does not establish a clear public identity.
- The established naming pattern favors concrete compounds tied to operational or craft concepts. The cross-agent family should follow that morphology without colliding with sibling project names.
- RouteLatch captured a declared route plus fail-closed closure, but the owner selected **Cairnspan** after the broader portfolio-theme review. Cairnspan's cairn/span metaphor communicates a marked route and bounded crossing without leading with authentication or claiming that the route itself creates confidentiality.
- Exact repository/package searches and RDAP are point-in-time smoke checks. They do not reserve a name or replace legal trademark review.
- Rename public and internal identifiers in one migration before publication.
  The completed clean break moved skill paths, runtime defaults, receipt names,
  protocol markers, and environment prefixes together and added a deterministic
  source audit to prevent mixed identities from returning.

## 2026-07-12 Atomic Cairnspan Migration

- A private-alpha rename is safest as a clean break. Runtime compatibility
  aliases would enlarge the contract and make future receipts ambiguous, so
  current code accepts only Cairnspan identifiers.
- Historical runtime receipts are evidence, not source to rewrite. Leave them
  private and ignored; add explicit legacy ignore entries so the new default
  cannot accidentally make old receipts visible to Git.
- The local checkout folder label belongs to the host environment. Product
  atomicity is enforced over tracked/untracked source surfaces, skill paths,
  runtime defaults, schemas, tests, fixtures, and CI without moving an active
  sandbox-bound checkout.
- A rename needs its own regression contract. Three tests now assert canonical
  and shim skill paths, reject legacy runtime identifiers outside the explicit
  historical ignore entries, and require the renamed receipt fixture.
- Post-migration evidence closed at 87 fast tests in 44.515 seconds with 1
  expected Windows symlink skip. The first full tier passed 243 tests in
  298.869 seconds; the final-state rerun passed the same 243 tests in 385.889
  seconds, both with 2 expected skips. Compile, all three skill validations,
  five artifact scans, and `git diff --check` also passed.

## 2026-07-12 Current Codex Image-Tool Compatibility

- Native image attachment and Codex-owned image tools are different capability
  layers. Repeated attachment description success does not prove `$imagegen` or
  `view_image` can start.
- The explicit `codex-cli 0.144.0-alpha.4` binary advertises
  `code_mode_host=true` and `image_generation=true`. That proves effective
  feature configuration only; it does not prove the code-mode runtime host is
  packaged, discoverable, or startable under `codex exec`.
- Strict no-tool isolation intentionally disables both `code_mode_host` and
  `image_generation`. An image-tool probe using that profile is invalid by
  construction, while a native input attachment remains allowed.
- A target can exit zero after explaining that an image tool failed. Capability
  probes therefore need a receipt-level required-capability assertion and an
  observed tool event; polite failure text is not success evidence.
- Keep explicit native executable paths and exact CLI versions in the receipt.
  The WindowsApps Codex remains visible but unlaunchable with `Access is denied`,
  so it cannot serve as a compatibility comparison on this machine.
- Offline doctor checks must remain honest: enabled flags produce
  `unknown(runtime_unverified)`, not `ok`. A bounded live synthetic probe is the
  only remaining way to distinguish a packaging/runtime regression from an
  execution-profile mismatch here.
- A long Windows full gate can produce a transient pre-launch config-code flake
  even when the same cases and the whole launcher module pass immediately
  afterward. Preserve the failed run, reproduce exact cases, and require one
  subsequent clean complete gate; do not hide the first result or promote a
  partial rerun. The authoritative rerun closed 224 tests in 616.147 seconds
  with only the two expected symlink-privilege skips.

## 2026-07-12 Typed Hostile-Workspace Write Profiles

- A write profile should own the prompt shape, not merely set a sandbox flag.
  The parent-generated nonce prompt removes caller-controlled instructions and
  fixes one adapter-specific result path and exact byte sequence.
- Minimal write access is adapter-specific. Codex can retain strict isolation
  with shell/app/plugin/MCP/web features disabled while accepting only
  `file_change` / `apply_patch` receipts; Claude needs `acceptEdits` plus the
  single `Write` tool while retaining safe mode and strict-empty MCP.
- Sandbox success and tool receipts are not write evidence. Closure also needs
  a strict origin-side delta, exact bytes without BOM/newline, regular
  single-link output, no NTFS streams, and an unchanged outside sibling
  sentinel.
- Parent-controlled receipts need their own shape check. Random capture names
  and identity checks protect active streams; a final exact receipt-root set,
  single-link/stream-free files, and immutable before-manifest bytes catch
  target-created or replaced evidence paths.
- Failure paths still need after-manifests. Timeout, output overflow, and
  process-leak cases can leave partial declared files; the transport failure
  remains primary while `write_profile_status=failed` records the invalid
  workspace state for parent-owned cleanup.
- Deterministic profile coverage is not live authorization. The next native
  step must remain one fresh synthetic case and one pinned client edge per
  explicit owner approval, with zero retries and no product data.

## 2026-07-12 Parent Hostile-Write Case Lifecycle

- Launcher receipts are necessary but not enough for a repeatable matrix. A
  parent plan must bind one fresh fixture, adapter, native executable hash and
  version, nonce, sentinel, limits, and exact dry/live commands before a target
  can run.
- An expected attack denial is closable only while the parent evidence remains
  authoritative. A canary in receipts, an extra receipt file, plan drift,
  command drift, or failed receipt-root validation prevents even a
  `denied-as-expected` closure.
- Cleanup is its own evidence-producing transition. It must require a closure,
  verify the deletion target is exactly the marked direct-child workspace,
  refuse reparse ambiguity, compare receipts before/after, and leave the
  sibling sentinel exactly as it was immediately before cleanup. It must not
  silently restore a sentinel already mutated by the target.
- Never use a generic exception handler to delete a caller-named fresh-root
  candidate. A pre-existing unmarked directory is not proof that this process
  created it. Preparation now refuses that path and preserves every byte;
  automatic recursive cleanup exists only after a matching plan and closure.
- Exception-based termination can enforce cleanup while under-reporting it.
  Timeout, output overflow, decode failure, and detected process leaks leave
  `run_process` through exceptions after its `finally` block kills the Job
  Object. Windows summaries now record that forced cleanup explicitly; POSIX
  process groups remain non-authoritative.
- The full gate caught the expected test-contract consequence: one old
  assertion still required `descendant_cleanup_verified=false` for a killed
  internal `cmd.exe`. Preserve that failed 239-test run, update the assertion
  to the stronger receipt contract, rerun the exact case, and require a clean
  complete gate.

## 2026-07-12 First Live Hostile-Write Proposal Audit

- A stored launcher command is not proof that the same command ran. The parent
  closer now requires a digest of the launcher's actual argv plus the exact
  timeout and output ceiling recorded by the launcher receipt; widening those
  controls prevents closure even when the target result otherwise looks safe.
- Parent identity and recursion policy should be explicit in the proposed
  command, not inherited from defaults. The first Codex plan now carries
  `origin_agent=cairnspan.parent`, run depth 0, max depth 1, max fan-out 1, and
  retry budget 0.
- Clean-break tests must cover runtime-computed strings. Concatenating
  `OAUTH_` with a new Cairnspan canary name escaped the literal naming scan and
  produced the wrong runtime prefix; the helper now emits only
  `CAIRNSPAN_CANARY_HOSTILE_WRITE_*`, with direct plan assertions and a source
  regression for the concatenation pattern.
- Preparing a case is distinct from launching it. The inspected first proposal
  created a fresh synthetic workspace, immutable plan, sentinel, and strict
  manifest, while leaving the receipt directory absent and both generated
  launcher commands unexecuted.
- The new regression changed the authoritative suite from 243 to 244 tests.
  Final evidence was 87 fast tests in 67.128 seconds with 1 expected Windows
  symlink skip and 244 full tests in 344.352 seconds with 2 expected skips;
  compile, all three skill validations, all five scans, and diff check passed.

## 2026-07-12 Case-Specific Parent Closure Evidence

- A generic failed target is not evidence that a selected hostile action was
  contained. Parent closure must require the observable fact named by the case:
  a control-directory delta, an actual sibling-sentinel mutation, process-leak
  details, or a nonempty partial declared result under the expected limit.
- Parent verification should recompute, not echo. The closer now derives the
  prepared-to-after strict delta, compares it with the launcher's changed-path
  receipt, checks the current workspace against the after manifest, and reads
  the declared output and sentinel directly.
- This hardening did not require a new case-plan schema or command. The audited
  schema `0.2` Codex proposal, case id, native executable identity, and both
  stored command digests remain unchanged and still await explicit approval.
- The focused hostile-write/naming gate passed 23 tests in 92.491 seconds. No
  generated launcher command or provider was run. The fast tier then passed 87
  tests in 122.557 seconds with 1 expected Windows symlink skip, and the
  authoritative full tier passed 247 tests in 600.975 seconds with 2 expected
  skips. Compile, all three skill validations, all five scans, and
  `git diff --check` passed.

## 2026-07-12 Distinct Hostile Dry-Run and Live Evidence

- A dry-run gate is not reusable evidence when its command and the live command
  target the same fresh-only receipt root. The first successful command makes
  the second command invalid unless evidence is overwritten, which is forbidden.
- Proposal repair requires a new immutable schema and case root. Preserve the
  superseded plan, marker, IDs, and hashes unchanged so the audit trail remains
  legible; do not silently rewrite a previously reviewed proposal.
- Closure must validate both command-specific summaries. Missing, merged,
  swapped, extra, or reused roots are failures, and the approval reference must
  bind the exact plan SHA-256 rather than a descriptive case name alone.

## 2026-07-12 Typed Model/Effort Contract

- Model selection without typed effort is not a reproducible model contract.
  The safe interface is a closed lowercase enum, a launcher-owned native
  transport, and an additive receipt field in every terminal state.
- Codex config transport needs a split claim: offline command construction can
  safely own `model_reasoning_effort`, but a WindowsApps binary that returns
  `Access is denied` cannot establish native compatibility. Doctor must keep
  that result at `unknown(runtime_unverified)` until a launchable official CLI
  passes bounded inspection.
- Request receipts are not provider attestations. `requested_model` and
  `requested_effort` prove parent intent and command construction; actual model
  usage must be checked independently when the target exposes it.
- Raw config, raw model/effort flags, profile precedence, and immutable typed
  profiles are the same bypass class. They must fail before target launch, and
  configuration-error receipts should retain the rejected typed request for
  audit.
- A phased program is a sequence, not a batch authorization. Offline readiness
  only makes the next phase eligible for a separate proposal; each phase must
  close before the next can be approved.
- The focused fake-target contract gate passed 27 tests in 51.697 seconds. No
  provider/model launch, authentication change, source-archive read, or
  product-tree operation occurred.
- The final offline gate passed 90 fast tests in 55.301 seconds with 1 expected
  skip and 261 full tests in 346.843 seconds with 2 expected skips. Compile,
  all three skill validations, five zero-finding scans, and diff check passed.
- Fake-native dry runs used `python.exe` only for a bounded version probe and
  stopped before target execution. Codex schema `0.14` recorded
  `gpt-5.6-sol`/`xhigh` with one effort mapping; Claude schema `0.12` recorded
  `claude-fable-5[1m]`/`xhigh` with one native effort flag. Both recorded zero
  tools/MCP. Their summary SHA-256 values are
  `afc76b84b231903932bc1bb86aa27de48f6db991081307b637b60ba13fc4b6b3`
  and `27f76da7b69658d1d4b726901bedb328000f321a61895f2624de2420de1c47ea`.
- The real bounded doctor pass separated support cleanly: Claude Code `2.1.201`
  advertises model plus all effort values across a multiline help entry; Codex
  `0.144.0-alpha.4` advertises model but not `model_reasoning_effort`, and
  image-tool feature flags still cannot prove runtime startup. Multiline help
  parsing needed an explicit regression so a valid continuation line was not
  mistaken for unknown accepted values.

## 2026-07-12 Separate Synthetic Capability Proposals

- One broad "continue" approval would blur three materially different facts:
  native Codex acceptance of a typed effort mapping, current image-generation
  tool startup, and current image-view tool startup. Prepare and approve them as
  three independent proposal ids with independent command hashes and receipts.
- Proposal preparation is useful offline work only when it freezes the native
  executable path, version, and SHA-256; exact prompt/input hashes; a strict
  workspace manifest; timeout/output ceilings; retry/depth/fan-out policy; and
  absent parent-controlled receipts before any launch.
- A prepared plan must say `approval_state=not-granted` and the helper must not
  execute even its stored dry-run command. This keeps inspection, approval, and
  provider use as distinct transitions.
- A successful typed-effort probe can prove that the pinned native CLI accepted
  the launcher-owned config transport and completed a bounded run. The request
  receipt still cannot prove provider-side model or effort honoring unless the
  client exposes independent usage evidence.
- Image generation and image viewing need observed tool events. Native image
  attachment remains a separate capability, and approval for either image probe
  does not authorize the other probe, a three-item batch, product data, or
  product integration.
- The completed offline gate now covers the proposal lifecycle itself: 5 focused
  proposal tests, 95 fast tests with 1 expected Windows symlink skip, and 266
  full tests with 2 expected skips. All three skill validations, all five
  public-surface scans, compile, and diff hygiene also passed before handing the
  exact proposals to the owner.
- Dry-run-first is only executable when dry and live evidence have different
  fresh roots. Reusing one path causes the dry summary to make the subsequent
  live command fail its nonempty-output guard. The original plans were preserved
  as evidence and superseded rather than mutated in place.
- A proposal closer should not trust the launcher summary alone. Recompute the
  native identity and strict workspace delta, independently parse JSONL, compare
  tool and terminal identities, bind the actual launcher argv digest, reject
  extra receipts, and validate generated bytes before closure.
- An approval-reference flag records operator attestation but cannot prove who
  supplied it. Keep that epistemic limit in the closure and never let it become
  transferable authority for another program phase, the other image probe, a
  batch, or integration.
- The schema `0.2` final gate passed 101 fast tests in 114.316 seconds with 1
  expected Windows skip and 272 full tests in 551.266 seconds with 2 expected
  skips. Compilation, all three skill validations, five clean artifact scans,
  and diff hygiene also passed without launching a provider.

## 2026-07-12 Finite Synthetic Image Pilot Controller

- A finite item list is not enough by itself. Reliability requires one parent
  controller to own ordering, daily attempt reservation, aggregate ceilings,
  item closure, and the stop-before-next transition.
- Human-readable approval references need an exact plan hash. Otherwise an
  approval can be replayed after a plan, item, limit, or command changes while
  retaining the same friendly identifier.
- Daily limits need cross-process state rather than a batch-local counter. An
  atomic lock plus parent-controlled UTC-day ledger lets concurrent controllers
  fail closed instead of each believing it owns the same remaining allowance.
- Failed batches must preserve partial evidence but prove absence of later-item
  receipts. Verification therefore treats attempted/completed items as ordered
  prefixes and rejects any later dry-run, live, manifest, or closure path.
- Closed receipts need a reusable verifier for downstream routes. Replaying the
  plan, native identity, JSONL, tool evidence, workspace, artifact, and closure
  claims prevents a later batch from trusting a stale or substituted closure.
- The real pilot remains ineligible: both current image cases are prepared but
  unapproved and unexecuted. The controller correctly stopped before creating a
  batch root or daily ledger when those closures were absent.
- The final combined deterministic gate passed 118 fast tests in 211.487
  seconds with 1 expected Windows skip and 292 full tests in 797.729 seconds
  with 2 expected skips. Compilation, all three skill validations, five clean
  scans, and diff hygiene also passed without provider or product-data use.
