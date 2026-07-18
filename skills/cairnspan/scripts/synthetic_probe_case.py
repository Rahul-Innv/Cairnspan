#!/usr/bin/env python3
"""Prepare and close immutable, owner-gated synthetic Codex capability proposals."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_manifest import inspect_png, validate_relative_path
from cli_version import probe_cli_version, version_probe_env
from hostile_write_profile import path_is_reparse
from start_codex_session import classify_image_tool_capability, parse_events
from workspace_manifest import compare, read_manifest, snapshot, write_json_atomic


SCHEMA_VERSION = "0.2"
MARKER_NAME = ".cairnspan-synthetic-probe.json"
PLAN_NAME = "proposal-plan.json"
PREPARED_MANIFEST_NAME = "workspace-prepared.json"
AFTER_MANIFEST_NAME = "workspace-after.json"
CLOSURE_NAME = "closure.json"
PROMPT_NAME = "prompt.txt"
VIEW_IMAGE_NAME = "synthetic-view-probe.png"
MODEL = "gpt-5.6-sol"
EFFORT = "xhigh"
MAX_OUTPUT_BYTES = 1_048_576
MAX_RECEIPT_BYTES = 12_000_000
MAX_ARTIFACT_BYTES = 5_000_000
APPROVAL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
SHELL_SUFFIXES = {".cmd", ".bat", ".ps1"}
SENSITIVE_PARTS = {".git", ".hg", ".svn", ".agents", ".claude", ".codex", ".cairnspan"}
CASE_ROOT_NAMES = {
    MARKER_NAME,
    PLAN_NAME,
    PREPARED_MANIFEST_NAME,
    AFTER_MANIFEST_NAME,
    CLOSURE_NAME,
    PROMPT_NAME,
    "workspace",
    "dry-run-receipts",
    "receipts",
}
PROBE_POLICIES: dict[str, dict[str, Any]] = {
    "codex-effort": {
        "sandbox": "read-only",
        "timeout_seconds": 120,
        "expected_final": "cairnspan-effort-ok",
        "model": MODEL,
        "effort": EFFORT,
        "strict_isolation": True,
        "require_no_tool_use": True,
        "required_image_capability": None,
        "expected_output": None,
    },
    "image-generation": {
        "sandbox": "workspace-write",
        "timeout_seconds": 420,
        "expected_final": "imagegen-ok",
        "model": None,
        "effort": None,
        "strict_isolation": False,
        "require_no_tool_use": False,
        "required_image_capability": "image-generation",
        "expected_output": ".cairnspan-imagegen/probe-image.png",
    },
    "image-view": {
        "sandbox": "read-only",
        "timeout_seconds": 120,
        "expected_final": "view-image-ok: blue-square-on-white",
        "model": None,
        "effort": None,
        "strict_isolation": False,
        "require_no_tool_use": False,
        "required_image_capability": "image-view",
        "expected_output": None,
    },
}


class SyntheticProbeError(ValueError):
    """Raised when proposal evidence cannot be trusted."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command_sha256(command: list[str]) -> str:
    encoded = json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def write_json_fresh(path: Path, value: dict[str, Any]) -> None:
    if os.path.lexists(path):
        raise SyntheticProbeError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, value)


def read_json_regular(path: Path, *, max_bytes: int = MAX_RECEIPT_BYTES) -> dict[str, Any]:
    if path_is_reparse(path) or not path.is_file():
        raise SyntheticProbeError(f"expected a regular non-reparse JSON file: {path}")
    stat_result = path.stat()
    if stat_result.st_nlink != 1 or stat_result.st_size > max_bytes:
        raise SyntheticProbeError(f"JSON file link count or size is invalid: {path}")
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise SyntheticProbeError(f"expected one JSON object: {path}")
    return value


def read_text_regular(path: Path, *, max_bytes: int = MAX_RECEIPT_BYTES) -> str:
    if path_is_reparse(path) or not path.is_file():
        raise SyntheticProbeError(f"expected a regular non-reparse text file: {path}")
    stat_result = path.stat()
    if stat_result.st_nlink != 1 or stat_result.st_size > max_bytes:
        raise SyntheticProbeError(f"text file link count or size is invalid: {path}")
    return path.read_text(encoding="utf-8", errors="strict")


