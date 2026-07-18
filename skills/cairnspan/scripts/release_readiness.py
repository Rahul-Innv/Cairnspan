"""Evaluate Cairnspan release readiness without publishing or provider use."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[3]
VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-alpha\.(0|[1-9]\d*)$")
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
REQUIRED_FILES = (
    ".gitlab-ci.yml",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "VERSION",
    "docs/install-skill.md",
    "docs/release-readiness.md",
    "docs/safety-checklist.md",
    "docs/threat-model.md",
    "docs/verification.md",
    "skills/cairnspan/SKILL.md",
    "skills/cairnspan/agents/openai.yaml",
)
SCAN_TARGETS = (
    ".gitlab-ci.yml",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "VERSION",
    "docs",
    "skills/cairnspan",
    ".agents",
    ".claude",
)
ATTESTATION_FIELDS = (
    "full_gate_passed",
    "public_artifact_human_review_passed",
    "name_namespace_legal_review_passed",
    "provider_copy_review_passed",
    "private_vulnerability_channel_enabled",
)


@dataclass(frozen=True)
class Check:
    id: str
    status: str
    detail: str


def git_output(root: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout.strip()
    if result.returncode and result.stderr.strip():
        output = result.stderr.strip()
    return result.returncode, output


def scan_target(root: Path, target: str) -> tuple[bool, str]:
    scanner = root / "skills" / "cairnspan" / "scripts" / "scan_artifacts.py"
    result = subprocess.run(
        [sys.executable, str(scanner), str(root / target), "--format", "json"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        return True, f"{target}: zero scanner findings"
    detail = result.stdout.strip() or result.stderr.strip() or "scanner failed"
    return False, f"{target}: {detail[:500]}"


def source_checks(
    root: Path,
    scanner: Callable[[Path, str], tuple[bool, str]] = scan_target,
) -> tuple[list[Check], str | None]:
    checks: list[Check] = []
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    checks.append(Check("required-files", "pass" if not missing else "block", "all required release files exist" if not missing else f"missing: {', '.join(missing)}"))

    version: str | None = None
    version_path = root / "VERSION"
    if version_path.is_file():
        version = version_path.read_text(encoding="utf-8").strip()
    version_ok = bool(version and VERSION_PATTERN.fullmatch(version))
    checks.append(Check("alpha-version", "pass" if version_ok else "block", f"planned version is {version}" if version_ok else "VERSION must be an alpha SemVer such as 0.1.0-alpha.1"))

    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").is_file() else ""
    scope_markers = (
        "Do not describe Cairnspan as production-ready.",
        "Do not describe Cairnspan as enterprise-ready or three-agent capable",
    )
    missing_markers = [marker for marker in scope_markers if marker not in readme]
    checks.append(Check("claim-scope", "pass" if not missing_markers else "block", "README retains alpha claim boundaries" if not missing_markers else "README is missing required claim boundaries"))

    for target in SCAN_TARGETS:
        ok, detail = scanner(root, target)
        checks.append(Check(f"scan:{target}", "pass" if ok else "block", detail))
    return checks, version


def load_attestations(path: Path | None, commit: str | None) -> list[Check]:
    if path is None:
        return [Check("release-attestations", "block", "--attestations is required for public-alpha and production")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [Check("release-attestations", "block", f"cannot load attestations: {exc}")]
    checks = [Check("attestation-schema", "pass" if payload.get("schema_version") == "0.1" else "block", "attestation schema is 0.1" if payload.get("schema_version") == "0.1" else "schema_version must equal 0.1")]
    reviewed = payload.get("reviewed_commit")
    commit_ok = isinstance(reviewed, str) and bool(COMMIT_PATTERN.fullmatch(reviewed)) and reviewed == commit
    checks.append(Check("attested-commit", "pass" if commit_ok else "block", "attestations bind the current commit" if commit_ok else "reviewed_commit must exactly match the current full commit id"))
    for field in ATTESTATION_FIELDS:
        checks.append(Check(f"attestation:{field}", "pass" if payload.get(field) is True else "block", f"{field}=true" if payload.get(field) is True else f"{field} must be true"))
    return checks


def public_alpha_checks(
    root: Path,
    version: str | None,
    attestations: Path | None,
    git: Callable[..., tuple[int, str]] = git_output,
) -> tuple[list[Check], str | None]:
    checks: list[Check] = []
    code, commit = git(root, "rev-parse", "HEAD")
    current_commit = commit if code == 0 and COMMIT_PATTERN.fullmatch(commit) else None
    checks.append(Check("git-commit", "pass" if current_commit else "block", f"candidate commit is {current_commit}" if current_commit else "cannot resolve candidate commit"))

    code, status = git(root, "status", "--porcelain", "--untracked-files=all")
    clean = code == 0 and not status
    checks.append(Check("clean-worktree", "pass" if clean else "block", "worktree is clean" if clean else "tracked or untracked release changes remain"))

    code, remotes = git(root, "remote")
    has_remote = code == 0 and bool(remotes.splitlines())
    checks.append(Check("canonical-remote", "pass" if has_remote else "block", f"configured remotes: {', '.join(remotes.splitlines())}" if has_remote else "no Git remote is configured"))

    expected_tag = f"v{version}" if version else None
    code, tags = git(root, "tag", "--points-at", "HEAD")
    tag_ok = code == 0 and expected_tag is not None and expected_tag in tags.splitlines()
    checks.append(Check("version-tag", "pass" if tag_ok else "block", f"{expected_tag} points at HEAD" if tag_ok else f"{expected_tag or 'version tag'} does not point at HEAD"))

    threat = (root / "docs" / "threat-model.md").read_text(encoding="utf-8")
    write_gate = "- [x] The separately specified write-enabled hostile-workspace matrix passes;" in threat
    checks.append(Check("write-hostile-matrix", "pass" if write_gate else "block", "live write-enabled hostile matrix is closed" if write_gate else "live write-enabled hostile matrix is still open; remove workspace-write or close the matrix"))
    checks.extend(load_attestations(attestations, current_commit))
    return checks, current_commit


def production_checks(root: Path) -> list[Check]:
    verification = (root / "docs" / "verification.md").read_text(encoding="utf-8")
    requirements = {
        "native-pressure-matrix": "- [x] Broader native-client crash/quota/rate-limit and live canary pressure gates pass.",
        "posix-containment": "- [x] Authoritative POSIX containment and live cleanup tests pass.",
        "signed-release-sbom": "- [x] Signed release artifacts and an SBOM are published.",
    }
    return [Check(check_id, "pass" if marker in verification else "block", "production gate is closed" if marker in verification else "production gate remains open") for check_id, marker in requirements.items()]


def build_report(
    root: Path,
    profile: str,
    attestations: Path | None = None,
    scanner: Callable[[Path, str], tuple[bool, str]] = scan_target,
    git: Callable[..., tuple[int, str]] = git_output,
) -> dict[str, object]:
    checks, version = source_checks(root, scanner)
    commit: str | None = None
    if profile in {"public-alpha", "production"}:
        extra, commit = public_alpha_checks(root, version, attestations, git)
        checks.extend(extra)
    if profile == "production":
        checks.extend(production_checks(root))
    blockers = sum(check.status == "block" for check in checks)
    return {
        "schema_version": "0.1",
        "profile": profile,
        "version": version,
        "commit": commit,
        "ready": blockers == 0,
        "counts": {"pass": sum(check.status == "pass" for check in checks), "block": blockers},
        "checks": [asdict(check) for check in checks],
    }


def render_text(report: dict[str, object]) -> str:
    lines = [f"profile={report['profile']} version={report['version']} ready={str(report['ready']).lower()}"]
    for item in report["checks"]:  # type: ignore[index]
        lines.append(f"{item['status'].upper():5} {item['id']}: {item['detail']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("source", "public-alpha", "production"), default="source")
    parser.add_argument("--attestations", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    report = build_report(args.root.resolve(), args.profile, args.attestations)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
