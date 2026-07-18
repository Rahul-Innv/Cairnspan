# Website And Image Artifact Route

Status: implemented and live-verified on synthetic public data. The route
produced one validated static PNG and closed with
`product_integration=not-run`; real product integration remains a separate
human-approved edge. This is historical evidence for the inspected binary used
by that run, not proof that `codex-cli 0.144.0-alpha.4` can currently start
`$imagegen` or `view_image`.

## Goal

Support a concrete workflow in which Claude Code prepares website design intent, Codex uses its account-backed image generation capability, and a trusted parent validates the resulting asset before any agent can consume or integrate it.

This is a separate route profile because an exact text nonce does not prove that an image is valid, expected, safe to parse, properly licensed, or the only file changed.

## Initial Route

```text
user-approved product brief
  -> Claude Code design-spec edge (no tools, no edits)
  -> parent validates/minimizes the design spec
  -> Codex image-generation edge (fresh scratch workspace, scoped write)
  -> parent validates one typed image artifact
  -> human approval
  -> separate integration edge or manual product-repo change
```

The image-generation edge must never write directly into a real product repository. The trusted parent copies an accepted artifact into an approved integration workspace only after validation and approval.

## Typed Artifact Manifest

The parent, not the producing model, creates the authoritative manifest. Minimum fields:

- schema version;
- artifact id and route id;
- producer adapter, child run id, and executable identity hash;
- normalized relative path under the fresh staging root;
- SHA-256, byte length, detected media type, and file signature;
- decoded width, height, color mode, and frame count;
- artifact role such as `hero`, `product`, `texture`, or `reference`;
- generation prompt hash and hashes of approved input references;
- creation time and policy version;
- validation results, rejection reasons, and final disposition;
- provenance/rights note suitable for the intended public use.

Model-supplied filenames, MIME labels, dimensions, and hashes are claims only. The parent recomputes them from bytes.

## Staging And Write Policy

- Use a fresh, empty, route-specific staging workspace.
- Permit exactly one expected output file unless the route plan explicitly allows variants.
- Reject absolute paths, parent traversal, links, reparse points, alternate data streams, hardlinks, device names, and writes outside the staging root.
- Keep authoritative receipts outside every target-writable workspace.
- Take strict before/after manifests including hidden files, empty directories, reparse metadata, and NTFS alternate data streams.
- Reject unexpected files, directories, metadata streams, modifications, or deletions.
- Enforce byte, dimension, pixel-count, frame-count, runtime, output, and route-cost ceilings before decoding or copying.
- Delete rejected scratch artifacts after preserving a redacted denial receipt; retain accepted raw artifacts only under the configured private retention policy.

## Image Validation

An accepted image must pass all of these checks:

- expected count and normalized path;
- non-empty regular file with no link/reparse behavior;
- signature and decoded format agree;
- dimensions, pixel count, frame count, and bytes remain under policy;
- full decoder load succeeds without truncation;
- no additional files appeared in staging;
- metadata is stripped or explicitly retained by policy;
- retained standard display chunks are limited to strictly validated fixed-size `gAMA`, `pHYs`, and `sRGB`; text, profiles, APNG, and unknown ancillary payloads remain denied by default;
- embedded text, QR codes, URLs, comments, profiles, and metadata are treated as untrusted content;
- public-use rights/provenance are recorded and any reference-image restrictions are respected;
- the artifact hash in the route receipt matches the exact bytes offered for integration.

Image content can carry prompt injection or hidden instructions. A later model may inspect pixels for design critique, but must not execute, browse, decode URLs, or follow instructions found in the image or metadata.

## Integration Gate

Integration is a new edge with a new approval, not an automatic continuation of generation.

`--visual-review-status passed` and any integration-approval flag are trusted operator attestations, not facts an agent may assert for itself. The human owner must invoke or explicitly authorize the closer after inspecting the hash-identified artifact; a target agent must not supply its own approval.

- The user approves the selected artifact and destination project.
- The parent copies only the hash-verified file into a fresh integration branch/worktree or explicitly scoped workspace.
- The integrating agent receives the product brief plus the artifact manifest, not raw generation logs.
- Expected destination paths are declared before launch.
- A before/after product manifest must show only approved changes.
- Build, lint, accessibility, responsive-layout, and visual checks run before the change is accepted.
- Generated text inside an image is not used for important UI copy, controls, legal text, or accessibility labels.

## Bounded Cross-Model Critique

