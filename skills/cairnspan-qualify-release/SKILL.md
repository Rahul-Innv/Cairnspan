---
name: cairnspan-qualify-release
description: Evaluate exactly one Cairnspan source, public-alpha, or production readiness profile and return a non-publishing verdict. Use for repository release qualification only, not setup checks, export, commit, or publication.
---

# Cairnspan Qualify Release

## Outcome

Return a non-publishing readiness verdict for exactly one selected profile.

## Trigger

Use when the user asks whether Cairnspan source, public alpha, or production claims are supported by local repository evidence.

Do not use to diagnose local launcher setup, export tracked source, create a commit, or publish anything.

## Runtime resolution

Resolve `CAIRNSPAN_RUNTIME_ROOT` from this file's location: take this `SKILL.md` directory's parent (the family skills root), then its `cairnspan` child. Resolve every helper below `CAIRNSPAN_RUNTIME_ROOT/scripts`; never resolve a helper or policy from the caller's working directory. Fail closed if the sibling runtime or exact helper is absent. Any owner-policy document must be supplied explicitly by the caller.

## Procedure

1. Require the exact target repository as an explicit absolute path, bind it as `<EXACT_TARGET_REPOSITORY>`, and fail closed if it is relative, missing, or not a directory. Never infer the target from the installed skill, runtime location, or caller's working directory.
2. Select exactly one profile and identify its required local evidence and attestations for `<EXACT_TARGET_REPOSITORY>`.
3. Run the deterministic tests and `<CAIRNSPAN_RUNTIME_ROOT>/scripts/scan_artifacts.py` over the exact target repository scope.
4. Run `<CAIRNSPAN_RUNTIME_ROOT>/scripts/release_readiness.py --root <EXACT_TARGET_REPOSITORY> --profile <profile>` without creating evidence that does not already exist. The `--root` value is mandatory even when the target happens to contain the runtime.
5. Report each satisfied and missing gate, the profile-specific verdict, the exact target repository, and the exact next action.
6. Stop before tracked export, commit, remote, tag, release, package publication, visibility change, deployment, or schedule.

## Non-goals

Do not use `prepare_tracked_snapshot.py` without separate export authority, manufacture attestations, publish, install, authenticate, call providers, or treat source readiness as public-alpha/production readiness.
