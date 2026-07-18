"""Validated file mailbox for Cairnspan fallback handoffs.

The mailbox is a fallback contract for environments where a live target-agent
launcher is unavailable or intentionally disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
AGENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
REQUEST_STATUSES = {"pending", "claimed", "running", "succeeded", "failed", "cancelled"}
RESPONSE_STATUSES = {"succeeded", "failed", "cancelled"}
SANDBOX_VALUES = {"read-only", "workspace-write", "danger-full-access"}
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL", "CLOCK$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
REQUEST_FIELDS = {
    "id", "origin_agent", "target_agent", "created_at", "prompt", "prompt_ref",
    "sandbox", "status", "result_ref", "error", "parent_run_id", "run_depth", "max_depth",
}
RESPONSE_FIELDS = {
    "id", "request_id", "origin_agent", "target_agent", "created_at", "status",
    "result_ref", "final", "error",
}
MAX_PROMPT_BYTES = 262_144
MAX_REF_CHARS = 1_024
MAX_MESSAGE_CHARS = 16_384


class SchemaError(ValueError):
    """Raised when a mailbox request or response does not match the contract."""


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def is_reparse_point(path: Path) -> bool:
    try:
        stat_result = path.lstat()
    except OSError:
        return False
    attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_flag = getattr(__import__("stat"), "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def require_regular_file(path: Path, root: Path, label: str) -> Path:
    resolved_root = root.resolve(strict=True)
    if is_reparse_point(root):
        raise SchemaError(f"{label} root cannot be a link or reparse point")
    resolved = path.resolve(strict=True)
    if not path_is_within(resolved, resolved_root):
        raise SchemaError(f"{label} escapes the mailbox root")
    if is_reparse_point(path) or not resolved.is_file():
        raise SchemaError(f"{label} must be a regular non-reparse file")
    if resolved.stat().st_nlink != 1:
        raise SchemaError(f"{label} cannot be hardlinked")
    return resolved


def validate_id(value: Any, field: str = "id") -> None:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise SchemaError(f"{field} must match {ID_PATTERN.pattern}")
    if value.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        raise SchemaError(f"{field} cannot use a Windows reserved filename")


def validate_agent(value: Any, field: str) -> None:
    if not isinstance(value, str) or not AGENT_PATTERN.fullmatch(value):
        raise SchemaError(f"{field} must be a non-empty agent id")


def validate_created_at(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise SchemaError("created_at must be an ISO timestamp string")
    parseable = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise SchemaError("created_at must be parseable ISO-8601") from exc
    if parsed.tzinfo is None:
        raise SchemaError("created_at must include a timezone")


def validate_status(value: Any, allowed: set[str], field: str = "status") -> None:
    if value not in allowed:
        raise SchemaError(f"{field} must be one of: {', '.join(sorted(allowed))}")


def validate_optional_ref(value: Any, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value or len(value) > MAX_REF_CHARS:
        raise SchemaError(f"{field} must be a non-empty bounded string when present")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", value):
        raise SchemaError(f"{field} must be a relative, non-traversing artifact reference")


def reject_unknown_fields(payload: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise SchemaError(f"unknown fields are not allowed: {', '.join(unknown)}")


def validate_request(payload: dict[str, Any]) -> None:
    reject_unknown_fields(payload, REQUEST_FIELDS)
    validate_id(payload.get("id"))
    validate_agent(payload.get("origin_agent"), "origin_agent")
    validate_agent(payload.get("target_agent"), "target_agent")
    validate_created_at(payload.get("created_at"))
    validate_status(payload.get("status"), REQUEST_STATUSES)
    if payload.get("sandbox") not in SANDBOX_VALUES:
        raise SchemaError(f"sandbox must be one of: {', '.join(sorted(SANDBOX_VALUES))}")

    has_prompt = isinstance(payload.get("prompt"), str) and bool(payload.get("prompt"))
    has_prompt_ref = isinstance(payload.get("prompt_ref"), str) and bool(payload.get("prompt_ref"))
    if has_prompt == has_prompt_ref:
        raise SchemaError("provide exactly one of prompt or prompt_ref")
    if has_prompt and len(payload["prompt"].encode("utf-8")) > MAX_PROMPT_BYTES:
        raise SchemaError(f"prompt exceeds {MAX_PROMPT_BYTES} UTF-8 bytes")
    if has_prompt_ref:
        validate_optional_ref(payload.get("prompt_ref"), "prompt_ref")

    validate_optional_ref(payload.get("result_ref"), "result_ref")
    error = payload.get("error")
    if error is not None and (not isinstance(error, str) or not error or len(error) > MAX_MESSAGE_CHARS):
        raise SchemaError("error must be a non-empty bounded string when present")
    if payload.get("parent_run_id") is not None:
        validate_id(payload.get("parent_run_id"), "parent_run_id")
    run_depth = payload.get("run_depth", 0)
    max_depth = payload.get("max_depth", 1)
    if not isinstance(run_depth, int) or run_depth < 0:
        raise SchemaError("run_depth must be a non-negative integer")
    if not isinstance(max_depth, int) or max_depth < 0:
        raise SchemaError("max_depth must be a non-negative integer")
    if run_depth > max_depth:
        raise SchemaError("run_depth cannot exceed max_depth")
    if run_depth > 0 and payload.get("parent_run_id") is None:
        raise SchemaError("run_depth greater than zero requires parent_run_id")
    if payload.get("parent_run_id") is not None and run_depth == 0:
        raise SchemaError("parent_run_id requires run_depth greater than zero")


def validate_response(payload: dict[str, Any]) -> None:
    reject_unknown_fields(payload, RESPONSE_FIELDS)
    validate_id(payload.get("id"))
    validate_id(payload.get("request_id"), "request_id")
    validate_agent(payload.get("origin_agent"), "origin_agent")
    validate_agent(payload.get("target_agent"), "target_agent")
    validate_created_at(payload.get("created_at"))
    validate_status(payload.get("status"), RESPONSE_STATUSES)
    validate_optional_ref(payload.get("result_ref"), "result_ref")
    final = payload.get("final")
    error = payload.get("error")
    if final is not None and (not isinstance(final, str) or not final or len(final) > MAX_MESSAGE_CHARS):
        raise SchemaError("final must be a non-empty bounded string when present")
    if error is not None and (not isinstance(error, str) or not error or len(error) > MAX_MESSAGE_CHARS):
        raise SchemaError("error must be a non-empty bounded string when present")

    if payload["status"] == "succeeded" and not (payload.get("result_ref") or payload.get("final")):
        raise SchemaError("succeeded responses require result_ref or final")
    if payload["status"] == "failed" and not payload.get("error"):
        raise SchemaError("failed responses require error")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SchemaError("mailbox file must contain a JSON object")
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any], overwrite: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("x", encoding="utf-8", newline="") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temp_path, path)
        else:
            try:
                os.link(temp_path, path)
            except FileExistsError as exc:
                raise FileExistsError(f"Mailbox file already exists: {path}") from exc
        return path
    finally:
        if temp_path.exists():
            temp_path.unlink()


def ensure_mailbox_folder(mailbox_dir: Path, folder: str) -> Path:
    mailbox_dir.mkdir(parents=True, exist_ok=True)
    if is_reparse_point(mailbox_dir) or not mailbox_dir.is_dir():
        raise SchemaError("mailbox root must be a real directory")
    root = mailbox_dir.resolve(strict=True)
    folder_path = mailbox_dir / folder
    folder_path.mkdir(exist_ok=True)
    if is_reparse_point(folder_path) or not folder_path.is_dir():
        raise SchemaError("mailbox folder must be a real directory")
    resolved = folder_path.resolve(strict=True)
    if not path_is_within(resolved, root):
        raise SchemaError("mailbox folder escapes mailbox root")
    return resolved


def mailbox_path(mailbox_dir: Path, folder: str, item_id: str, create_folder: bool = False) -> Path:
    validate_id(item_id)
    base = ensure_mailbox_folder(mailbox_dir, folder) if create_folder else (mailbox_dir / folder).resolve()
    path = (base / f"{item_id}.json").resolve()
    if not path_is_within(path, base):
        raise SchemaError("mailbox path escapes mailbox folder")
    return path


def write_request(mailbox_dir: Path, payload: dict[str, Any], overwrite: bool = False) -> Path:
    validate_request(payload)
    return write_json_atomic(mailbox_path(mailbox_dir, "requests", payload["id"], create_folder=True), payload, overwrite)


def write_response(mailbox_dir: Path, payload: dict[str, Any], overwrite: bool = False) -> Path:
    validate_response(payload)
    return write_json_atomic(mailbox_path(mailbox_dir, "responses", payload["id"], create_folder=True), payload, overwrite)


def validate_file(kind: str, path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if kind == "request":
        validate_request(payload)
    elif kind == "response":
        validate_response(payload)
    else:
        raise SchemaError("kind must be request or response")
    return payload


def read_pinned_json(kind: str, path: Path, root: Path, label: str) -> tuple[Path, dict[str, Any], str]:
    """Read, validate, and hash one immutable mailbox file from the same open handle."""
    resolved = require_regular_file(path, root, label)
    with resolved.open("rb") as handle:
        before = os.fstat(handle.fileno())
        raw = handle.read()
        after = os.fstat(handle.fileno())
    try:
        current = resolved.lstat()
    except OSError as exc:
        raise SchemaError(f"{label} changed while it was read") from exc
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    path_identity = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
    if identity_before != identity_after or identity_after != path_identity:
        raise SchemaError(f"{label} changed while it was read")
    if is_reparse_point(resolved) or current.st_nlink != 1:
        raise SchemaError(f"{label} must remain a regular non-linked file")
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except UnicodeDecodeError as exc:
        raise SchemaError(f"{label} must be strict UTF-8") from exc
    if not isinstance(payload, dict):
        raise SchemaError(f"{label} must contain one JSON object")
    if kind == "request":
        validate_request(payload)
    elif kind == "response":
        validate_response(payload)
    else:
        raise SchemaError("kind must be request or response")
    return resolved, payload, hashlib.sha256(raw).hexdigest()


def resolve_mailbox_ref(mailbox_dir: Path, value: str, label: str) -> Path:
    validate_optional_ref(value, label)
    relative = Path(value.replace("/", os.sep))
    return require_regular_file(mailbox_dir / relative, mailbox_dir, label)


def validate_exchange(mailbox_dir: Path, request_path: Path, response_path: Path) -> dict[str, Any]:
    root = mailbox_dir.resolve(strict=True)
    if is_reparse_point(mailbox_dir) or not root.is_dir():
        raise SchemaError("mailbox root must be a real directory")
    request_file, request, request_sha256 = read_pinned_json("request", request_path, root, "request file")
    response_file, response, response_sha256 = read_pinned_json("response", response_path, root, "response file")

    if request_file != mailbox_path(root, "requests", request["id"]):
        raise SchemaError("request path does not match request id")
    if response_file != mailbox_path(root, "responses", response["id"]):
        raise SchemaError("response path does not match response id")
    if request.get("status") != "pending":
        raise SchemaError("immutable mailbox requests must remain pending")
    if response["request_id"] != request["id"]:
        raise SchemaError("response request_id does not match request id")
    if response["origin_agent"] != request["target_agent"]:
        raise SchemaError("response origin_agent must equal request target_agent")
    if response["target_agent"] != request["origin_agent"]:
        raise SchemaError("response target_agent must equal request origin_agent")

    prompt_ref = request.get("prompt_ref")
    if prompt_ref:
        resolve_mailbox_ref(root, prompt_ref, "prompt_ref")
    result_ref = response.get("result_ref")
    if result_ref:
        resolve_mailbox_ref(root, result_ref, "result_ref")

    matching_responses: list[Path] = []
    responses_dir = root / "responses"
    for candidate in sorted(responses_dir.glob("*.json")):
        candidate_file, candidate_payload, _ = read_pinned_json("response", candidate, root, "response candidate")
        if candidate_payload.get("request_id") == request["id"]:
            matching_responses.append(candidate_file)
    if matching_responses != [response_file]:
        raise SchemaError("request must have exactly one matching terminal response")

    return {
        "status": "valid",
        "request_id": request["id"],
        "response_id": response["id"],
        "origin_agent": request["origin_agent"],
        "target_agent": request["target_agent"],
        "request_sha256": request_sha256,
        "response_sha256": response_sha256,
        "request_prompt_sha256": hashlib.sha256(request["prompt"].encode("utf-8")).hexdigest() if request.get("prompt") else None,
        "response_final_sha256": hashlib.sha256(response["final"].encode("utf-8")).hexdigest() if response.get("final") else None,
        "response_status": response["status"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Cairnspan mailbox JSON files.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate a request or response file")
    validate.add_argument("kind", choices=("request", "response"))
    validate.add_argument("path", type=Path)
    exchange = subparsers.add_parser("validate-exchange", help="Validate one linked mailbox exchange")
    exchange.add_argument("--mailbox-dir", type=Path, required=True)
    exchange.add_argument("--request", type=Path, required=True)
    exchange.add_argument("--response", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            validate_file(args.kind, args.path)
            print(f"mailbox-{args.kind}-ok")
        else:
            value = validate_exchange(args.mailbox_dir, args.request, args.response)
            print(json.dumps(value, indent=2, sort_keys=True))
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        label = args.kind if args.command == "validate" else "exchange"
        print(f"mailbox-{label}-invalid: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