The first critique profile is a parent-controlled directed acyclic graph, not an open conversation:

1. One agent creates a design spec or artifact.
2. A second agent receives a minimized, immutable copy and returns structured critique only.
3. The parent validates the critique schema and decides whether one revision is allowed.
4. At most one revision and one final critique run occur by default.
5. No critic writes to the producer workspace, no target launches another target, and no model decides to add rounds.

Route policy must set max edges, max rounds, max fan-out, per-edge and aggregate runtime/output/cost, allowed providers, data classification, allowed artifact types, and approval points. Conflicting critiques are presented to the user; they are not resolved by silently adding more agents.

When a critique workflow requires a reviewed model/effort pair, each parent
edge plan must use the typed launcher fields and freeze the expected child
`requested_model`, `requested_effort`, executable identity, and CLI version.
The allowed effort set is `low`, `medium`, `high`, `xhigh`, and `max`; raw args,
profiles, and caller-authored config expressions are not substitutes. A child
receipt proves only the request. Provider-side honoring requires independent
usage/runtime evidence when the client exposes it.

## Finite Unattended Batch Contract

A batch is a parent-authored immutable ordered list, not a mailbox queue or an
open-ended loop. Its plan records the batch id, exact item ids and order,
prompt/input hashes, expected roles and paths, native executable identity,
policy version, approval state, and every aggregate ceiling.

Initial policy:

- concurrency: 1;
- automatic retries: 0;
- maximum synthetic pilot size: 3 items;
- hard per-run and per-batch runtime and output ceilings;
- hard daily item/provider-use ceiling;
- hard staging plus receipt disk ceiling;
- explicit private retention duration and parent-owned cleanup disposition;
- fresh per-item staging, receipts, strict manifests, typed artifact manifest,
  visual approval, and integration decision.

The implemented first-pilot controller covers generation, byte validation,
receipts, limits, and terminal batch disposition. It records no visual approval
and keeps integration `not-run`; those remain later human/product edges.

The parent stops the entire batch before launching the next item if any item
reports or implies an authentication, quota, rate-limit, required-capability,
containment, unexpected-file, manifest, cleanup, or receipt-integrity failure.
There is no automatic skip, retry, fallback provider, or partial product
integration. Preserved receipts must make the terminal batch disposition and
the last attempted item unambiguous.

Account-backed image generation has no assumed sustained-volume contract. The
three-item pilot must measure actual latency, output bytes, staging/receipt disk,
cleanup, and provider-limit signals before the owner is shown a recommended
batch size or API-backed alternative. Scheduling or overnight supervision is a
separate explicitly approved parent-controller concern, not an artifact-route
or mailbox feature.

## Adversarial Tests Before Live Use

- output missing, empty, malformed, truncated, wrong format, or wrong extension;
- multiple outputs when one was expected;
- oversized bytes, dimensions, pixel count, or animation frames;
- path traversal, absolute path, symlink, junction, hardlink, ADS, and device-name outputs;
- unexpected hidden files or directories;
- source workspace mutation outside the scratch root;
- metadata containing secrets, local paths, URLs, or instruction-like text;
- QR/visible text instructing a critic to use tools or disclose data;
- producer receipt hash mismatch and stale artifact replay;
- executable identity drift between route plan and closure;
- timeout, output overflow, disk exhaustion, quota/rate limit, and partial write;
- critic attempts tool use, network access, workspace edits, recursive delegation, or extra rounds;
- product integration changes an undeclared file;
- artifact scanner catches public-fixture canaries and local path leakage.

## First Live Pass Criteria

- Claude returns a schema-valid, secret-free design spec with zero tools and no workspace changes.
- Codex produces exactly one expected image in a fresh scratch workspace through the account-backed built-in image path.
- Parent validation records the typed manifest and rejects any unexpected staging change.
- The accepted artifact's bytes, signature, dimensions, and SHA-256 are independently verified.
- No raw API-key fallback is used and no secret environment value appears in receipts.
- No target process or descendant survives either edge.
- No product repository is modified during generation.
- The route stays within explicit runtime, output, disk, and reported-cost ceilings.
- A human approves the asset before any product integration edge.

The first live artifact test should use a synthetic public website brief and no private source files. Real product integration comes only after that probe passes.

For any downstream product consumer, this historical first-pass evidence is
only a template, not general product authorization. Current image
capabilities, the three-item synthetic pilot, data classification, repository
ownership, visual approval, and integration scope must be established again
with fresh receipts.