def resolve_native_binary(value: Path) -> Path:
    if not value.is_absolute():
        raise SyntheticProbeError("--codex-bin must be an absolute path")
    resolved = value.resolve()
    if path_is_reparse(value) or not resolved.is_file():
        raise SyntheticProbeError("--codex-bin must be a regular non-reparse file")
    stat_result = resolved.stat()
    if stat_result.st_nlink != 1:
        raise SyntheticProbeError("--codex-bin must not be hardlinked")
    if resolved.suffix.casefold() in SHELL_SUFFIXES:
        raise SyntheticProbeError("--codex-bin must be native, not a shell wrapper")
    return resolved


def validate_case_root(root: Path) -> Path:
    if not root.is_absolute():
        raise SyntheticProbeError("--case-root must be absolute")
    if any(part.casefold() in SENSITIVE_PARTS for part in root.parts):
        raise SyntheticProbeError("--case-root cannot be inside a control or runtime directory")
    if os.path.lexists(root):
        raise SyntheticProbeError("--case-root must be fresh and must not already exist")
    parent = root.parent.resolve()
    if not parent.is_dir() or path_is_reparse(root.parent):
        raise SyntheticProbeError("--case-root parent must be an existing regular directory")
    return root


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def prompt_for(probe: str) -> str:
    if probe == "codex-effort":
        return (
            "This is a bounded synthetic public-data Codex typed-effort compatibility probe.\n\n"
            "Do not use tools, MCP, web search, image tools, shell, or workspace writes.\n"
            "Return exactly:\n\n"
            "cairnspan-effort-ok\n"
        )
    source_name = "imagegen.txt" if probe == "image-generation" else "image-view.txt"
    return (repo_root() / "docs" / "probes" / source_name).read_text(encoding="utf-8", errors="strict")


def png_chunk(name: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload))


def synthetic_view_png() -> bytes:
    width = height = 64
    rows: list[bytes] = []
    for y in range(height):
        pixels = bytearray()
        for x in range(width):
            pixels.extend((0, 102, 204) if 16 <= x < 48 and 16 <= y < 48 else (255, 255, 255))
        rows.append(b"\x00" + bytes(pixels))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9))
        + png_chunk(b"IEND", b"")
    )


def expected_command(plan: dict[str, Any], *, execute: bool) -> list[str]:
    policy = plan["policy"]
    request = plan["request"]
    command = [
        sys.executable,
        str(Path(__file__).resolve().with_name("start_codex_session.py")),
        "--cwd", plan["paths"]["workspace"],
        "--out-dir", plan["paths"]["receipts" if execute else "dry_run_receipts"],
        "--allow-outside-workspace-out-dir",
        "--origin-agent", "cairnspan.parent",
        "--run-depth", "0",
        "--max-depth", "1",
        "--codex-bin", plan["executable"]["path"],
        "--expected-cli-version", plan["executable"]["version"],
        "--prompt-file", plan["paths"]["prompt"],
        "--sandbox", policy["sandbox"],
        "--skip-git-repo-check",
        "--timeout-seconds", str(policy["timeout_seconds"]),
        "--max-output-bytes", str(policy["max_output_bytes"]),
    ]
    if request["model"]:
        command.extend(["--model", request["model"]])
    if request["effort"]:
        command.extend(["--effort", request["effort"]])
    if policy["strict_isolation"]:
        command.append("--strict-isolation")
    if policy["require_no_tool_use"]:
        command.append("--require-no-tool-use")
    if policy["required_image_capability"]:
        command.extend(["--require-image-capability", policy["required_image_capability"]])
    command.append("--execute" if execute else "--dry-run")
    return command


