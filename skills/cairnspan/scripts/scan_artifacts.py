"""Scan Cairnspan artifacts for obvious private data before publishing.

This helper is intentionally stdlib-only. It is a release-safety check for
redacted fixtures, not a complete secret scanner.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
from urllib.parse import unquote
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


MAX_TEXT_BYTES = 5 * 1024 * 1024
BASE64_CANDIDATE = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{20,}={0,2}(?![A-Za-z0-9+/=])")
COMPRESSED_SIGNATURES = (b"\x1f\x8b", b"PK\x03\x04", b"BZh", b"\xfd7zXZ\x00")
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("canary_secret", re.compile(r"\bCAIRNSPAN_CANARY_SECRET[A-Za-z0-9._~+/=-]*\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("anthropic_api_key", re.compile(r"\bsk-ant-[A-Za-z0-9._-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    (
        "assigned_secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie|sessionid)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{12,}"
        ),
    ),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
LOCAL_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "windows_user_path",
        re.compile(r"[A-Za-z]:(?:\\{1,2})Users(?:\\{1,2})[^\\\s\"']+(?:(?:\\{1,2})[^\\\s\"']+)*"),
    ),
    ("unix_user_path", re.compile(r"/(?:Users|home)/[^/\s\"']+(?:/[^/\s\"']+)*")),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    kind: str
    sample: str


def redacted_sample(kind: str) -> str:
    if kind.endswith("_path"):
        return "<local-path>"
    if kind == "private_key":
        return "<private-key>"
    if kind in {"oversized_artifact", "linked_artifact", "compressed_artifact"}:
        return "<unscanned>"
    return "<secret>"


def is_probably_binary(data: bytes) -> bool:
    return b"\x00" in data[:4096]


def iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if path.is_symlink():
            yield path
            continue
        if path.is_file():
            yield path
            continue
        if not path.is_dir():
            continue
        def raise_walk_error(error: OSError) -> None:
            raise error

        for root, dirs, files in os.walk(path, onerror=raise_walk_error):
            dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
            root_path = Path(root)
            for filename in files:
                yield root_path / filename


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    patterns = SECRET_PATTERNS + LOCAL_PATH_PATTERNS
    for line_number, line in enumerate(text.splitlines(), 1):
        for kind, pattern in patterns:
            for match in pattern.finditer(line):
                findings.append(
                    Finding(
                        path=str(path),
                        line=line_number,
                        column=match.start() + 1,
                        kind=kind,
                        sample=redacted_sample(kind),
                    )
                )
    return findings


def scan_encoded_views(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    compact = re.sub(r"\s+", "", text)
    if compact != text:
        for kind, pattern in SECRET_PATTERNS:
            if kind in {"assigned_secret", "bearer_token", "private_key"}:
                continue
            if pattern.search(compact):
                findings.append(Finding(str(path), 1, 1, kind, redacted_sample(kind)))

    decoded_url = unquote(text)
    if decoded_url != text and len(decoded_url.encode("utf-8")) <= MAX_TEXT_BYTES:
        findings.extend(scan_text(path, decoded_url))

    for match in BASE64_CANDIDATE.finditer(text):
        token = match.group(0)
        padding = "=" * (-len(token) % 4)
        try:
            decoded = base64.b64decode(token + padding, validate=True)
        except (binascii.Error, ValueError):
            continue
        if len(decoded) > MAX_TEXT_BYTES:
            findings.append(Finding(str(path), 1, 1, "oversized_artifact", "<unscanned>"))
            continue
        findings.extend(scan_text(path, decoded.decode("utf-8", errors="replace")))
    return findings


def scan_bytes(path: Path, data: bytes) -> list[Finding]:
    if len(data) > MAX_TEXT_BYTES:
        return [Finding(str(path), 1, 1, "oversized_artifact", redacted_sample("oversized_artifact"))]
    if data.startswith(COMPRESSED_SIGNATURES):
        return [Finding(str(path), 1, 1, "compressed_artifact", redacted_sample("compressed_artifact"))]
    text = data.decode("utf-8", errors="replace")
    findings = scan_text(path, text)
    findings.extend(scan_encoded_views(path, text))
    return list(dict.fromkeys(findings))


def scan_file(path: Path) -> list[Finding]:
    if path.is_symlink():
        return [Finding(str(path), 1, 1, "linked_artifact", redacted_sample("linked_artifact"))]
    return scan_bytes(path, path.read_bytes())


def scan_paths(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(paths):
        findings.extend(scan_file(path))
    return findings


def make_payload(findings: list[Finding]) -> dict[str, object]:
    return {
        "status": "failed" if findings else "clean",
        "finding_count": len(findings),
        "findings": [asdict(finding) for finding in findings],
    }


def print_text_payload(findings: list[Finding]) -> None:
    if not findings:
        print("artifact-scan-clean")
        return
    print(f"artifact-scan-failed: {len(findings)} finding(s)")
    for finding in findings:
        print(f"{finding.path}:{finding.line}:{finding.column}: {finding.kind}: {finding.sample}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan Cairnspan artifacts before publishing.")
    parser.add_argument("paths", nargs="+", type=Path, help="File or directory paths to scan")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        findings = scan_paths(args.paths)
    except OSError as exc:
        print(f"artifact-scan-config-error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(make_payload(findings), indent=2, sort_keys=True))
    else:
        print_text_payload(findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
