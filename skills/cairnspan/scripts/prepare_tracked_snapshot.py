#!/usr/bin/env python3
"""Export a secret-guarded, tracked-HEAD-only workspace snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from scan_artifacts import scan_bytes


SCHEMA_VERSION = "0.1"
DEFAULT_MAX_FILES = 10_000
DEFAULT_MAX_TOTAL_BYTES = 250 * 1024 * 1024
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
SAFE_ENV_TEMPLATES = {".env.example", ".env.sample", ".env.template"}
SENSITIVE_NAMES = {
    ".env",
    "credentials.json",
    "credentials.yml",
    "credentials.yaml",
    "secrets.json",
    "secrets.yml",
    "secrets.yaml",
    "id_rsa",
    "id_ed25519",
}
SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".jks", ".keystore"}
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
HEX_OID = re.compile(r"^[0-9a-f]{40,64}$")


class SnapshotError(ValueError):
    """Raised when a repository cannot be exported under snapshot policy."""


@dataclass(frozen=True)
class BlobEntry:
    mode: str
    oid: str
    size: int
    path: str
    data: bytes


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(repo: Path, *args: str) -> bytes:
    git = shutil.which("git")
    if not git:
        raise SnapshotError("git executable was not found on PATH")
    command = [git, "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), *args]
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise SnapshotError(detail or f"git {' '.join(args)} failed with {result.returncode}")
    return result.stdout


def validate_repo_path(raw_path: str) -> PurePosixPath:
    if not raw_path or "\x00" in raw_path or any(ord(char) < 32 for char in raw_path):
        raise SnapshotError("tracked path contains an empty or control-character segment")
    if "\\" in raw_path:
        raise SnapshotError(f"tracked path uses a backslash: {raw_path!r}")
    path = PurePosixPath(raw_path)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise SnapshotError(f"tracked path is not a safe relative path: {raw_path!r}")
    for part in path.parts:
        if ":" in part or part.endswith((" ", ".")):
            raise SnapshotError(f"tracked path is unsafe on Windows: {raw_path!r}")
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED:
            raise SnapshotError(f"tracked path uses a Windows device name: {raw_path!r}")
    name = path.name.lower()
    if name.startswith(".env") and name not in SAFE_ENV_TEMPLATES:
        raise SnapshotError(f"tracked environment file is forbidden: {raw_path!r}")
    if name in SENSITIVE_NAMES or any(name.endswith(suffix) for suffix in SENSITIVE_SUFFIXES):
        raise SnapshotError(f"tracked credential-like file is forbidden: {raw_path!r}")
    return path


def normalize_include_prefixes(values: list[str] | None) -> list[str]:
    prefixes: list[str] = []
    for value in values or []:
        normalized = validate_repo_path(value.rstrip("/"))
        prefixes.append(normalized.as_posix())
    return sorted(set(prefixes))


def path_is_included(path: str, include_prefixes: list[str]) -> bool:
    return not include_prefixes or any(path == prefix or path.startswith(prefix + "/") for prefix in include_prefixes)


def parse_tree(
    repo: Path,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
    include_prefixes: list[str],
) -> list[BlobEntry]:
    output = run_git(repo, "ls-tree", "-rlz", "--full-tree", "HEAD")
    records = [record for record in output.split(b"\x00") if record]

    entries: list[BlobEntry] = []
    total_bytes = 0
    for record in records:
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode_raw, object_type_raw, oid_raw, size_raw = metadata.split(b" ", 3)
            mode = mode_raw.decode("ascii")
            object_type = object_type_raw.decode("ascii")
            oid = oid_raw.decode("ascii")
            path_text = raw_path.decode("utf-8", errors="strict")
        except (UnicodeError, ValueError) as exc:
            raise SnapshotError("git tree contains an unparseable entry") from exc
        validate_repo_path(path_text)
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise SnapshotError(
                f"tracked entry must be a regular file blob, got mode={mode} type={object_type}: {path_text!r}"
            )
        if not path_is_included(path_text, include_prefixes):
            continue
        if len(entries) >= max_files:
            raise SnapshotError(f"included tracked file count exceeds limit {max_files}")
        if not HEX_OID.fullmatch(oid):
            raise SnapshotError(f"tracked entry has an invalid object id: {path_text!r}")
        try:
            declared_size = int(size_raw.decode("ascii"))
        except (UnicodeError, ValueError) as exc:
            raise SnapshotError(f"tracked entry has an invalid size: {path_text!r}") from exc
        if declared_size < 0 or declared_size > max_file_bytes:
            raise SnapshotError(
                f"tracked file {path_text!r} size {declared_size} exceeds limit {max_file_bytes}"
            )
        total_bytes += declared_size
        if total_bytes > max_total_bytes:
            raise SnapshotError(f"tracked bytes exceed aggregate limit {max_total_bytes}")
        data = run_git(repo, "cat-file", "blob", oid)
        if len(data) != declared_size:
            raise SnapshotError(f"git blob size changed while exporting: {path_text!r}")
        findings = scan_bytes(Path(path_text), data)
        if findings:
            kinds = ", ".join(sorted({finding.kind for finding in findings}))
            raise SnapshotError(f"tracked content failed publish-safety scan ({kinds}): {path_text!r}")
        entries.append(BlobEntry(mode=mode, oid=oid, size=declared_size, path=path_text, data=data))
    return sorted(entries, key=lambda item: item.path)


def ensure_clean_tracked_worktree(repo: Path) -> None:
    status = run_git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=no")
    if status:
        raise SnapshotError("tracked worktree or index is dirty; commit/stash it or export a reviewed commit explicitly")


def export_snapshot(
    source_repo: Path,
    out_dir: Path,
    manifest_out: Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    include_prefixes: list[str] | None = None,
) -> dict[str, Any]:
    repo = source_repo.resolve(strict=True)
    if not repo.is_dir() or not (repo / ".git").exists():
        raise SnapshotError(f"source is not a Git checkout: {repo}")
    destination = out_dir.resolve(strict=False)
    manifest_path = manifest_out.resolve(strict=False)
    if destination.exists():
        raise SnapshotError(f"snapshot destination already exists: {destination}")
    if manifest_path.exists():
        raise SnapshotError(f"snapshot manifest already exists: {manifest_path}")
    if destination == repo or repo in destination.parents or destination in repo.parents:
        raise SnapshotError("source repository and snapshot destination must not overlap")
    if manifest_path == destination or destination in manifest_path.parents:
        raise SnapshotError("authoritative snapshot manifest must be outside the exported workspace")
    if max_files <= 0 or max_file_bytes <= 0 or max_total_bytes <= 0:
        raise SnapshotError("snapshot limits must be positive")

    ensure_clean_tracked_worktree(repo)
    normalized_prefixes = normalize_include_prefixes(include_prefixes)
    commit = run_git(repo, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if not HEX_OID.fullmatch(commit):
        raise SnapshotError("HEAD did not resolve to a full commit id")
    entries = parse_tree(repo, max_files, max_file_bytes, max_total_bytes, normalized_prefixes)
    if normalized_prefixes and not entries:
        raise SnapshotError("include-prefix policy selected no tracked regular files")

    destination.mkdir(parents=True, exist_ok=False)
    for entry in entries:
        relative = PurePosixPath(entry.path)
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(entry.data)
        if os.name != "nt" and entry.mode == "100755":
            target.chmod(target.stat().st_mode | stat.S_IXUSR)

    files = [
        {
            "path": entry.path,
            "git_mode": entry.mode,
            "git_oid": entry.oid,
            "bytes": entry.size,
            "sha256": sha256_bytes(entry.data),
        }
        for entry in entries
    ]
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "succeeded",
        "created_at": utc_now(),
        "source_repo_name": repo.name,
        "source_commit": commit,
        "tracked_worktree_clean": True,
        "policy": {
            "source": "committed HEAD blobs only",
            "regular_file_modes": ["100644", "100755"],
            "tracked_environment_files_denied": True,
            "symlinks_denied": True,
            "submodules_denied": True,
            "content_publish_scan": True,
            "max_files": max_files,
            "max_file_bytes": max_file_bytes,
            "max_total_bytes": max_total_bytes,
            "include_prefixes": normalized_prefixes,
        },
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = manifest_path.with_name(f".{manifest_path.name}.{os.getpid()}.tmp")
    with temp_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temp_path, manifest_path)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument(
        "--include-prefix",
        action="append",
        default=[],
        help="Repeatable tracked file or directory prefix to include; omit to export all tracked files",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = export_snapshot(
            args.source_repo,
            args.out_dir,
            args.manifest_out,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
            include_prefixes=args.include_prefix,
        )
    except (FileNotFoundError, OSError, SnapshotError, UnicodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "succeeded",
        "source_commit": manifest["source_commit"],
        "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"],
        "manifest": str(args.manifest_out.resolve(strict=False)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