def prepare_case(
    args: argparse.Namespace,
    *,
    prompt_text: str | None = None,
    proposal_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = validate_case_root(args.case_root)
    binary = resolve_native_binary(args.codex_bin)
    observed_version = probe_cli_version(binary, root.parent, version_probe_env())
    if observed_version != args.expected_cli_version:
        raise SyntheticProbeError(
            f"Codex CLI version mismatch: expected {args.expected_cli_version!r}, observed {observed_version!r}"
        )

    policy = dict(PROBE_POLICIES[args.probe])
    proposal_id = uuid.uuid4().hex
    workspace = root / "workspace"
    dry_run_receipts = root / "dry-run-receipts"
    receipts = root / "receipts"
    prompt_path = root / PROMPT_NAME
    root.mkdir()
    workspace.mkdir()
    prompt_path.write_text(
        prompt_for(args.probe) if prompt_text is None else prompt_text,
        encoding="utf-8",
        newline="\n",
    )

    input_artifact: dict[str, Any] | None = None
    if args.probe == "image-view":
        image_path = workspace / VIEW_IMAGE_NAME
        image_path.write_bytes(synthetic_view_png())
        input_artifact = {
            "path": str(image_path),
            "relative_path": VIEW_IMAGE_NAME,
            "sha256": sha256_file(image_path),
            "bytes": image_path.stat().st_size,
            "media_type": "image/png",
        }

    prepared_manifest = snapshot(workspace, strict=True)
    write_json_fresh(root / PREPARED_MANIFEST_NAME, prepared_manifest)
    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "approval_state": "not-granted",
        "proposal_id": proposal_id,
        "probe_name": args.probe,
        "created_at": utc_now(),
        "proposal_context": proposal_context,
        "paths": {
            "case_root": str(root),
            "workspace": str(workspace),
            "dry_run_receipts": str(dry_run_receipts),
            "receipts": str(receipts),
            "prompt": str(prompt_path),
            "prepared_manifest": str(root / PREPARED_MANIFEST_NAME),
            "after_manifest": str(root / AFTER_MANIFEST_NAME),
            "closure": str(root / CLOSURE_NAME),
        },
        "executable": {
            "path": str(binary),
            "sha256": sha256_file(binary),
            "version": observed_version,
        },
        "request": {
            "model": policy.pop("model"),
            "effort": policy.pop("effort"),
            "prompt_sha256": sha256_file(prompt_path),
            "expected_final": policy.pop("expected_final"),
            "expected_output": policy.pop("expected_output"),
            "input_artifact": input_artifact,
        },
        "policy": {
            **policy,
            "max_output_bytes": MAX_OUTPUT_BYTES,
            "max_artifact_bytes": MAX_ARTIFACT_BYTES if args.probe == "image-generation" else None,
            "retry_budget": 0,
            "max_depth": 1,
            "max_fan_out": 1,
            "provider_launches_prepared": 0,
            "dry_run_required": True,
            "provider_honoring_claim": "not-established-by-request-receipt",
        },
        "prepared_manifest_sha256": sha256_file(root / PREPARED_MANIFEST_NAME),
    }
    plan["dry_run_command"] = expected_command(plan, execute=False)
    plan["execute_command"] = expected_command(plan, execute=True)
    plan["dry_run_command_sha256"] = command_sha256(plan["dry_run_command"])
    plan["execute_command_sha256"] = command_sha256(plan["execute_command"])
    write_json_fresh(root / PLAN_NAME, plan)
    marker = {
        "schema_version": SCHEMA_VERSION,
        "proposal_id": proposal_id,
        "probe_name": args.probe,
        "case_root": str(root),
        "plan_sha256": sha256_file(root / PLAN_NAME),
    }
    write_json_fresh(root / MARKER_NAME, marker)
    return plan


def require_exact_paths(root: Path, plan: dict[str, Any]) -> None:
    expected = {
        "case_root": root,
        "workspace": root / "workspace",
        "dry_run_receipts": root / "dry-run-receipts",
        "receipts": root / "receipts",
        "prompt": root / PROMPT_NAME,
        "prepared_manifest": root / PREPARED_MANIFEST_NAME,
        "after_manifest": root / AFTER_MANIFEST_NAME,
        "closure": root / CLOSURE_NAME,
    }
    for name, path in expected.items():
        if plan.get("paths", {}).get(name) != str(path):
            raise SyntheticProbeError(f"proposal path drift: {name}")


def validate_case_root_entries(root: Path) -> None:
    names: set[str] = set()
    for path in root.iterdir():
        if path_is_reparse(path):
            raise SyntheticProbeError(f"proposal root contains a reparse entry: {path.name}")
        names.add(path.name)
    unexpected = names - CASE_ROOT_NAMES
    if unexpected:
        raise SyntheticProbeError(f"proposal root contains unexpected entries: {sorted(unexpected)}")


