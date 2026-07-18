"""Run a bounded parent-orchestrated Codex/Claude two-edge closure probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from cli_version import probe_cli_version, version_probe_env

from workspace_manifest import compare, is_reparse_point, snapshot, write_json_atomic


SCHEMA_VERSION = "0.2"
MAX_CONTROL_CAPTURE_BYTES = 2_000_000
EDGE_RECEIPT_NAMES = ("events.jsonl", "transcript.log", "final.md", "cairnspan-summary.json")
SHELL_WRAPPER_SUFFIXES = {".cmd", ".bat", ".ps1"}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CODEX_LAUNCHER = Path(__file__).with_name("start_codex_session.py")
CLAUDE_LAUNCHER = Path(__file__).with_name("start_claude_session.py")
ROUTE_ORDERS = {
    "codex-first": ("codex", "claude"),
    "claude-first": ("claude", "codex"),
}
AGENT_DISPLAY_NAMES = {"codex": "codex", "claude": "claude-code"}


class RouteError(Exception):
    def __init__(self, kind: str, message: str, return_code: int = 1) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.return_code = return_code


@dataclass
class LauncherResult:
    return_code: int
    stdout: bytes
    stderr: bytes
    elapsed_seconds: float


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_route_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"route-{stamp}-{uuid.uuid4().hex[:8]}"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def executable_identity(path: Path) -> dict[str, Any]:
    stat_result = path.stat()
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "size": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
        "file_id": [stat_result.st_dev, stat_result.st_ino],
        "version": probe_cli_version(path, path.parent, version_probe_env()),
    }


def write_bytes_atomic(path: Path, value: bytes) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def write_text_atomic(path: Path, value: str) -> None:
    write_bytes_atomic(path, value.encode("utf-8"))


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def path_is_reparse(path: Path) -> bool:
    try:
        return path.is_symlink() or is_reparse_point(path.lstat())
    except OSError:
        return False


def validate_existing_ancestors(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:-1]:
        current /= part
        if os.path.lexists(current) and path_is_reparse(current):
            raise RouteError("path_policy", f"Route output ancestor is a link or reparse point: {current}", 2)


def resolve_workspace(value: Path, label: str) -> Path:
    resolved = value.resolve()
    if not resolved.is_dir():
        raise RouteError("config", f"{label} workspace does not exist or is not a directory: {resolved}", 2)
    if path_is_reparse(value.absolute()):
        raise RouteError("path_policy", f"{label} workspace root cannot be a link or reparse point", 2)
    return resolved


def resolve_executable(value: Path, label: str, allow_shell_wrapper: bool) -> Path:
    if not value.is_absolute():
        raise RouteError("config", f"{label} executable must be an absolute path", 2)
    try:
        resolved = value.resolve(strict=True)
    except OSError as exc:
        raise RouteError("config", f"{label} executable cannot be resolved: {exc}", 2) from exc
    if not resolved.is_file():
        raise RouteError("config", f"{label} executable is not a file: {resolved}", 2)
    if path_is_reparse(value):
        raise RouteError("path_policy", f"{label} executable cannot be a link or reparse point", 2)
    if resolved.suffix.lower() in SHELL_WRAPPER_SUFFIXES and not allow_shell_wrapper:
        raise RouteError("path_policy", f"{label} executable must be native, not a shell wrapper", 2)
    return resolved


def positive_int(value: int, label: str) -> int:
    if value <= 0:
        raise RouteError("config", f"{label} must be greater than zero", 2)
    return value


def positive_decimal(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise RouteError("config", f"{label} must be a finite positive decimal", 2) from exc
    if not parsed.is_finite() or parsed <= 0:
        raise RouteError("config", f"{label} must be a finite positive decimal", 2)
    return parsed


def safe_read_json(path: Path, max_bytes: int = 2_000_000) -> dict[str, Any]:
    if not path.is_file() or path_is_reparse(path):
        raise RouteError("receipt", f"Expected a regular receipt file: {path}")
    stat_result = path.stat()
    if stat_result.st_nlink != 1:
        raise RouteError("receipt", f"Receipt file has multiple hardlinks: {path}")
    if stat_result.st_size > max_bytes:
        raise RouteError("receipt", f"Receipt file exceeds {max_bytes} bytes: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RouteError("receipt", f"Invalid JSON receipt {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RouteError("receipt", f"Receipt must be a JSON object: {path}")
    return payload


def safe_read_text(path: Path, max_bytes: int) -> str:
    if not path.is_file() or path_is_reparse(path):
        raise RouteError("receipt", f"Expected a regular artifact file: {path}")
    stat_result = path.stat()
    if stat_result.st_nlink != 1:
        raise RouteError("receipt", f"Artifact file has multiple hardlinks: {path}")
    if stat_result.st_size > max_bytes:
        raise RouteError("receipt", f"Artifact exceeds {max_bytes} bytes: {path}")
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise RouteError("receipt", f"Artifact is not valid UTF-8: {path}") from exc


def terminate_launcher(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        proc.kill()
        proc.wait(timeout=10)


def run_launcher(command: list[str], timeout_seconds: float) -> LauncherResult:
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        terminate_launcher(proc)
        raise RouteError("route_timeout", "Route deadline expired while a launcher was running", 124) from exc
    except BaseException:
        terminate_launcher(proc)
        raise
    if len(stdout) + len(stderr) > MAX_CONTROL_CAPTURE_BYTES:
        raise RouteError("control_output_limit", "Launcher control output exceeded its fixed limit", 125)
    return LauncherResult(proc.returncode, stdout, stderr, round(time.monotonic() - started, 3))


def validate_receipt_paths(edge_dir: Path) -> None:
    for name in EDGE_RECEIPT_NAMES:
        path = edge_dir / name
        if not path.is_file() or path_is_reparse(path):
            raise RouteError("receipt", f"Missing or linked edge receipt: {path}")
        if path.stat().st_nlink != 1:
            raise RouteError("receipt", f"Edge receipt has multiple hardlinks: {path}")


def edge_output_bytes(edge_dir: Path) -> int:
    total = 0
    for name in ("events.jsonl", "transcript.log", "final.md"):
        path = edge_dir / name
        if not path.is_file() or path_is_reparse(path):
            raise RouteError("receipt", f"Missing or linked edge artifact: {path}")
        total += path.stat().st_size
    return total


def decimal_from_summary(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise RouteError("receipt", "Edge receipt contains an invalid cost value") from exc
    if not parsed.is_finite() or parsed < 0:
        raise RouteError("receipt", "Edge receipt contains an invalid cost value")
    return parsed


def validate_edge_summary(
    payload: dict[str, Any],
    *,
    agent: str,
    route_id: str,
    workspace: Path,
    edge_dir: Path,
    prompt_sha256: str,
    expected_cli_version: str,
    execute: bool,
) -> None:
    expected_target = "codex" if agent == "codex" else "claude-code"
    expected_status = "succeeded" if execute else "dry_run"
    required = {
        "target_agent": expected_target,
        "parent_run_id": route_id,
        "run_depth": 1,
        "max_depth": 1,
        "origin_agent": "cairnspan-route",
        "prompt_sha256": prompt_sha256,
        "status": expected_status,
        "dry_run": not execute,
        "target_cli_version": expected_cli_version,
        "expected_cli_version": expected_cli_version,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise RouteError("receipt_linkage", f"{agent} receipt field {key!r} did not match the route")
    for key, expected_path in (
        ("target_workspace", workspace),
        ("cwd", workspace),
        ("out_dir", edge_dir),
        ("summary_file", edge_dir / "cairnspan-summary.json"),
        ("final_message", edge_dir / "final.md"),
    ):
        value = payload.get(key)
        if not isinstance(value, str) or Path(value).resolve() != expected_path.resolve():
            raise RouteError("receipt_linkage", f"{agent} receipt path {key!r} did not match the route")
    if execute:
        if payload.get("return_code") != 0:
            raise RouteError("target_failure", f"{agent} edge returned a nonzero target code")
        if payload.get("containment") != "job-object":
            raise RouteError("receipt", f"{agent} edge did not record strong process containment")
        identity = payload.get("thread_id") if agent == "codex" else payload.get("session_id")
        if not isinstance(identity, str) or not identity:
            raise RouteError("receipt", f"{agent} edge did not record its target session identity")
    if agent == "codex":
        if payload.get("sandbox") != "read-only":
            raise RouteError("policy", "Codex edge did not use the read-only sandbox")
        if payload.get("strict_isolation") is not True:
            raise RouteError("policy", "Codex edge did not preserve strict isolation")
        if execute and (payload.get("tool_use_count") != 0 or payload.get("mcp_tool_use_count") != 0):
            raise RouteError("policy", "Codex edge emitted forbidden tool-use events")
    if agent == "claude":
        if payload.get("tools") != "" or payload.get("safe_mode") is not True:
            raise RouteError("policy", "Claude edge did not preserve the empty-tool safe-mode policy")
        if payload.get("strict_mcp_config") is not True:
            raise RouteError("policy", "Claude edge did not preserve strict MCP policy")
        if execute:
            init = payload.get("init_capabilities")
            if not isinstance(init, dict):
                raise RouteError("policy", "Claude edge did not record init capabilities")
            for key in ("tools", "mcp_servers", "plugins", "skills", "slash_commands"):
                if init.get(key) not in ([], None):
                    raise RouteError("policy", f"Claude edge advertised forbidden capability metadata: {key}")
            if payload.get("tool_use_count") != 0 or payload.get("mcp_tool_use_count") != 0:
                raise RouteError("policy", "Claude edge emitted forbidden tool-use events")


def make_edge_record(
    agent: str,
    result: LauncherResult,
    payload: dict[str, Any],
    edge_dir: Path,
) -> dict[str, Any]:
    final_path = edge_dir / "final.md"
    summary_path = edge_dir / "cairnspan-summary.json"
    identity = payload.get("thread_id") if agent == "codex" else payload.get("session_id")
    return {
        "agent": agent,
        "launcher_return_code": result.return_code,
        "launcher_elapsed_seconds": result.elapsed_seconds,
        "target_run_id": payload.get("run_id"),
        "target_identity": identity,
        "status": payload.get("status"),
        "prompt_sha256": payload.get("prompt_sha256"),
        "final_sha256": sha256_file(final_path) if final_path.is_file() else None,
        "summary_sha256": sha256_file(summary_path),
        "output_bytes": edge_output_bytes(edge_dir),
        "reported_cost_usd": str(decimal_from_summary(payload.get("total_cost_usd")))
        if payload.get("total_cost_usd") is not None
        else None,
        "descendant_cleanup_verified": bool(payload.get("descendant_cleanup_verified", False)),
        "containment": payload.get("containment"),
        "target_cli_version": payload.get("target_cli_version"),
        "cleaned_descendant_names": sorted(
            {
                str(item.get("name"))
                for item in payload.get("process_leak_details", [])
                if isinstance(item, dict) and item.get("name")
            }
        ),
        "receipt_dir": str(edge_dir),
    }


def edge_command(
    *,
    agent: str,
    workspace: Path,
    edge_dir: Path,
    prompt_file: Path,
    executable: Path,
    expected_cli_version: str,
    route_id: str,
    timeout_seconds: int,
    max_output_bytes: int,
    claude_budget: Decimal,
    execute: bool,
    allow_shell_wrapper: bool,
) -> list[str]:
    if agent == "codex":
        command = [
            sys.executable,
            str(CODEX_LAUNCHER),
            "--cwd",
            str(workspace),
            "--out-dir",
            str(edge_dir),
            "--allow-outside-workspace-out-dir",
            "--prompt-file",
            str(prompt_file),
            "--sandbox",
            "read-only",
            "--strict-isolation",
            "--require-no-tool-use",
            "--skip-git-repo-check",
            "--codex-bin",
            str(executable),
            "--expected-cli-version",
            expected_cli_version,
        ]
    else:
        command = [
            sys.executable,
            str(CLAUDE_LAUNCHER),
            "--cwd",
            str(workspace),
            "--out-dir",
            str(edge_dir),
            "--allow-outside-workspace-out-dir",
            "--prompt-file",
            str(prompt_file),
            "--permission-mode",
            "dontAsk",
            "--tools=",
            "--strict-mcp-config",
            "--safe-mode",
            "--no-session-persistence",
            "--max-budget-usd",
            format(claude_budget, "f"),
            "--claude-bin",
            str(executable),
            "--expected-cli-version",
            expected_cli_version,
        ]
    command.extend(
        [
            "--origin-agent",
            "cairnspan-route",
            "--parent-run-id",
            route_id,
            "--run-depth",
            "1",
            "--max-depth",
            "1",
            "--timeout-seconds",
            str(timeout_seconds),
            "--max-output-bytes",
            str(max_output_bytes),
        ]
    )
    if allow_shell_wrapper:
        command.append("--allow-shell-wrapper")
    command.append("--execute" if execute else "--dry-run")
    return command


def manifest_record(root: Path, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    differences = compare(before, after)
    return {
        "root": str(root),
        "status": "identical" if not differences else "changed",
        "difference_count": len(differences),
        "difference_paths": [item["path"] for item in differences],
    }


def validate_disposable_workspace(manifest: dict[str, Any], label: str) -> None:
    allowed_empty_dirs = {".git", ".agents"}
    unexpected: list[str] = []
    for entry in manifest.get("entries", []):
        path = entry.get("path")
        if path not in allowed_empty_dirs or entry.get("type") != "directory" or entry.get("streams") not in ([], None):
            unexpected.append(str(path))
    if unexpected:
        raise RouteError(
            "workspace_not_disposable",
            f"{label} workspace contains unapproved baseline entries: {sorted(unexpected)}",
            2,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a bounded Cairnspan two-edge closure probe.")
    parser.add_argument("--codex-cwd", type=Path, required=True)
    parser.add_argument("--claude-cwd", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True, help="Fresh parent-controlled route receipt directory")
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--claude-bin", type=Path, required=True)
    parser.add_argument("--codex-timeout-seconds", type=int, default=90)
    parser.add_argument("--claude-timeout-seconds", type=int, default=90)
    parser.add_argument("--max-route-seconds", type=int, default=210)
    parser.add_argument("--max-edge-output-bytes", type=int, default=1_048_576)
    parser.add_argument("--max-route-output-bytes", type=int, default=2_097_152)
    parser.add_argument("--max-claude-budget-usd", default="0.05")
    parser.add_argument("--max-route-reported-cost-usd", default="0.05")
    parser.add_argument("--nonce-bytes", type=int, default=16)
    parser.add_argument("--route-order", choices=tuple(ROUTE_ORDERS), default="codex-first")
    parser.add_argument("--allow-test-shell-wrappers", action="store_true")
    parser.add_argument("--allow-unsafe", action="store_true")
    parser.add_argument("--unsafe-reason")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    route_id = make_route_id()
    route_started = time.monotonic()
    route_summary: dict[str, Any] | None = None
    out_dir: Path | None = None
    manifests: dict[str, dict[str, Any]] = {}
    exit_code = 0

    try:
        if args.execute and args.dry_run:
            raise RouteError("config", "Choose only one of --execute or --dry-run", 2)
        execute = bool(args.execute)
        codex_timeout = positive_int(args.codex_timeout_seconds, "Codex timeout")
        claude_timeout = positive_int(args.claude_timeout_seconds, "Claude timeout")
        max_route_seconds = positive_int(args.max_route_seconds, "Route timeout")
        max_edge_output = positive_int(args.max_edge_output_bytes, "Edge output limit")
        max_route_output = positive_int(args.max_route_output_bytes, "Route output limit")
        if args.nonce_bytes < 16 or args.nonce_bytes > 64:
            raise RouteError("config", "Nonce size must be between 16 and 64 bytes", 2)
        claude_budget = positive_decimal(args.max_claude_budget_usd, "Claude budget")
        route_budget = positive_decimal(args.max_route_reported_cost_usd, "Route reported-cost ceiling")
        if claude_budget > route_budget:
            raise RouteError("budget", "Claude edge budget exceeds the route reported-cost ceiling", 2)
        if args.allow_test_shell_wrappers and (not args.allow_unsafe or not args.unsafe_reason):
            raise RouteError(
                "config",
                "--allow-test-shell-wrappers requires --allow-unsafe and --unsafe-reason",
                2,
            )
        if (args.allow_unsafe or args.unsafe_reason) and not args.allow_test_shell_wrappers:
            raise RouteError("config", "Unsafe acknowledgement is only valid with test shell wrappers", 2)

        codex_workspace = resolve_workspace(args.codex_cwd, "Codex")
        claude_workspace = resolve_workspace(args.claude_cwd, "Claude")
        if codex_workspace == claude_workspace:
            raise RouteError("path_policy", "The first live route requires distinct target workspaces", 2)
        codex_bin = resolve_executable(args.codex_bin, "Codex", args.allow_test_shell_wrappers)
        claude_bin = resolve_executable(args.claude_bin, "Claude", args.allow_test_shell_wrappers)
        for executable, label in ((codex_bin, "Codex"), (claude_bin, "Claude")):
            if path_is_within(executable, codex_workspace) or path_is_within(executable, claude_workspace):
                raise RouteError("path_policy", f"{label} executable cannot be selected from a target workspace", 2)

        requested_out = args.out_dir.absolute()
        validate_existing_ancestors(requested_out)
        if os.path.lexists(requested_out):
            raise RouteError("stale_route", "Route output directory already exists; use a fresh path", 2)
        requested_out.parent.mkdir(parents=True, exist_ok=True)
        if path_is_reparse(requested_out.parent):
            raise RouteError("path_policy", "Route output parent cannot be a link or reparse point", 2)
        out_dir = requested_out.resolve()
        if any(
            path_is_within(out_dir, workspace) or path_is_within(workspace, out_dir)
            for workspace in (codex_workspace, claude_workspace)
        ):
            raise RouteError("path_policy", "Route receipts must be outside both target workspaces", 2)
        out_dir.mkdir()
        for name in ("prompts", "edges", "control", "manifests"):
            (out_dir / name).mkdir()

        route_agents = ROUTE_ORDERS[args.route_order]
        route_order = [AGENT_DISPLAY_NAMES[agent] for agent in route_agents]
        first_agent, second_agent = route_agents
        first_prefix = "cairnspan-codex" if first_agent == "codex" else "cairnspan-claude"
        first_expected = f"{first_prefix}:{secrets.token_hex(args.nonce_bytes)}"
        nonce = first_expected.rsplit(":", 1)[1]
        closure_expected = f"cairnspan-closed:{nonce}"
        first_prompt = f"Reply with exactly {first_expected} and no other text."
        planned_second_prompt = (
            f"Local string-transformation test. Input: {first_expected} Replace only the prefix "
            f"{first_prefix}: with cairnspan-closed:. Output exactly {closure_expected} and no other text."
        )
        first_prompt_path = out_dir / "prompts" / f"{first_agent}.txt"
        write_text_atomic(first_prompt_path, first_prompt)

        codex_before = snapshot(codex_workspace, strict=True)
        claude_before = snapshot(claude_workspace, strict=True)
        write_json_atomic(out_dir / "manifests" / "codex-before.json", codex_before)
        write_json_atomic(out_dir / "manifests" / "claude-before.json", claude_before)

        route_summary = {
            "schema_version": SCHEMA_VERSION,
            "route_id": route_id,
            "created_at": utc_now(),
            "completed_at": None,
            "status": "running" if execute else "dry_run_running",
            "state": "created",
            "dry_run": not execute,
            "error_kind": None,
            "error": None,
            "route_order": route_order,
            "edge_attempts": 0,
            "successful_edges": 0,
            "nonce_sha256": sha256_text(nonce),
            "policy": {
                "max_edges": 2,
                "max_depth": 1,
                "max_fan_out": 1,
                "retry_budget": 0,
                "codex_timeout_seconds": codex_timeout,
                "claude_timeout_seconds": claude_timeout,
                "max_route_seconds": max_route_seconds,
                "max_edge_output_bytes": max_edge_output,
                "max_route_output_bytes": max_route_output,
                "max_claude_budget_usd": format(claude_budget, "f"),
                "max_route_reported_cost_usd": format(route_budget, "f"),
                "native_executables_required": not args.allow_test_shell_wrappers,
                "disposable_workspace_allowlist": [".agents", ".git"],
                "unsafe_reason": args.unsafe_reason if args.allow_test_shell_wrappers else None,
            },
            "executables": {
                "codex": executable_identity(codex_bin),
                "claude": executable_identity(claude_bin),
            },
            "workspaces": {"codex": str(codex_workspace), "claude": str(claude_workspace)},
            "edges": [],
            "manifests": manifests,
            "aggregate": {
                "elapsed_seconds": 0.0,
                "output_bytes": 0,
                "reported_cost_usd": "0",
                "unreported_cost_edges": [],
            },
            "closure_file": None,
        }
        route_plan = {
            "schema_version": SCHEMA_VERSION,
            "route_id": route_id,
            "route_order": route_summary["route_order"],
            "nonce_sha256": route_summary["nonce_sha256"],
            "policy": route_summary["policy"],
            "executables": route_summary["executables"],
            "workspaces": route_summary["workspaces"],
            "first_agent": AGENT_DISPLAY_NAMES[first_agent],
            "second_agent": AGENT_DISPLAY_NAMES[second_agent],
            "first_prompt_sha256": sha256_text(first_prompt),
            "expected_first_final_sha256": sha256_text(first_expected),
            "expected_closure_final_sha256": sha256_text(closure_expected),
            "codex_prompt_sha256": sha256_text(
                first_prompt if first_agent == "codex" else planned_second_prompt
            ),
            "expected_codex_final_sha256": sha256_text(
                first_expected if first_agent == "codex" else closure_expected
            ),
            "expected_claude_final_sha256": sha256_text(
                first_expected if first_agent == "claude" else closure_expected
            ),
        }
        route_plan_path = out_dir / "route-plan.json"
        write_json_atomic(route_plan_path, route_plan)
        route_summary["route_plan_sha256"] = sha256_file(route_plan_path)
        write_json_atomic(out_dir / "route-summary.json", route_summary)
        validate_disposable_workspace(codex_before, "Codex")
        validate_disposable_workspace(claude_before, "Claude")

        edge_payloads: dict[str, dict[str, Any]] = {}
        aggregate_output = 0
        aggregate_cost = Decimal("0")

        def remaining_route_seconds() -> float:
            return max_route_seconds - (time.monotonic() - route_started)

        def run_edge(agent: str, prompt_path: Path, budget: Decimal) -> tuple[dict[str, Any], dict[str, Any]]:
            nonlocal aggregate_output, aggregate_cost
            remaining = remaining_route_seconds()
            if remaining <= 0:
                raise RouteError("route_timeout", "Route deadline expired before the next edge", 124)
            configured_timeout = codex_timeout if agent == "codex" else claude_timeout
            edge_timeout = max(1, min(configured_timeout, int(remaining)))
            remaining_output = max_route_output - aggregate_output
            if remaining_output <= 0:
                raise RouteError("route_output_limit", "No aggregate output budget remains", 125)
            edge_output_limit = min(max_edge_output, remaining_output)
            edge_dir = out_dir / "edges" / agent
            command = edge_command(
                agent=agent,
                workspace=codex_workspace if agent == "codex" else claude_workspace,
                edge_dir=edge_dir,
                prompt_file=prompt_path,
                executable=codex_bin if agent == "codex" else claude_bin,
                expected_cli_version=route_summary["executables"][agent]["version"],
                route_id=route_id,
                timeout_seconds=edge_timeout,
                max_output_bytes=edge_output_limit,
                claude_budget=budget,
                execute=execute,
                allow_shell_wrapper=args.allow_test_shell_wrappers,
            )
            route_summary["edge_attempts"] += 1
            route_summary["state"] = f"{agent}_running"
            write_json_atomic(out_dir / "route-summary.json", route_summary)
            result = run_launcher(command, max(0.1, remaining_route_seconds()))
            write_bytes_atomic(out_dir / "control" / f"{agent}-launcher.stdout.log", result.stdout)
            write_bytes_atomic(out_dir / "control" / f"{agent}-launcher.stderr.log", result.stderr)
            summary_path = edge_dir / "cairnspan-summary.json"
            payload = safe_read_json(summary_path)
            if result.return_code != 0:
                child_error = payload.get("error_kind")
                if child_error in {
                    "timeout", "output_limit", "policy", "process_leak",
                    "rate_limit", "quota", "crash",
                }:
                    mapped = {
                        "timeout": ("route_timeout", 124),
                        "output_limit": ("route_output_limit", 125),
                        "policy": ("policy", 1),
                        "process_leak": ("process_leak", 125),
                        "rate_limit": ("rate_limit", 1),
                        "quota": ("quota", 1),
                        "crash": ("crash", 1),
                    }[str(child_error)]
                    raise RouteError(mapped[0], f"{agent} edge failed its {child_error} policy", mapped[1])
                raise RouteError(
                    "target_failure",
                    f"{agent} launcher failed with code {result.return_code} ({child_error})",
                )
            if execute:
                validate_receipt_paths(edge_dir)
            validate_edge_summary(
                payload,
                agent=agent,
                route_id=route_id,
                workspace=codex_workspace if agent == "codex" else claude_workspace,
                edge_dir=edge_dir,
                prompt_sha256=sha256_file(prompt_path),
                expected_cli_version=route_summary["executables"][agent]["version"],
                execute=execute,
            )
            if execute:
                record = make_edge_record(agent, result, payload, edge_dir)
            else:
                record = {
                    "agent": agent,
                    "launcher_return_code": result.return_code,
                    "launcher_elapsed_seconds": result.elapsed_seconds,
                    "target_run_id": payload.get("run_id"),
                    "target_identity": None,
                    "status": payload.get("status"),
                    "prompt_sha256": payload.get("prompt_sha256"),
                    "final_sha256": None,
                    "summary_sha256": sha256_file(summary_path),
                    "output_bytes": 0,
                    "reported_cost_usd": None,
                    "receipt_dir": str(edge_dir),
                }
            aggregate_output += int(record["output_bytes"])
            if aggregate_output > max_route_output:
                raise RouteError("route_output_limit", "Aggregate edge output exceeded route policy", 125)
            cost = decimal_from_summary(payload.get("total_cost_usd"))
            if cost is None:
                route_summary["aggregate"]["unreported_cost_edges"].append(agent)
            else:
                aggregate_cost += cost
            if aggregate_cost > route_budget:
                raise RouteError("route_budget", "Reported aggregate target cost exceeded route policy")
            route_summary["successful_edges"] += 1
            route_summary["edges"].append(record)
            route_summary["aggregate"]["output_bytes"] = aggregate_output
            route_summary["aggregate"]["reported_cost_usd"] = format(aggregate_cost, "f")
            edge_payloads[agent] = payload
            write_json_atomic(out_dir / "route-summary.json", route_summary)
            return payload, record

        def budget_for(agent: str) -> Decimal:
            if agent != "claude":
                return claude_budget
            remaining_cost = route_budget - aggregate_cost
            if remaining_cost <= 0:
                raise RouteError("route_budget", "No reported-cost budget remains for the Claude edge")
            return min(claude_budget, remaining_cost)

        def capture_manifest(agent: str) -> None:
            workspace = codex_workspace if agent == "codex" else claude_workspace
            before = codex_before if agent == "codex" else claude_before
            after = snapshot(workspace, strict=True)
            write_json_atomic(out_dir / "manifests" / f"{agent}-after.json", after)
            manifests[agent] = manifest_record(workspace, before, after)
            route_summary["manifests"] = manifests
            if manifests[agent]["status"] != "identical":
                label = "read-only" if agent == "codex" else "no-tools"
                raise RouteError("workspace_modified", f"{AGENT_DISPLAY_NAMES[agent]} workspace changed during the {label} edge")

        first_payload, first_record = run_edge(first_agent, first_prompt_path, budget_for(first_agent))
        capture_manifest(first_agent)

        if execute:
            first_final = safe_read_text(out_dir / "edges" / first_agent / "final.md", max_edge_output)
            if first_final != first_expected:
                raise RouteError("nonce_mismatch", "First-edge final artifact did not match the nonce challenge")
        else:
            first_final = first_expected
        route_summary["state"] = f"{first_agent}_verified"

        second_prompt = planned_second_prompt
        second_prompt_path = out_dir / "prompts" / f"{second_agent}.txt"
        write_text_atomic(second_prompt_path, second_prompt)
        route_summary["verified_first_artifact_sha256"] = sha256_text(first_final)
        route_summary["second_prompt_sha256"] = sha256_text(second_prompt)
        write_json_atomic(out_dir / "route-summary.json", route_summary)

        second_payload, second_record = run_edge(second_agent, second_prompt_path, budget_for(second_agent))
        capture_manifest(second_agent)

        if not execute:
            route_summary["status"] = "dry_run"
            route_summary["state"] = "dry_run"
            route_summary["completed_at"] = utc_now()
            route_summary["aggregate"]["elapsed_seconds"] = round(time.monotonic() - route_started, 3)
            write_json_atomic(out_dir / "route-summary.json", route_summary)
            print(json.dumps(route_summary, indent=2, sort_keys=True))
            return 0

        closure_final = safe_read_text(out_dir / "edges" / second_agent / "final.md", max_edge_output)
        if closure_final != closure_expected:
            raise RouteError("nonce_mismatch", "Second-edge final artifact did not close the nonce challenge")
        route_summary["state"] = f"{second_agent}_verified"
        elapsed = round(time.monotonic() - route_started, 3)
        if elapsed > max_route_seconds:
            raise RouteError("route_timeout", "Route exceeded its aggregate elapsed-time policy", 124)
        if executable_identity(codex_bin) != route_summary["executables"]["codex"]:
            raise RouteError("executable_changed", "Codex executable identity changed during the route")
        if executable_identity(claude_bin) != route_summary["executables"]["claude"]:
            raise RouteError("executable_changed", "Claude executable identity changed during the route")
        if route_summary["successful_edges"] != 2 or route_summary["edge_attempts"] != 2:
            raise RouteError("route_shape", "Route did not complete exactly two ordered edges")

        closure = {
            "schema_version": SCHEMA_VERSION,
            "route_id": route_id,
            "closed_at": utc_now(),
            "status": "closed",
            "route_order": route_order,
            "route_plan_sha256": route_summary["route_plan_sha256"],
            "nonce_sha256": sha256_text(nonce),
            "policy": route_summary["policy"],
            "executables": route_summary["executables"],
            "edges": [
                {
                    "agent": record["agent"],
                    "target_run_id": record["target_run_id"],
                    "target_identity": record["target_identity"],
                    "prompt_sha256": record["prompt_sha256"],
                    "final_sha256": record["final_sha256"],
                    "summary_sha256": record["summary_sha256"],
                }
                for record in (first_record, second_record)
            ],
            "verified_first_artifact_sha256": sha256_text(first_final),
            "second_prompt_sha256": sha256_text(second_prompt),
            "final_closure_sha256": sha256_text(closure_final),
            "manifests": manifests,
            "aggregate": {
                "elapsed_seconds": elapsed,
                "output_bytes": aggregate_output,
                "reported_cost_usd": format(aggregate_cost, "f"),
                "unreported_cost_edges": route_summary["aggregate"]["unreported_cost_edges"],
            },
        }
        closure_path = out_dir / "closure.json"
        write_json_atomic(closure_path, closure)
        route_summary["status"] = "succeeded"
        route_summary["state"] = "closed"
        route_summary["completed_at"] = utc_now()
        route_summary["aggregate"] = closure["aggregate"]
        route_summary["closure_file"] = str(closure_path)
        write_json_atomic(out_dir / "route-summary.json", route_summary)
        print(json.dumps(route_summary, indent=2, sort_keys=True))
        return 0

    except RouteError as exc:
        exit_code = exc.return_code
        if route_summary is not None and out_dir is not None:
            failed_from_state = route_summary.get("state")
            route_summary["status"] = "failed"
            route_summary["state"] = "failed"
            route_summary["failed_from_state"] = failed_from_state
            route_summary["error_kind"] = exc.kind
            route_summary["error"] = exc.message
            route_summary["completed_at"] = utc_now()
            route_summary["aggregate"]["elapsed_seconds"] = round(time.monotonic() - route_started, 3)
            try:
                if "codex" not in manifests:
                    codex_after = snapshot(Path(route_summary["workspaces"]["codex"]), strict=True)
                    write_json_atomic(out_dir / "manifests" / "codex-after.json", codex_after)
                    manifests["codex"] = manifest_record(
                        Path(route_summary["workspaces"]["codex"]), codex_before, codex_after
                    )
                if "claude" not in manifests:
                    claude_after = snapshot(Path(route_summary["workspaces"]["claude"]), strict=True)
                    write_json_atomic(out_dir / "manifests" / "claude-after.json", claude_after)
                    manifests["claude"] = manifest_record(
                        Path(route_summary["workspaces"]["claude"]), claude_before, claude_after
                    )
                route_summary["manifests"] = manifests
            except (OSError, ValueError):
                route_summary.setdefault("policy_observations", []).append(
                    "one or more failure-path after-manifests could not be captured"
                )
            write_json_atomic(out_dir / "route-summary.json", route_summary)
            print(json.dumps(route_summary, indent=2, sort_keys=True), file=sys.stderr)
        else:
            print(json.dumps({"status": "config_error", "error_kind": exc.kind, "error": exc.message}), file=sys.stderr)
        return exit_code
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        if route_summary is not None and out_dir is not None:
            route_summary["status"] = "failed"
            route_summary["error_kind"] = "internal"
            route_summary["error"] = str(exc)
            route_summary["completed_at"] = utc_now()
            write_json_atomic(out_dir / "route-summary.json", route_summary)
        print(f"cairnspan-route-error: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
