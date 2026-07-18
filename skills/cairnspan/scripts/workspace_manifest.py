"""Create and compare deterministic workspace manifests for no-edit probes."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "0.2"
DEFAULT_EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("x", encoding="utf-8", newline="") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_reparse_point(stat_result: os.stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    flag = getattr(__import__("stat"), "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & flag)


def excluded(relative: Path, extra_excludes: set[str], strict: bool) -> bool:
    if any(part in extra_excludes for part in relative.parts):
        return True
    if strict:
        return False
    if relative.suffix.lower() == ".pyc":
        return True
    for part in relative.parts:
        if part in DEFAULT_EXCLUDED_DIRS or part.startswith(".cairnspan"):
            return True
    return False


def link_target(path: Path) -> str | None:
    try:
        return os.readlink(path)
    except OSError:
        return None


def windows_streams(path: Path) -> list[dict[str, Any]]:
    if os.name != "nt":
        return []

    class WIN32_FIND_STREAM_DATA(ctypes.Structure):
        _fields_ = [("StreamSize", ctypes.c_longlong), ("cStreamName", ctypes.c_wchar * 296)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    find_first = kernel32.FindFirstStreamW
    find_first.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(WIN32_FIND_STREAM_DATA), ctypes.c_uint]
    find_first.restype = ctypes.c_void_p
    find_next = kernel32.FindNextStreamW
    find_next.argtypes = [ctypes.c_void_p, ctypes.POINTER(WIN32_FIND_STREAM_DATA)]
    find_next.restype = ctypes.c_int
    find_close = kernel32.FindClose
    find_close.argtypes = [ctypes.c_void_p]
    find_close.restype = ctypes.c_int

    data = WIN32_FIND_STREAM_DATA()
    invalid_handle = ctypes.c_void_p(-1).value
    handle = find_first(str(path), 0, ctypes.byref(data), 0)
    if handle == invalid_handle:
        error = ctypes.get_last_error()
        if error in {2, 38}:
            return []
        raise OSError(error, f"FindFirstStreamW failed for {path}")
    streams: list[dict[str, Any]] = []
    try:
        while True:
            name = data.cStreamName
            if name and name != "::$DATA":
                stream_path = Path(str(path) + name.removesuffix(":$DATA"))
                streams.append(
                    {
                        "name": name,
                        "size": int(data.StreamSize),
                        "sha256": sha256_file(stream_path),
                    }
                )
            if not find_next(handle, ctypes.byref(data)):
                error = ctypes.get_last_error()
                if error == 38:
                    break
                raise OSError(error, f"FindNextStreamW failed for {path}")
    finally:
        find_close(handle)
    streams.sort(key=lambda item: item["name"])
    return streams


def make_entry(path: Path, root: Path, include_streams: bool) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    stat_result = path.lstat()
    if path.is_symlink() or is_reparse_point(stat_result):
        return {
            "path": relative,
            "type": "reparse",
            "target": link_target(path),
            "size": stat_result.st_size,
            "mtime_ns": stat_result.st_mtime_ns,
        }
    common = {
        "path": relative,
        "mtime_ns": stat_result.st_mtime_ns,
        "mode": stat_result.st_mode,
        "nlink": stat_result.st_nlink,
        "file_id": [stat_result.st_dev, stat_result.st_ino],
    }
    if include_streams:
        common["streams"] = windows_streams(path)
    if path.is_dir():
        return {**common, "type": "directory"}
    return {
        **common,
        "type": "file",
        "size": stat_result.st_size,
        "sha256": sha256_file(path),
    }


def iter_workspace_entries(root: Path, extra_excludes: set[str], strict: bool) -> Iterable[Path]:
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for name in sorted(dirs):
            path = current_path / name
            relative = path.relative_to(root)
            if excluded(relative, extra_excludes, strict):
                continue
            if path.is_symlink() or is_reparse_point(path.lstat()):
                yield path
                continue
            if strict:
                yield path
            kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in sorted(files):
            path = current_path / name
            if not excluded(path.relative_to(root), extra_excludes, strict):
                yield path


def snapshot(
    root: Path,
    extra_excludes: set[str] | None = None,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ValueError(f"Workspace root is not a directory: {resolved}")
    excludes = set(extra_excludes or set())
    entries = [
        make_entry(path, resolved, strict)
        for path in iter_workspace_entries(resolved, excludes, strict)
    ]
    entries.sort(key=lambda entry: entry["path"])
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "root": str(resolved),
        "excludes": sorted(excludes),
        "strict": strict,
        "root_metadata": make_entry(resolved, resolved.parent, True) if strict else None,
        "entries": entries,
    }


def read_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        raise ValueError(f"Invalid workspace manifest: {path}")
    return payload


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    for key in ("schema_version", "root", "excludes", "strict", "root_metadata"):
        if before.get(key) != after.get(key):
            differences.append(
                {"path": f"<manifest:{key}>", "before": before.get(key), "after": after.get(key)}
            )
    before_by_path = {entry["path"]: entry for entry in before["entries"]}
    after_by_path = {entry["path"]: entry for entry in after["entries"]}
    for path in sorted(set(before_by_path) | set(after_by_path)):
        old = before_by_path.get(path)
        new = after_by_path.get(path)
        if old != new:
            differences.append({"path": path, "before": old, "after": new})
    return differences


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Snapshot or compare Cairnspan workspace manifests.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--root", type=Path, required=True)
    snapshot_parser.add_argument("--output", type=Path, required=True)
    snapshot_parser.add_argument("--exclude", action="append", default=[])
    snapshot_parser.add_argument("--strict", action="store_true")
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("before", type=Path)
    compare_parser.add_argument("after", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            payload = snapshot(args.root, set(args.exclude), strict=args.strict)
            write_json_atomic(args.output.resolve(), payload)
            print(json.dumps({"status": "created", "entry_count": len(payload["entries"]), "output": str(args.output.resolve())}))
            return 0
        before = read_manifest(args.before)
        after = read_manifest(args.after)
        differences = compare(before, after)
        print(json.dumps({"status": "changed" if differences else "identical", "differences": differences}, indent=2, sort_keys=True))
        return 1 if differences else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"workspace-manifest-error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