def load_case(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not root.is_absolute() or path_is_reparse(root) or not root.is_dir():
        raise SyntheticProbeError("--case-root must be one existing regular absolute directory")
    marker = read_json_regular(root / MARKER_NAME)
    plan = read_json_regular(root / PLAN_NAME)
    validate_case_root_entries(root)
    if marker.get("schema_version") != SCHEMA_VERSION or plan.get("schema_version") != SCHEMA_VERSION:
        raise SyntheticProbeError("unsupported or mismatched proposal schema")
    if plan.get("status") != "prepared" or plan.get("approval_state") != "not-granted":
        raise SyntheticProbeError("proposal is not in the immutable prepared state")
    if marker.get("proposal_id") != plan.get("proposal_id") or marker.get("probe_name") != plan.get("probe_name"):
        raise SyntheticProbeError("proposal marker identity mismatch")
    if marker.get("case_root") != str(root) or marker.get("plan_sha256") != sha256_file(root / PLAN_NAME):
        raise SyntheticProbeError("proposal marker or plan hash mismatch")
    require_exact_paths(root, plan)
    if plan.get("probe_name") not in PROBE_POLICIES:
        raise SyntheticProbeError("unknown proposal probe name")
    prompt_path = Path(plan["paths"]["prompt"])
    if sha256_file(prompt_path) != plan.get("request", {}).get("prompt_sha256"):
        raise SyntheticProbeError("proposal prompt hash mismatch")
    prepared_path = Path(plan["paths"]["prepared_manifest"])
    if sha256_file(prepared_path) != plan.get("prepared_manifest_sha256"):
        raise SyntheticProbeError("prepared manifest hash mismatch")
    prepared = read_manifest(prepared_path)
    if prepared.get("strict") is not True or prepared.get("root") != plan["paths"]["workspace"]:
        raise SyntheticProbeError("prepared manifest policy or root mismatch")
    if expected_command(plan, execute=False) != plan.get("dry_run_command"):
        raise SyntheticProbeError("dry-run command drift")
    if expected_command(plan, execute=True) != plan.get("execute_command"):
        raise SyntheticProbeError("execute command drift")
    if command_sha256(plan["dry_run_command"]) != plan.get("dry_run_command_sha256"):
        raise SyntheticProbeError("dry-run command hash mismatch")
    if command_sha256(plan["execute_command"]) != plan.get("execute_command_sha256"):
        raise SyntheticProbeError("execute command hash mismatch")
    executable = Path(plan["executable"]["path"])
    if sha256_file(executable) != plan["executable"]["sha256"]:
        raise SyntheticProbeError("native executable hash drift")
    observed_version = probe_cli_version(executable, root, version_probe_env())
    if observed_version != plan["executable"]["version"]:
        raise SyntheticProbeError("native executable version drift")
    input_artifact = plan.get("request", {}).get("input_artifact")
    if plan["probe_name"] == "image-view":
        expected_input = Path(plan["paths"]["workspace"]) / VIEW_IMAGE_NAME
        if not input_artifact or input_artifact.get("path") != str(expected_input):
            raise SyntheticProbeError("synthetic input artifact path drift")
        if sha256_file(expected_input) != input_artifact.get("sha256"):
            raise SyntheticProbeError("synthetic input artifact hash drift")
        if expected_input.stat().st_size != input_artifact.get("bytes"):
            raise SyntheticProbeError("synthetic input artifact size drift")
    elif input_artifact is not None:
        raise SyntheticProbeError("unexpected synthetic input artifact")
    return marker, plan


def receipt_names(root: Path) -> set[str]:
    if path_is_reparse(root) or not root.is_dir():
        raise SyntheticProbeError(f"receipt root is missing or reparse-backed: {root}")
    names: set[str] = set()
    for path in root.iterdir():
        if path_is_reparse(path) or not path.is_file() or path.stat().st_nlink != 1:
            raise SyntheticProbeError(f"receipt entry is not one regular file: {path}")
        if path.stat().st_size > MAX_RECEIPT_BYTES:
            raise SyntheticProbeError(f"receipt entry exceeds the byte ceiling: {path}")
        names.add(path.name)
    return names


def validate_summary_common(summary: dict[str, Any], plan: dict[str, Any], *, dry_run: bool) -> None:
    paths = plan["paths"]
    request = plan["request"]
    policy = plan["policy"]
    out_dir = paths["dry_run_receipts" if dry_run else "receipts"]
    expected_values = {
        "schema_version": "0.14",
        "origin_agent": "cairnspan.parent",
        "target_agent": "codex",
        "target_workspace": paths["workspace"],
        "cwd": paths["workspace"],
        "codex_bin_resolved": plan["executable"]["path"],
        "target_cli_version": plan["executable"]["version"],
        "expected_cli_version": plan["executable"]["version"],
        "dry_run": dry_run,
        "sandbox": policy["sandbox"],
        "requested_model": request["model"],
        "requested_effort": request["effort"],
        "requested_image_capability": policy["required_image_capability"],
        "prompt_file": paths["prompt"],
        "prompt_sha256": request["prompt_sha256"],
        "out_dir": out_dir,
        "timeout_seconds": policy["timeout_seconds"],
        "max_output_bytes": policy["max_output_bytes"],
        "parent_run_id": None,
        "run_depth": 0,
        "max_depth": 1,
    }
    for name, expected in expected_values.items():
        if summary.get(name) != expected:
            raise SyntheticProbeError(f"summary field drift: {name}")
    expected_digest = plan["dry_run_command_sha256" if dry_run else "execute_command_sha256"]
    if summary.get("launcher_command_sha256") != expected_digest:
        raise SyntheticProbeError("launcher command digest does not match the proposal")


def validate_dry_run(plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(plan["paths"]["dry_run_receipts"])
    if receipt_names(root) != {"cairnspan-summary.json"}:
        raise SyntheticProbeError("dry-run receipt root contains unexpected files")
    summary = read_json_regular(root / "cairnspan-summary.json")
    validate_summary_common(summary, plan, dry_run=True)
    if summary.get("status") != "dry_run" or summary.get("return_code") is not None:
        raise SyntheticProbeError("dry-run summary is not a successful no-execution receipt")
    if summary.get("containment") != "not-run" or summary.get("terminal_event_count") != 0:
        raise SyntheticProbeError("dry-run summary falsely reports target execution")
    return summary


def validate_live_receipts(plan: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    root = Path(plan["paths"]["receipts"])
    required = {"cairnspan-summary.json", "events.jsonl", "transcript.log", "final.md"}
    if receipt_names(root) != required:
        raise SyntheticProbeError("live receipt root contains missing or unexpected files")
    summary = read_json_regular(root / "cairnspan-summary.json")
    validate_summary_common(summary, plan, dry_run=False)
    required_success = {
        "status": "succeeded",
        "return_code": 0,
        "terminal_event_count": 1,
        "parse_warnings": [],
        "mcp_tool_use_count": 0,
        "containment": "job-object",
        "descendant_cleanup_verified": True,
    }
    for name, expected in required_success.items():
        if summary.get(name) != expected:
            raise SyntheticProbeError(f"live summary is not closable: {name}")
    thread_id = summary.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id or summary.get("observed_thread_ids") != [thread_id]:
        raise SyntheticProbeError("live summary lacks one stable thread identity")
    parsed = parse_events(root / "events.jsonl")
    if parsed.warnings or parsed.terminal_event_count != 1 or parsed.thread_id != thread_id:
        raise SyntheticProbeError("independent event parsing rejected terminal identity or structure")
    if parsed.tool_names != summary.get("tool_names") or parsed.tool_use_count != summary.get("tool_use_count"):
        raise SyntheticProbeError("independent event parsing disagrees with tool receipts")
    if parsed.mcp_tool_use_count != summary.get("mcp_tool_use_count"):
        raise SyntheticProbeError("independent event parsing disagrees with MCP receipts")
    final_text = read_text_regular(root / "final.md")
    if final_text != parsed.final_message:
        raise SyntheticProbeError("final artifact disagrees with independently parsed events")
    expected_final = plan["request"]["expected_final"]
    if plan["probe_name"] == "image-generation":
        if not final_text.rstrip() or final_text.rstrip().splitlines()[-1] != expected_final:
            raise SyntheticProbeError("image-generation final marker is missing or not terminal")
    elif final_text != expected_final:
        raise SyntheticProbeError("final artifact does not match the exact proposal result")
    return summary, parsed


def validate_probe_result(plan: dict[str, Any], summary: dict[str, Any], parsed: Any) -> dict[str, Any]:
    probe = plan["probe_name"]
    request = plan["request"]
    workspace = Path(plan["paths"]["workspace"])
    before = read_manifest(Path(plan["paths"]["prepared_manifest"]))
    after = snapshot(workspace, strict=True)
    differences = compare(before, after)
    changed = {item["path"] for item in differences}
    result: dict[str, Any] = {"changed_paths": sorted(changed)}

    if probe in {"codex-effort", "image-view"}:
        if changed:
            raise SyntheticProbeError(f"no-edit probe changed the workspace: {sorted(changed)}")
    else:
        relative = request["expected_output"]
        parent = Path(relative).parent.as_posix()
        expected = {relative, parent, "<manifest:root_metadata>"}
        required = {relative, parent}
        if not required.issubset(changed) or not changed.issubset(expected):
            raise SyntheticProbeError(f"image-generation workspace delta is invalid: {sorted(changed)}")
        artifact, normalized = validate_relative_path(workspace / Path(relative), workspace)
        if artifact.stat().st_size <= 0 or artifact.stat().st_size > plan["policy"]["max_artifact_bytes"]:
            raise SyntheticProbeError("generated PNG exceeds the artifact byte policy")
        image = inspect_png(
            artifact,
            max_width=4096,
            max_height=4096,
            max_pixels=16_777_216,
            allow_metadata=False,
        )
        result["artifact"] = {
            "relative_path": normalized,
            "sha256": sha256_file(artifact),
            "bytes": artifact.stat().st_size,
            "validation": image,
        }

    if probe == "codex-effort":
        if summary.get("tool_use_count") != 0 or parsed.tool_names:
            raise SyntheticProbeError("typed-effort probe used a tool")
        command = summary.get("command")
        mapping = f'model_reasoning_effort="{request["effort"]}"'
        if not isinstance(command, list) or command.count("--model") != 1 or command.count(mapping) != 1:
            raise SyntheticProbeError("typed model/effort command mapping is not exact")
        if "--profile" in command:
            raise SyntheticProbeError("typed-effort command unexpectedly used a profile")
        result["native_cli_acceptance"] = "passed"
        result["provider_honoring"] = "unknown"
    else:
        required_capability = plan["policy"]["required_image_capability"]
        capability, reason = classify_image_tool_capability(parsed, required_capability)
        expected = f"ok({required_capability})"
        if capability != expected or summary.get("codex_image_tools") != expected or reason is not None:
            raise SyntheticProbeError("required image capability did not close with observed tool evidence")
        result["capability"] = expected
    return {"after_manifest": after, "result": result}


def close_case(args: argparse.Namespace) -> dict[str, Any]:
    if not APPROVAL_PATTERN.fullmatch(args.approval_reference):
        raise SyntheticProbeError(f"--approval-reference must match {APPROVAL_PATTERN.pattern}")
    root = args.case_root.resolve()
    _, plan = load_case(root)
    plan_sha256 = sha256_file(root / PLAN_NAME)
    if args.approved_plan_sha256 != plan_sha256:
        raise SyntheticProbeError("--approved-plan-sha256 does not match the immutable proposal plan")
    if os.path.lexists(root / CLOSURE_NAME) or os.path.lexists(root / AFTER_MANIFEST_NAME):
        raise SyntheticProbeError("proposal closure outputs already exist")
    dry_summary = validate_dry_run(plan)
    live_summary, parsed = validate_live_receipts(plan)
    validated = validate_probe_result(plan, live_summary, parsed)
    write_json_fresh(root / AFTER_MANIFEST_NAME, validated["after_manifest"])
    closure = {
        "schema_version": SCHEMA_VERSION,
        "status": "closed",
        "proposal_id": plan["proposal_id"],
        "probe_name": plan["probe_name"],
        "closed_at": utc_now(),
        "approval_reference": args.approval_reference,
        "approval_attestation": "operator-supplied-reference-not-independently-verifiable",
        "approved_plan_sha256": args.approved_plan_sha256,
        "plan_sha256": plan_sha256,
        "dry_run_summary_sha256": sha256_file(Path(plan["paths"]["dry_run_receipts"]) / "cairnspan-summary.json"),
        "live_summary_sha256": sha256_file(Path(plan["paths"]["receipts"]) / "cairnspan-summary.json"),
        "events_sha256": sha256_file(Path(plan["paths"]["receipts"]) / "events.jsonl"),
        "final_sha256": sha256_file(Path(plan["paths"]["receipts"]) / "final.md"),
        "after_manifest_sha256": sha256_file(root / AFTER_MANIFEST_NAME),
        "dry_run_id": dry_summary.get("run_id"),
        "live_run_id": live_summary.get("run_id"),
        "thread_id": live_summary.get("thread_id"),
        "executable": plan["executable"],
        "result": validated["result"],
    }
    write_json_fresh(root / CLOSURE_NAME, closure)
    return closure


def verify_closed_case(root: Path) -> dict[str, Any]:
    _, plan = load_case(root)
    closure = read_json_regular(root / CLOSURE_NAME)
    stored_after = read_json_regular(root / AFTER_MANIFEST_NAME)
    if not APPROVAL_PATTERN.fullmatch(str(closure.get("approval_reference", ""))):
        raise SyntheticProbeError("closed proposal has an invalid approval reference")
    dry_summary = validate_dry_run(plan)
    live_summary, parsed = validate_live_receipts(plan)
    validated = validate_probe_result(plan, live_summary, parsed)
    if compare(stored_after, validated["after_manifest"]):
        raise SyntheticProbeError("stored after-manifest no longer matches the current workspace")
    expected = {
        "schema_version": SCHEMA_VERSION,
        "status": "closed",
        "proposal_id": plan["proposal_id"],
        "probe_name": plan["probe_name"],
        "approval_attestation": "operator-supplied-reference-not-independently-verifiable",
        "approved_plan_sha256": sha256_file(root / PLAN_NAME),
        "plan_sha256": sha256_file(root / PLAN_NAME),
        "dry_run_summary_sha256": sha256_file(Path(plan["paths"]["dry_run_receipts"]) / "cairnspan-summary.json"),
        "live_summary_sha256": sha256_file(Path(plan["paths"]["receipts"]) / "cairnspan-summary.json"),
        "events_sha256": sha256_file(Path(plan["paths"]["receipts"]) / "events.jsonl"),
        "final_sha256": sha256_file(Path(plan["paths"]["receipts"]) / "final.md"),
        "after_manifest_sha256": sha256_file(root / AFTER_MANIFEST_NAME),
        "dry_run_id": dry_summary.get("run_id"),
        "live_run_id": live_summary.get("run_id"),
        "thread_id": live_summary.get("thread_id"),
        "executable": plan["executable"],
        "result": validated["result"],
    }
    for name, value in expected.items():
        if closure.get(name) != value:
            raise SyntheticProbeError(f"closure field or evidence drift: {name}")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "verified",
        "proposal_id": plan["proposal_id"],
        "probe_name": plan["probe_name"],
        "closure_sha256": sha256_file(root / CLOSURE_NAME),
        "approval_reference": closure["approval_reference"],
        "case_root": str(root),
        "plan_sha256": sha256_file(root / PLAN_NAME),
        "executable": plan["executable"],
        "result": validated["result"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    prepare = subparsers.add_parser("prepare", help="prepare one immutable proposal")
    prepare.add_argument("--case-root", type=Path, required=True)
    prepare.add_argument("--probe", choices=tuple(PROBE_POLICIES), required=True)
    prepare.add_argument("--codex-bin", type=Path, required=True)
    prepare.add_argument("--expected-cli-version", required=True)
    close = subparsers.add_parser("close", help="close existing dry/live evidence")
    close.add_argument("--case-root", type=Path, required=True)
    close.add_argument("--approval-reference", required=True)
    close.add_argument("--approved-plan-sha256", required=True)
    verify = subparsers.add_parser("verify", help="independently re-verify a closed proposal")
    verify.add_argument("--case-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "prepare":
            value = prepare_case(args)
        elif args.action == "close":
            value = close_case(args)
        else:
            value = verify_closed_case(args.case_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
