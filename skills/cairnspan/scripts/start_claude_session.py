"""Launch a scoped Claude Code session for cross-agent delegation.

This helper is intentionally stdlib-only so Codex or another local agent can
run it from a fresh checkout without installing dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli_version import VersionProbeError, probe_cli_version, version_probe_env
from hostile_write_profile import (
    AFTER_MANIFEST_NAME,
    BEFORE_MANIFEST_NAME,
    PROFILE_NAME as HOSTILE_WRITE_PROFILE,
    HostileWriteProfileError,
    PreparedProfile,
    canonical_prompt as hostile_write_prompt,
    prepare as prepare_hostile_write,
    sentinel_matches,
    validate_after as validate_hostile_write_after,
    validate_receipt_root as validate_hostile_write_receipts,
)
from workspace_manifest import compare as compare_manifests
from workspace_manifest import snapshot as snapshot_workspace
from workspace_manifest import write_json_atomic as write_manifest_atomic


SCHEMA_VERSION = "0.12"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
REDACTED_PROMPT = "<prompt redacted>"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
AGENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
SENSITIVE_AUTH_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "AWS_BEARER_TOKEN_BEDROCK",
    "AZURE_OPENAI_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDE_CODE_USE_VERTEX",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)
RECEIPT_NAMES = ("events.jsonl", "transcript.log", "final.md", "cairnspan-summary.json")
SENSITIVE_WORKSPACE_DIRS = {".git", ".hg", ".svn", ".claude", ".codex", ".agents"}
MAX_WINDOWS_COMMAND_UNITS = 30_000
DESCENDANT_EXIT_GRACE_SECONDS = 5.0
DESCENDANT_START_SETTLE_SECONDS = 0.25
SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(access[_-]?token\s*[=:]\s*)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(refresh[_-]?token\s*[=:]\s*)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(authorization:\s*)[^\r\n]+"),
)
UNSAFE_PERMISSION_MODES = {"bypassPermissions"}
UNSAFE_TOOL_VALUES = {"default", "*", "all"}
UNSAFE_CLAUDE_ARGS = {
    "--dangerously-skip-permissions",
    "--allow-dangerously-skip-permissions",
    "--bare",
}
RESERVED_CLAUDE_RAW_FLAGS = UNSAFE_CLAUDE_ARGS | {
    "--chrome", "--continue", "--disable-slash-commands", "--max-budget-usd", "--mcp-config",
    "--effort", "--model", "--no-chrome", "--no-session-persistence", "--output-format", "--permission-mode",
    "--resume", "--safe-mode", "--session-id", "--setting-sources", "--settings",
    "--strict-mcp-config", "--tools", "--verbose",
}


@dataclass
class ParsedEvents:
    session_id: str | None = None
    usage: dict[str, Any] | None = None
    model_usage: dict[str, Any] | None = None
    total_cost_usd: float | int | None = None
    final_message: str = ""
    is_error: bool = False
    api_error_status: str | int | None = None
    valid_event_count: int = 0
    completion_observed: bool = False
    terminal_event_count: int = 0
    observed_session_ids: list[str] = field(default_factory=list)
    init_capabilities: dict[str, list[str]] | None = None
    tool_names: list[str] = field(default_factory=list)
    tool_use_count: int = 0
    mcp_tool_use_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class CairnspanSummary:
    schema_version: str
    run_id: str
    parent_run_id: str | None
    run_depth: int
    max_depth: int
    created_at: str
    origin_agent: str
    target_agent: str
    target_workspace: str
    cwd: str
    command: list[str]
    launcher_command_sha256: str | None
    claude_bin_resolved: str | None
    target_cli_version: str | None
    expected_cli_version: str | None
    dry_run: bool
    status: str
    permission_mode: str
    tools: str
    output_format: str
    strict_mcp_config: bool
    safe_mode: bool
    max_budget_usd: str | None
    requested_model: str | None
    requested_effort: str | None
    prompt_file: str | None
    prompt_sha256: str
    out_dir: str
    events_log: str
    transcript_log: str
    final_message: str
    summary_file: str
    timeout_seconds: int
    max_output_bytes: int
    max_prompt_bytes: int
    prompt_bytes: int
    scrubbed_env: list[str]
    return_code: int | None = None
    session_id: str | None = None
    usage: dict[str, Any] | None = None
    model_usage: dict[str, Any] | None = None
    total_cost_usd: float | int | None = None
    error: str | None = None
    error_kind: str | None = None
    transcript_excerpt: str | None = None
    parse_warnings: list[str] = field(default_factory=list)
    terminal_event_count: int = 0
    observed_session_ids: list[str] = field(default_factory=list)
    init_capabilities: dict[str, list[str]] | None = None
    tool_names: list[str] = field(default_factory=list)
    tool_use_count: int = 0
    mcp_tool_use_count: int = 0
    execution_profile: str = "default"
    declared_write_path: str | None = None
    allowed_tool_names: list[str] = field(default_factory=list)
    write_profile_status: str = "not_checked"
    write_profile_nonce_sha256: str | None = None
    write_profile_before_manifest: str | None = None
    write_profile_after_manifest: str | None = None
    write_profile_changed_paths: list[str] = field(default_factory=list)
    protected_sentinel_sha256: str | None = None
    protected_sentinel_unchanged: bool | None = None
    write_profile_receipt_root_status: str = "not_checked"
    policy_observations: list[str] = field(default_factory=list)
    process_leak_details: list[dict[str, Any]] = field(default_factory=list)
    descendant_cleanup_verified: bool = False
    containment: str = "not-run"
    elapsed_seconds: float | None = None
    unsafe_reason: str | None = None


class OutputLimitExceeded(Exception):
    """Raised when the target process writes more output than policy allows."""


class OutputDecodeError(Exception):
    """Raised when the target process emits non-UTF-8 machine output."""


class DescendantProcessSurvived(Exception):
    """Raised when a target exits but leaves a descendant process running."""

    def __init__(self, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__("target descendant survived process exit")
        self.details = details or []


class ContainmentUnavailable(Exception):
    """Raised when strong Windows process containment cannot be attached."""


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_run_id() -> str:
    return f"{utc_stamp()}-{uuid.uuid4().hex[:8]}"


def default_out_dir(cwd: Path, run_id: str) -> Path:
    return cwd / ".cairnspan" / run_id


def safe_default_out_dir(cwd: Path, run_id: str) -> Path:
    preferred = default_out_dir(cwd, run_id)
    if path_is_within(preferred, cwd):
        return preferred.resolve()
    return (cwd / f".cairnspan-{run_id}").resolve()


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def directory_has_contents(path: Path) -> bool:
    if not path.exists():
        return False
    if not path.is_dir():
        return True
    return any(path.iterdir())


def run_can_write(args: argparse.Namespace) -> bool:
    if args.permission_mode == "acceptEdits":
        return True
    read_only_tools = {"read", "glob", "grep", "websearch", "webfetch"}
    tokens = {token.casefold() for token in re.split(r"[\s,]+", args.tools.strip()) if token}
    return bool(tokens - read_only_tools)


def is_sensitive_workspace_out_dir(out_dir: Path, cwd: Path) -> bool:
    if not path_is_within(out_dir, cwd):
        return False
    relative = out_dir.relative_to(cwd)
    return not relative.parts or any(part.casefold() in SENSITIVE_WORKSPACE_DIRS for part in relative.parts)


def validate_out_dir(out_dir: Path, cwd: Path, args: argparse.Namespace) -> None:
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"Output path exists and is not a directory: {out_dir}")
    if not path_is_within(out_dir, cwd) and not args.allow_outside_workspace_out_dir:
        raise ValueError(
            "--out-dir must resolve inside --cwd unless --allow-outside-workspace-out-dir is set."
        )
    if is_sensitive_workspace_out_dir(out_dir, cwd):
        raise ValueError("--out-dir cannot be the workspace root or inside a workspace control directory.")
    if run_can_write(args) and path_is_within(out_dir, cwd):
        raise ValueError("Write-capable Claude runs require --out-dir outside --cwd with --allow-outside-workspace-out-dir.")
    if directory_has_contents(out_dir) and not args.overwrite_out_dir:
        raise ValueError("--out-dir exists and is not empty; choose a new directory or pass --overwrite-out-dir.")


def resolve_out_dir(args: argparse.Namespace, cwd: Path, run_id: str) -> Path:
    out_dir = (args.out_dir or default_out_dir(cwd, run_id)).resolve()
    validate_out_dir(out_dir, cwd, args)
    return out_dir


def config_error_out_dir(args: argparse.Namespace, run_id: str) -> Path:
    fallback_base = args.cwd.resolve() if args.cwd.exists() and args.cwd.is_dir() else Path.cwd().resolve()
    requested = args.out_dir.resolve() if args.out_dir else None
    if requested and requested.exists() and not requested.is_dir():
        return safe_default_out_dir(fallback_base, run_id)
    if requested and not is_sensitive_workspace_out_dir(requested, fallback_base) and (
        args.allow_outside_workspace_out_dir or path_is_within(requested, fallback_base)
    ):
        if not directory_has_contents(requested) or args.overwrite_out_dir:
            return requested
    return safe_default_out_dir(fallback_base, run_id)


def redact_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(r"\1<redacted>", redacted)
    return redacted


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_utf8_preserving_newlines(path: Path) -> str:
    """Decode strict UTF-8 without universal-newline byte drift."""
    with path.open("r", encoding="utf-8", errors="strict", newline="") as handle:
        return handle.read()


def read_prompt(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.hostile_write_nonce:
        return hostile_write_prompt("claude-code", args.hostile_write_nonce), None
    if args.prompt_file:
        prompt_path = args.prompt_file.resolve()
        if not prompt_path.is_file():
            raise ValueError(f"Prompt file does not exist: {prompt_path}")
        return read_utf8_preserving_newlines(prompt_path), str(prompt_path)
    return args.prompt, None


def has_path_separator(value: str) -> bool:
    return any(separator in value for separator in (os.sep, os.altsep) if separator)


def resolve_claude_bin(claude_bin: str, cwd: Path, allow_shell_wrapper: bool) -> Path:
    candidate = Path(claude_bin)
    if candidate.is_absolute():
        if not candidate.is_file():
            raise FileNotFoundError(f"Claude executable is not a file: {candidate}")
        resolved_path = candidate.resolve()
        if resolved_path.suffix.lower() in {".cmd", ".bat", ".ps1"} and not allow_shell_wrapper:
            raise ValueError("Shell-wrapper Claude executables require --allow-shell-wrapper.")
        return resolved_path

    if has_path_separator(claude_bin):
        raise ValueError(
            "--claude-bin must be an absolute path or a command name on PATH; "
            "relative executable paths are not allowed."
        )

    resolved = shutil.which(claude_bin)
    if not resolved:
        raise FileNotFoundError(f"Claude executable not found on PATH: {claude_bin}")
    resolved_path = Path(resolved).resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Claude executable is not a file: {resolved_path}")
    if path_is_within(resolved_path, cwd):
        raise ValueError(
            "Claude command-name resolution selected an executable inside --cwd; "
            "pass an explicit trusted absolute --claude-bin path instead."
        )
    if resolved_path.suffix.lower() in {".cmd", ".bat", ".ps1"} and not allow_shell_wrapper:
        raise ValueError("Shell-wrapper Claude executables require --allow-shell-wrapper.")
    return resolved_path


def redact_command(command: list[str], prompt: str, opaque_values: list[str] | None = None) -> list[str]:
    opaque = set(opaque_values or [])
    redacted: list[str] = []
    for value in command:
        if value == prompt:
            redacted.append(REDACTED_PROMPT)
        elif value in opaque:
            redacted.append("<sensitive-arg redacted>")
        else:
            redacted.append(redact_text(value))
    return redacted


def build_command(args: argparse.Namespace, claude_bin: Path, prompt: str) -> list[str]:
    command = [
        str(claude_bin),
        "-p",
        "--output-format",
        args.output_format,
        "--permission-mode",
        args.permission_mode,
        "--tools",
        args.tools,
    ]
    if args.output_format == "stream-json":
        command.append("--verbose")
    if args.no_session_persistence:
        command.append("--no-session-persistence")
    if args.max_budget_usd:
        command.extend(["--max-budget-usd", args.max_budget_usd])
    if args.safe_mode:
        command.extend(
            [
                "--safe-mode",
                "--disable-slash-commands",
                "--setting-sources",
                "",
                "--no-chrome",
            ]
        )
    if args.model:
        command.extend(["--model", args.model])
    if args.effort:
        command.extend(["--effort", args.effort])
    if args.mcp_config:
        for config in args.mcp_config:
            command.extend(["--mcp-config", config])
    if args.strict_mcp_config:
        command.append("--strict-mcp-config")
    for extra in args.claude_arg:
        command.append(extra)
    command.append(prompt)
    return command


def extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def event_session_id(event: dict[str, Any]) -> str | None:
    value = event.get("session_id")
    if isinstance(value, str) and value:
        return value
    message = event.get("message")
    if isinstance(message, dict):
        value = message.get("session_id")
        if isinstance(value, str) and value:
            return value
    return None


def event_usage(event: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(event.get("usage"), dict):
        return event["usage"]
    message = event.get("message")
    if isinstance(message, dict) and isinstance(message.get("usage"), dict):
        return message["usage"]
    return None


def event_message_text(event: dict[str, Any]) -> str:
    if isinstance(event.get("result"), str):
        return event["result"]
    if event.get("type") in {"assistant", "message", "assistant_message"}:
        if isinstance(event.get("text"), str):
            return event["text"]
        content_text = extract_text_from_content(event.get("content"))
        if content_text:
            return content_text
    message = event.get("message")
    if isinstance(message, dict) and message.get("role") in {None, "assistant"}:
        return extract_text_from_content(message.get("content"))
    delta = event.get("delta")
    if isinstance(delta, dict):
        text = delta.get("text")
        if isinstance(text, str):
            return text
    return ""


def capability_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        name: str | None = None
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            name = item["name"]
        if name and name not in names:
            names.append(name)
    return names


def event_tool_names(event: dict[str, Any]) -> list[str]:
    names: list[str] = []

    def add_tool_name(item: Any) -> None:
        if not isinstance(item, dict) or item.get("type") not in {"tool_use", "tool_call", "mcp_tool_call"}:
            return
        for key in ("name", "tool_name"):
            value = item.get(key)
            if isinstance(value, str) and value and value not in names:
                names.append(value)
                return

    add_tool_name(event)
    for container in (event, event.get("message")):
        if not isinstance(container, dict):
            continue
        content = container.get("content")
        if isinstance(content, list):
            for item in content:
                add_tool_name(item)
    return names


def parse_events(events_path: Path) -> ParsedEvents:
    parsed = ParsedEvents()
    if not events_path.exists():
        parsed.warnings.append("events log does not exist")
        return parsed

    collected_chunks: list[str] = []
    terminal_index: int | None = None
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            parsed.warnings.append(f"line {line_number}: invalid JSON ignored")
            continue
        if not isinstance(event, dict):
            parsed.warnings.append(f"line {line_number}: non-object JSON event ignored")
            continue

        parsed.valid_event_count += 1
        if event.get("type") == "result":
            parsed.completion_observed = True
            parsed.terminal_event_count += 1
            terminal_index = parsed.valid_event_count
        if event.get("type") == "system" and event.get("subtype") == "init":
            parsed.init_capabilities = {
                key: capability_names(event.get(key))
                for key in ("tools", "mcp_servers", "plugins", "skills", "agents", "slash_commands")
            }

        tool_names = event_tool_names(event)
        if tool_names:
            parsed.tool_use_count += len(tool_names)
            for name in tool_names:
                if name not in parsed.tool_names:
                    parsed.tool_names.append(name)
                if name.lower().startswith(("mcp__", "mcp_")):
                    parsed.mcp_tool_use_count += 1

        session_id = event_session_id(event)
        if session_id:
            if session_id not in parsed.observed_session_ids:
                parsed.observed_session_ids.append(session_id)
            parsed.session_id = session_id

        usage = event_usage(event)
        if usage:
            parsed.usage = usage

        model_usage = event.get("modelUsage")
        if isinstance(model_usage, dict):
            parsed.model_usage = model_usage

        total_cost = event.get("total_cost_usd")
        if isinstance(total_cost, (float, int)) and not isinstance(total_cost, bool):
            try:
                cost = Decimal(str(total_cost))
            except InvalidOperation:
                parsed.warnings.append("result event contained an invalid total cost")
            else:
                if not cost.is_finite() or cost < 0:
                    parsed.warnings.append("result event contained a non-finite or negative total cost")
                else:
                    parsed.total_cost_usd = total_cost

        if event.get("is_error") is True:
            parsed.is_error = True
        if event.get("api_error_status") is not None:
            parsed.api_error_status = event.get("api_error_status")
            parsed.is_error = True
        if event.get("type") == "result" and event.get("subtype") not in {None, "success"}:
            parsed.is_error = True

        message_text = event_message_text(event)
        if message_text:
            if event.get("type") == "result" and isinstance(event.get("result"), str):
                parsed.final_message = message_text
            else:
                collected_chunks.append(message_text)

    if not parsed.final_message and collected_chunks:
        parsed.final_message = "".join(collected_chunks)
    if parsed.terminal_event_count != 1:
        parsed.warnings.append(f"expected exactly one terminal event; observed {parsed.terminal_event_count}")
    if terminal_index is not None and terminal_index != parsed.valid_event_count:
        parsed.warnings.append("one or more events appeared after the terminal event")
    if len(parsed.observed_session_ids) > 1:
        parsed.warnings.append("conflicting session ids were observed")
    return parsed


def write_text_atomic(path: Path, text: str) -> None:
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("x", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_json(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def transcript_excerpt(path: Path, limit: int = 1200) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return redact_text(text[-limit:]).strip()


def classify_failure(return_code: int | None, transcript: str, parsed: ParsedEvents | None = None) -> tuple[str | None, str | None]:
    if parsed and parsed.is_error:
        if parsed.api_error_status:
            lowered_status = str(parsed.api_error_status).lower()
            if any(marker in lowered_status for marker in ("rate limit", "rate_limit", "too many requests", "429")):
                return "rate_limit", "Claude Code reported a provider rate limit."
            if any(marker in lowered_status for marker in ("quota", "usage limit", "insufficient credits", "credit balance")):
                return "quota", "Claude Code reported exhausted provider quota or credits."
            return "api", f"Claude Code reported an API error: {parsed.api_error_status}."
        return "api", "Claude Code reported an API error."
    if return_code in (None, 0):
        return None, None
    lowered = transcript.lower()
    if return_code == 124:
        return "timeout", "Claude Code run timed out."
    if return_code == 125 or "output limit" in lowered:
        return "output_limit", "Claude Code run exceeded the Cairnspan output byte limit."
    if return_code == 65:
        return "protocol", "Claude Code emitted non-UTF-8 machine output."
    if return_code == 127 or "not found" in lowered:
        return "missing_executable", "Claude executable was not found."
    if "connectionrefused" in lowered or "unable to connect to api" in lowered or "socket" in lowered:
        return "network", "Claude Code could not reach the Anthropic API due to a local network or socket restriction."
    if any(marker in lowered for marker in ("rate limit", "rate_limit", "too many requests", "http 429", "status 429")):
        return "rate_limit", "Claude Code reported a provider rate limit."
    if any(marker in lowered for marker in ("quota", "usage limit", "insufficient credits", "credit balance")):
        return "quota", "Claude Code reported exhausted provider quota or credits."
    if return_code == 126 or "access is denied" in lowered or "permission" in lowered:
        return "permission", "Claude executable could not be started due to OS permissions or permission policy."
    if "auth" in lowered or "login" in lowered or "credential" in lowered:
        return "auth", "Claude Code reported an authentication or credential failure."
    if "tool" in lowered and ("permission" in lowered or "not allowed" in lowered or "denied" in lowered):
        return "tool_permission", "Claude Code reported a tool permission failure."
    if "model" in lowered:
        return "model", "Claude Code reported a model configuration failure."
    if return_code < 0 or return_code >= 0xC0000000 or any(
        marker in lowered
        for marker in ("segmentation fault", "access violation", "core dumped", "panicked at", "fatal runtime error")
    ):
        return "crash", "Claude Code terminated because the target process crashed."
    return "unknown", f"Claude Code exited with return code {return_code}."


def terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    if os.name != "nt":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            if proc.poll() is None:
                proc.kill()
        return
    if proc.poll() is not None:
        return
    if os.name == "nt":
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        taskkill = system_root / "System32" / "taskkill.exe"
        subprocess.run(
            [str(taskkill), "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return


def create_windows_kill_job(proc: subprocess.Popen[str]) -> Any | None:
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = 0x00002000
    configured = kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    assigned = configured and kernel32.AssignProcessToJobObject(job, wintypes.HANDLE(proc._handle))
    if not assigned:
        kernel32.CloseHandle(job)
        return None
    return job


def close_windows_job(job: Any | None) -> None:
    if job is None or os.name != "nt":
        return
    import ctypes

    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle(job)


def resume_windows_process(proc: subprocess.Popen[str]) -> None:
    import ctypes
    from ctypes import wintypes

    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = wintypes.LONG
    status = int(ntdll.NtResumeProcess(wintypes.HANDLE(proc._handle)))
    if status != 0:
        raise OSError(f"NtResumeProcess failed with status 0x{status & 0xFFFFFFFF:08x}")


def windows_descendant_pids(root_pid: int) -> list[int]:
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return []
    children: dict[int, list[int]] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                children.setdefault(int(entry.th32ParentProcessID), []).append(int(entry.th32ProcessID))
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)

    descendants: list[int] = []
    pending = list(children.get(root_pid, []))
    while pending:
        pid = pending.pop()
        if pid in descendants:
            continue
        descendants.append(pid)
        pending.extend(children.get(pid, []))
    return descendants


def terminate_windows_pid(pid: int) -> None:
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x0001, False, pid)
    if not handle:
        return
    try:
        kernel32.TerminateProcess(handle, 125)
    finally:
        kernel32.CloseHandle(handle)


def windows_pid_alive(pid: int) -> bool:
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel32.CloseHandle(handle)


def windows_job_active_processes(job: Any | None) -> int:
    if os.name != "nt" or job is None:
        return 0
    import ctypes
    from ctypes import wintypes

    class BASIC_ACCOUNTING(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    info = BASIC_ACCOUNTING()
    returned = wintypes.DWORD()
    if not kernel32.QueryInformationJobObject(job, 1, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(returned)):
        return 0
    return int(info.ActiveProcesses)


def windows_job_process_ids(job: Any | None) -> list[int]:
    if os.name != "nt" or job is None:
        return []
    import ctypes
    from ctypes import wintypes

    class PID_LIST(ctypes.Structure):
        _fields_ = [
            ("NumberOfAssignedProcesses", wintypes.DWORD),
            ("NumberOfProcessIdsInList", wintypes.DWORD),
            ("ProcessIdList", ctypes.c_size_t * 256),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    info = PID_LIST()
    returned = wintypes.DWORD()
    if not kernel32.QueryInformationJobObject(job, 3, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(returned)):
        return []
    count = min(int(info.NumberOfProcessIdsInList), len(info.ProcessIdList))
    return [int(info.ProcessIdList[index]) for index in range(count)]


def windows_tracked_processes_active(job: Any | None, known_descendants: set[int]) -> bool:
    if os.name != "nt":
        return False
    if job is not None:
        return windows_job_active_processes(job) > 0
    return any(windows_pid_alive(pid) for pid in known_descendants)


def windows_tracked_process_ids(job: Any | None, known_descendants: set[int]) -> set[int]:
    if os.name != "nt":
        return set()
    if job is not None:
        return set(windows_job_process_ids(job))
    return {pid for pid in known_descendants if windows_pid_alive(pid)}


def windows_process_image(pid: int) -> str | None:
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def windows_process_details(pids: set[int]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for pid in sorted(pids):
        if not windows_pid_alive(pid):
            continue
        image = windows_process_image(pid)
        details.append({"pid": pid, "image": image, "name": Path(image).name if image else None})
    return details


def stop_process(proc: subprocess.Popen[str], job: Any | None = None) -> None:
    descendants = windows_descendant_pids(proc.pid)
    job_pids = windows_job_process_ids(job)
    if job is not None and os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject(job, 125)
        deadline = time.monotonic() + 5.0
        while windows_job_active_processes(job) > 0 and time.monotonic() < deadline:
            time.sleep(0.05)
    close_windows_job(job)
    if os.name == "nt":
        for pid in reversed(list(dict.fromkeys(job_pids + descendants))):
            terminate_windows_pid(pid)
        for pid in reversed(windows_descendant_pids(proc.pid)):
            terminate_windows_pid(pid)
    if proc.poll() is None and os.name == "nt":
        proc.kill()
    elif proc.poll() is None:
        terminate_process_tree(proc)
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def copy_limited_stream(
    source: Any,
    destination: Any,
    max_output_bytes: int,
    counter: dict[str, int],
    lock: threading.Lock,
    limit_event: threading.Event,
    decode_error_event: threading.Event,
) -> None:
    while True:
        try:
            chunk = source.readline(64 * 1024)
        except UnicodeDecodeError:
            decode_error_event.set()
            return
        if chunk == "":
            return
        chunk_bytes = len(chunk.encode("utf-8", errors="replace"))
        with lock:
            next_total = counter["bytes"] + chunk_bytes
            if max_output_bytes > 0 and next_total > max_output_bytes:
                counter["bytes"] = next_total
                limit_event.set()
                return
            counter["bytes"] = next_total
        destination.write(chunk)
        destination.flush()


def capture_identity(handle: Any) -> tuple[int, int]:
    stat_result = os.fstat(handle.fileno())
    return stat_result.st_dev, stat_result.st_ino


def capture_path_matches(path: Path, expected: tuple[int, int]) -> bool:
    try:
        if path.is_symlink():
            return False
        stat_result = path.stat()
    except OSError:
        return False
    return (stat_result.st_dev, stat_result.st_ino) == expected and stat_result.st_nlink == 1


def run_process(
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
    max_output_bytes: int,
    stdout: Any,
    stderr: Any,
    env: dict[str, str],
) -> tuple[int, str]:
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(
            subprocess, "CREATE_SUSPENDED", 0x00000004
        )
    else:
        popen_kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        bufsize=1,
        env=env,
        **popen_kwargs,
    )
    job = create_windows_kill_job(proc)
    if os.name == "nt":
        if job is None:
            stop_process(proc, None)
            raise ContainmentUnavailable("Windows Job Object attachment failed")
        try:
            resume_windows_process(proc)
        except OSError:
            stop_process(proc, job)
            job = None
            raise
        containment = "job-object"
    else:
        containment = "process-group"
    counter = {"bytes": 0}
    lock = threading.Lock()
    limit_event = threading.Event()
    decode_error_event = threading.Event()
    threads = [
        threading.Thread(
            target=copy_limited_stream,
            args=(proc.stdout, stdout, max_output_bytes, counter, lock, limit_event, decode_error_event),
            daemon=True,
        ),
        threading.Thread(
            target=copy_limited_stream,
            args=(proc.stderr, stderr, max_output_bytes, counter, lock, limit_event, decode_error_event),
            daemon=True,
        ),
    ]
    known_descendants: set[int] = set()
    started_threads: list[threading.Thread] = []
    try:
        for thread in threads:
            thread.start()
            started_threads.append(thread)
        deadline = time.monotonic() + timeout_seconds if timeout_seconds > 0 else None
        while proc.poll() is None:
            if os.name == "nt":
                known_descendants.update(windows_descendant_pids(proc.pid))
            if decode_error_event.is_set():
                raise OutputDecodeError
            if limit_event.is_set():
                raise OutputLimitExceeded
            if deadline is not None and time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(command, timeout_seconds)
            time.sleep(0.05)

        for thread in threads:
            thread.join(timeout=1)
        if decode_error_event.is_set():
            raise OutputDecodeError
        if limit_event.is_set():
            raise OutputLimitExceeded
        if os.name == "nt":
            settle_deadline = time.monotonic() + DESCENDANT_START_SETTLE_SECONDS
            while time.monotonic() < settle_deadline:
                known_descendants.update(windows_descendant_pids(proc.pid))
                if windows_tracked_processes_active(job, known_descendants):
                    break
                time.sleep(0.01)
            grace_deadline = time.monotonic() + DESCENDANT_EXIT_GRACE_SECONDS
            while time.monotonic() < grace_deadline and windows_tracked_processes_active(
                job, known_descendants
            ):
                time.sleep(0.05)
            if windows_tracked_processes_active(job, known_descendants):
                pids = windows_tracked_process_ids(job, known_descendants)
                pids.discard(proc.pid)
                raise DescendantProcessSurvived(windows_process_details(pids))
        if os.name != "nt":
            try:
                os.killpg(proc.pid, 0)
            except ProcessLookupError:
                pass
            except PermissionError:
                raise DescendantProcessSurvived
            else:
                raise DescendantProcessSurvived
        return int(proc.returncode or 0), containment
    finally:
        if proc.poll() is None or (
            os.name == "nt" and windows_tracked_processes_active(job, known_descendants)
        ):
            stop_process(proc, job)
            job = None
        elif os.name != "nt":
            try:
                os.killpg(proc.pid, 0)
            except (ProcessLookupError, PermissionError):
                pass
            else:
                stop_process(proc, job)
                job = None
        close_windows_job(job)
        for thread in started_threads:
            thread.join(timeout=1)


def has_unsafe_tool_value(tools: str) -> bool:
    tokens = [token for token in re.split(r"[\s,]+", tools.strip().lower()) if token]
    return any(token in UNSAFE_TOOL_VALUES for token in tokens)


def configure_execution_profile(args: argparse.Namespace) -> None:
    if args.execution_profile == "default":
        if args.hostile_write_nonce or args.protected_sentinel:
            raise ValueError(
                "--hostile-write-nonce and --protected-sentinel require "
                f"--execution-profile {HOSTILE_WRITE_PROFILE}."
            )
        return
    if args.execution_profile != HOSTILE_WRITE_PROFILE:
        raise ValueError(f"Unsupported execution profile: {args.execution_profile}")
    if not args.hostile_write_nonce:
        raise ValueError("The hostile-workspace-write profile requires --hostile-write-nonce.")
    if not args.expected_cli_version:
        raise ValueError("The hostile-workspace-write profile requires --expected-cli-version.")
    if args.out_dir is None or not args.allow_outside_workspace_out_dir:
        raise ValueError(
            "The hostile-workspace-write profile requires an explicit parent-controlled --out-dir "
            "and --allow-outside-workspace-out-dir."
        )
    if args.allow_shell_wrapper:
        raise ValueError("The hostile-workspace-write profile requires a native executable, not a shell wrapper.")
    if any((args.claude_arg, args.mcp_config, args.model, args.effort)):
        raise ValueError(
            "The hostile-workspace-write profile forbids raw args, MCP configs, and model/effort overrides."
        )
    if args.allow_unsafe or args.inherit_sensitive_auth_env or not args.safe_mode:
        raise ValueError("The hostile-workspace-write profile forbids unsafe, environment, and customization overrides.")
    try:
        budget = Decimal(args.max_budget_usd)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("The hostile-workspace-write profile requires a bounded decimal budget.") from exc
    if not budget.is_finite() or budget <= 0 or budget > Decimal("0.05"):
        raise ValueError("The hostile-workspace-write profile requires --max-budget-usd at or below 0.05.")
    args.permission_mode = "acceptEdits"
    args.tools = "Write"
    args.output_format = "stream-json"
    args.safe_mode = True
    args.strict_mcp_config = True
    args.no_session_persistence = True


def validate_depth_policy(args: argparse.Namespace) -> None:
    if args.run_depth < 0:
        raise ValueError("--run-depth cannot be negative.")
    if args.max_depth < 0:
        raise ValueError("--max-depth cannot be negative.")
    if args.run_depth > args.max_depth:
        raise ValueError("--run-depth exceeds --max-depth; refusing recursive handoff.")
    if args.parent_run_id and not RUN_ID_PATTERN.fullmatch(args.parent_run_id):
        raise ValueError("--parent-run-id contains unsupported characters or is too long.")
    if args.parent_run_id and args.run_depth == 0:
        raise ValueError("--parent-run-id requires --run-depth greater than 0.")
    if args.run_depth > 0 and not args.parent_run_id:
        raise ValueError("--run-depth greater than 0 requires --parent-run-id.")


def validate_policy(args: argparse.Namespace) -> None:
    configure_execution_profile(args)
    validate_depth_policy(args)
    if args.permission_mode in UNSAFE_PERMISSION_MODES and not args.allow_unsafe:
        raise ValueError(f"{args.permission_mode} requires --allow-unsafe and --unsafe-reason.")
    if has_unsafe_tool_value(args.tools) and not args.allow_unsafe:
        raise ValueError('Broad Claude tool access requires --allow-unsafe and --unsafe-reason.')
    if args.allow_unsafe and not args.unsafe_reason:
        raise ValueError("--allow-unsafe requires --unsafe-reason.")
    if not AGENT_PATTERN.fullmatch(args.origin_agent):
        raise ValueError(f"--origin-agent must match {AGENT_PATTERN.pattern}")
    if args.claude_arg and not args.allow_raw_claude_arg:
        raise ValueError("--claude-arg requires --allow-raw-claude-arg.")
    if args.claude_arg and (not args.allow_unsafe or not args.unsafe_reason):
        raise ValueError("--claude-arg requires --allow-unsafe and --unsafe-reason.")
    for raw_arg in args.claude_arg:
        flag = raw_arg.split("=", 1)[0]
        if flag in RESERVED_CLAUDE_RAW_FLAGS:
            raise ValueError(f"Raw Claude arg {flag} conflicts with a launcher-controlled option.")
    if not args.strict_mcp_config and (not args.allow_unsafe or not args.unsafe_reason):
        raise ValueError("--allow-configured-mcp requires --allow-unsafe and --unsafe-reason.")
    if args.mcp_config and not args.allow_mcp_config:
        raise ValueError("--mcp-config requires --allow-mcp-config.")
    if args.mcp_config and (not args.allow_unsafe or not args.unsafe_reason):
        raise ValueError("--mcp-config requires --allow-unsafe and --unsafe-reason.")
    if not args.safe_mode and (not args.allow_unsafe or not args.unsafe_reason):
        raise ValueError("--allow-customizations requires --allow-unsafe and --unsafe-reason.")
    if args.timeout_seconds < 0:
        raise ValueError("--timeout-seconds cannot be negative.")
    if args.max_output_bytes < 0:
        raise ValueError("--max-output-bytes cannot be negative.")
    if args.max_prompt_bytes <= 0:
        raise ValueError("--max-prompt-bytes must be greater than zero.")
    if args.inherit_sensitive_auth_env and (not args.allow_unsafe or not args.unsafe_reason):
        raise ValueError("--inherit-sensitive-auth-env requires --allow-unsafe and --unsafe-reason.")
    if args.max_budget_usd is not None:
        try:
            budget = Decimal(args.max_budget_usd)
        except InvalidOperation as exc:
            raise ValueError("--max-budget-usd must be a finite positive decimal.") from exc
        if not budget.is_finite() or budget <= 0:
            raise ValueError("--max-budget-usd must be a finite positive decimal.")


def validate_prompt_size(prompt: str, max_prompt_bytes: int) -> int:
    if "\x00" in prompt:
        raise ValueError("Prompt cannot contain a NUL character.")
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > max_prompt_bytes:
        raise ValueError(
            f"Prompt is {prompt_bytes} UTF-8 bytes, exceeding --max-prompt-bytes={max_prompt_bytes}."
        )
    return prompt_bytes


def validate_command_length(command: list[str]) -> None:
    if os.name != "nt":
        return
    command_line = subprocess.list2cmdline(command)
    utf16_units = len(command_line.encode("utf-16-le")) // 2
    if utf16_units > MAX_WINDOWS_COMMAND_UNITS:
        raise ValueError(
            f"Windows command line is {utf16_units} UTF-16 units; limit is {MAX_WINDOWS_COMMAND_UNITS}. "
            "Use a smaller prompt."
        )


def build_child_env(args: argparse.Namespace, run_id: str) -> tuple[dict[str, str], list[str]]:
    env = os.environ.copy()
    env["CAIRNSPAN_RUN_ID"] = run_id
    env["CAIRNSPAN_RUN_DEPTH"] = str(args.run_depth)
    env["CAIRNSPAN_MAX_DEPTH"] = str(args.max_depth)
    scrubbed: list[str] = []
    if not args.inherit_sensitive_auth_env:
        for name in SENSITIVE_AUTH_ENV_VARS:
            if name in env:
                env.pop(name)
                scrubbed.append(name)
    return env, scrubbed


def prepare_receipt_paths(out_dir: Path, overwrite: bool) -> None:
    for name in RECEIPT_NAMES:
        path = out_dir / name
        if not os.path.lexists(path):
            continue
        if not overwrite:
            raise ValueError(f"Receipt path already exists: {path}")
        if path.is_dir() and not path.is_symlink():
            raise ValueError(f"Receipt path is a directory and cannot be replaced: {path}")
        path.unlink()


def record_forced_cleanup(summary: CairnspanSummary) -> None:
    summary.containment = "job-object" if os.name == "nt" else "process-group"
    summary.descendant_cleanup_verified = os.name == "nt"


def make_summary(
    args: argparse.Namespace,
    run_id: str,
    cwd: Path,
    out_dir: Path,
    prompt: str,
    prompt_file: str | None,
    command: list[str],
    claude_bin: Path | None,
    status: str,
) -> CairnspanSummary:
    events_path = out_dir / "events.jsonl"
    transcript_path = out_dir / "transcript.log"
    final_path = out_dir / "final.md"
    summary_path = out_dir / "cairnspan-summary.json"
    return CairnspanSummary(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        parent_run_id=args.parent_run_id,
        run_depth=args.run_depth,
        max_depth=args.max_depth,
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        origin_agent=args.origin_agent,
        target_agent="claude-code",
        target_workspace=str(cwd),
        cwd=str(cwd),
        command=redact_command(command, prompt, args.claude_arg + (args.mcp_config or [])),
        launcher_command_sha256=getattr(args, "launcher_command_sha256", None),
        claude_bin_resolved=str(claude_bin) if claude_bin else None,
        target_cli_version=None,
        expected_cli_version=args.expected_cli_version,
        dry_run=not args.execute,
        status=status,
        permission_mode=args.permission_mode,
        tools=args.tools,
        output_format=args.output_format,
        strict_mcp_config=args.strict_mcp_config,
        safe_mode=args.safe_mode,
        max_budget_usd=args.max_budget_usd,
        requested_model=args.model,
        requested_effort=args.effort,
        prompt_file=prompt_file,
        prompt_sha256=sha256_text(prompt),
        out_dir=str(out_dir),
        events_log=str(events_path),
        transcript_log=str(transcript_path),
        final_message=str(final_path),
        summary_file=str(summary_path),
        timeout_seconds=args.timeout_seconds,
        max_output_bytes=args.max_output_bytes,
        max_prompt_bytes=args.max_prompt_bytes,
        prompt_bytes=len(prompt.encode("utf-8")),
        scrubbed_env=sorted(
            name for name in SENSITIVE_AUTH_ENV_VARS if name in os.environ and not args.inherit_sensitive_auth_env
        ),
        execution_profile=args.execution_profile,
        unsafe_reason=redact_text(args.unsafe_reason) if args.unsafe_reason else None,
    )


def config_error(args: argparse.Namespace, run_id: str, message: str) -> int:
    out_dir = config_error_out_dir(args, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    empty_prompt = (
        hostile_write_prompt("claude-code", args.hostile_write_nonce)
        if args.hostile_write_nonce
        else (args.prompt or "")
    )
    cwd = args.cwd.resolve()
    summary = make_summary(
        args=args,
        run_id=run_id,
        cwd=cwd,
        out_dir=out_dir,
        prompt=empty_prompt,
        prompt_file=str(args.prompt_file.resolve()) if args.prompt_file else None,
        command=[],
        claude_bin=None,
        status="config_error",
    )
    summary.return_code = 2
    summary.error_kind = "config"
    summary.error = message
    try:
        write_json(Path(summary.summary_file), asdict(summary))
    except OSError:
        fallback = safe_default_out_dir(args.cwd.resolve() if args.cwd.is_dir() else Path.cwd().resolve(), run_id)
        fallback.mkdir(parents=True, exist_ok=True)
        summary = make_summary(
            args, run_id, args.cwd.resolve(), fallback, empty_prompt,
            str(args.prompt_file.resolve()) if args.prompt_file else None, [], None, "config_error",
        )
        summary.return_code = 2
        summary.error_kind = "config"
        summary.error = message
        write_json(Path(summary.summary_file), asdict(summary))
    print(json.dumps(asdict(summary), indent=2, sort_keys=True), file=sys.stderr)
    return 2


def run(args: argparse.Namespace) -> int:
    run_id = make_run_id()
    prepared_profile: PreparedProfile | None = None
    try:
        validate_policy(args)
        prompt, prompt_file = read_prompt(args)
        validate_prompt_size(prompt, args.max_prompt_bytes)
        cwd = args.cwd.resolve()
        if not cwd.is_dir():
            raise ValueError(f"Target workspace does not exist or is not a directory: {cwd}")
        claude_bin = resolve_claude_bin(args.claude_bin, cwd, args.allow_shell_wrapper)
        command = build_command(args, claude_bin, prompt)
        validate_command_length(command)
        out_dir = resolve_out_dir(args, cwd, run_id)
        if args.execution_profile == HOSTILE_WRITE_PROFILE:
            if out_dir.exists():
                raise ValueError("The hostile-workspace-write profile requires a fresh --out-dir.")
            prepared_profile = prepare_hostile_write(
                cwd, "claude-code", args.hostile_write_nonce, args.protected_sentinel
            )
    except (FileNotFoundError, UnicodeError, ValueError) as exc:
        return config_error(args, run_id, str(exc))

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        prepare_receipt_paths(out_dir, args.overwrite_out_dir)
    except ValueError as exc:
        return config_error(args, run_id, str(exc))
    if prepared_profile and args.execute:
        write_manifest_atomic(out_dir / BEFORE_MANIFEST_NAME, prepared_profile.before_manifest)

    events_path = out_dir / "events.jsonl"
    transcript_path = out_dir / "transcript.log"
    final_path = out_dir / "final.md"
    summary_path = out_dir / "cairnspan-summary.json"
    child_env, _ = build_child_env(args, run_id)
    summary = make_summary(args, run_id, cwd, out_dir, prompt, prompt_file, command, claude_bin, "dry_run")
    if prepared_profile:
        summary.declared_write_path = prepared_profile.declared_path
        summary.allowed_tool_names = list(prepared_profile.allowed_tools)
        summary.write_profile_status = "prepared"
        summary.write_profile_nonce_sha256 = prepared_profile.nonce_sha256
        summary.write_profile_before_manifest = str(out_dir / BEFORE_MANIFEST_NAME)
        summary.write_profile_after_manifest = str(out_dir / AFTER_MANIFEST_NAME)
        summary.protected_sentinel_sha256 = prepared_profile.sentinel.sha256

    try:
        summary.target_cli_version = probe_cli_version(claude_bin, cwd, version_probe_env(child_env))
        if args.expected_cli_version and summary.target_cli_version != args.expected_cli_version:
            raise VersionProbeError(
                f"target CLI version mismatch: expected {args.expected_cli_version!r}, "
                f"observed {summary.target_cli_version!r}"
            )
    except VersionProbeError as exc:
        summary.status = "config_error"
        summary.return_code = 2
        summary.error_kind = "version_probe"
        summary.error = str(exc)
        write_json(summary_path, asdict(summary))
        print(json.dumps(asdict(summary), indent=2, sort_keys=True))
        return 2

    if not args.execute:
        write_json(summary_path, asdict(summary))
        print(json.dumps(asdict(summary), indent=2, sort_keys=True))
        return 0

    start_time = time.monotonic()
    summary.status = "running"
    write_json(summary_path, asdict(summary))
    capture_nonce = uuid.uuid4().hex
    events_temp = out_dir / f".events.{capture_nonce}.tmp"
    transcript_temp = out_dir / f".transcript.{capture_nonce}.tmp"
    capture_valid = True
    with events_temp.open("x", encoding="utf-8") as events_file, transcript_temp.open(
        "x", encoding="utf-8", errors="replace"
    ) as transcript_file:
        events_identity = capture_identity(events_file)
        transcript_identity = capture_identity(transcript_file)
        try:
            summary.return_code, summary.containment = run_process(
                command,
                cwd,
                args.timeout_seconds,
                args.max_output_bytes,
                events_file,
                transcript_file,
                child_env,
            )
            summary.descendant_cleanup_verified = True
        except ContainmentUnavailable as exc:
            summary.return_code = 125
            summary.containment = "unavailable"
            transcript_file.write(f"\nCairnspan containment unavailable: {exc}\n")
        except subprocess.TimeoutExpired:
            summary.return_code = 124
            record_forced_cleanup(summary)
            transcript_file.write("\nCairnspan timeout reached.\n")
        except OutputLimitExceeded:
            summary.return_code = 125
            record_forced_cleanup(summary)
            transcript_file.write("\nCairnspan output limit reached.\n")
        except OutputDecodeError:
            summary.return_code = 65
            record_forced_cleanup(summary)
            transcript_file.write("\nCairnspan rejected non-UTF-8 target output.\n")
        except DescendantProcessSurvived as exc:
            summary.return_code = 125
            record_forced_cleanup(summary)
            summary.process_leak_details = exc.details
            transcript_file.write("\nCairnspan terminated a surviving target descendant.\n")
        except PermissionError as exc:
            summary.return_code = 126
            transcript_file.write(f"\nClaude executable could not be started: {exc}\n")
        except OSError as exc:
            summary.return_code = 126
            transcript_file.write(f"\nClaude executable could not be started: {exc}\n")
        capture_valid = capture_path_matches(events_temp, events_identity) and capture_path_matches(
            transcript_temp, transcript_identity
        )
        if not capture_valid:
            summary.return_code = 125
            transcript_file.write("\nCairnspan capture path identity changed.\n")

    summary.elapsed_seconds = round(time.monotonic() - start_time, 3)
    if not capture_valid:
        for path in (events_temp, transcript_temp):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        write_text_atomic(events_path, "")
        write_text_atomic(transcript_path, "Cairnspan rejected replaced capture files.\n")
        write_text_atomic(final_path, "")
        summary.status = "failed"
        summary.error_kind = "capture_tamper"
        summary.error = "Target capture path identity changed before receipt publication."
        summary.parse_warnings = ["capture path identity changed"]
        if prepared_profile:
            after_manifest = snapshot_workspace(cwd, strict=True)
            write_manifest_atomic(out_dir / AFTER_MANIFEST_NAME, after_manifest)
            summary.write_profile_status = "failed"
            summary.write_profile_changed_paths = [
                item["path"]
                for item in compare_manifests(prepared_profile.before_manifest, after_manifest)
            ]
            summary.protected_sentinel_unchanged = sentinel_matches(prepared_profile.sentinel)
            summary.policy_observations.append("target capture path identity changed")
        write_json(summary_path, asdict(summary))
        print(json.dumps(asdict(summary), indent=2, sort_keys=True))
        return 125
    parsed = parse_events(events_temp)
    summary.session_id = parsed.session_id
    summary.usage = parsed.usage
    summary.model_usage = parsed.model_usage
    summary.total_cost_usd = parsed.total_cost_usd
    summary.parse_warnings = parsed.warnings
    summary.terminal_event_count = parsed.terminal_event_count
    summary.observed_session_ids = parsed.observed_session_ids
    summary.init_capabilities = parsed.init_capabilities
    summary.tool_names = parsed.tool_names
    summary.tool_use_count = parsed.tool_use_count
    summary.mcp_tool_use_count = parsed.mcp_tool_use_count
    write_text_atomic(final_path, parsed.final_message)

    excerpt = transcript_excerpt(transcript_temp)
    summary.transcript_excerpt = excerpt or None
    error_kind, error = classify_failure(summary.return_code, excerpt, parsed)
    summary.error_kind = error_kind
    summary.error = error
    if summary.return_code == 125 and "surviving target descendant" in excerpt.lower():
        summary.error_kind = "process_leak"
        summary.error = "Claude Code left a descendant process running after target exit."
    if summary.containment == "unavailable":
        summary.error_kind = "containment"
        summary.error = "Strong Windows process containment was unavailable; target was not allowed to run."
    summary.status = "succeeded" if summary.return_code == 0 and not parsed.is_error else "failed"
    if summary.return_code == 0 and not parsed.is_error and (
        not parsed.completion_observed or not parsed.session_id or bool(parsed.warnings)
    ):
        summary.status = "failed"
        summary.error_kind = "protocol"
        summary.error = "Claude Code exited successfully without a complete JSON event receipt."
        if not parsed.completion_observed:
            summary.parse_warnings.append("result event was not observed")
        if not parsed.session_id:
            summary.parse_warnings.append("session id was not observed")
        if parsed.warnings:
            summary.error = "Claude Code JSON event receipt was incomplete or damaged."
    if summary.status == "succeeded" and args.max_budget_usd is not None and parsed.total_cost_usd is not None:
        if Decimal(str(parsed.total_cost_usd)) > Decimal(args.max_budget_usd):
            summary.status = "failed"
            summary.error_kind = "policy"
            summary.error = "Claude reported a total cost above the configured edge budget."
    if parsed.init_capabilities:
        advertised_customizations = [
            key
            for key in ("plugins", "skills", "slash_commands")
            if parsed.init_capabilities.get(key)
        ]
        if summary.safe_mode and advertised_customizations:
            summary.policy_observations.append(
                "safe-mode init advertised customization metadata for: "
                + ", ".join(advertised_customizations)
                + "; metadata does not prove those customizations were executable"
            )

    policy_violations: list[str] = []
    if parsed.init_capabilities:
        if summary.tools == "" and parsed.init_capabilities.get("tools"):
            policy_violations.append("Claude init advertised built-in tools despite an empty tool policy")
        if summary.strict_mcp_config and not args.mcp_config and parsed.init_capabilities.get("mcp_servers"):
            policy_violations.append("Claude init advertised MCP servers despite strict empty MCP configuration")
    if summary.tools == "" and parsed.tool_use_count:
        policy_violations.append("Claude emitted tool-use events despite an empty tool policy")
    if summary.strict_mcp_config and not args.mcp_config and parsed.mcp_tool_use_count:
        policy_violations.append("Claude emitted MCP tool-use events despite strict empty MCP configuration")
    if prepared_profile:
        advertised = set(parsed.init_capabilities.get("tools", [])) if parsed.init_capabilities else set()
        allowed = set(prepared_profile.allowed_tools)
        if not parsed.init_capabilities:
            policy_violations.append("Claude hostile-write profile did not emit init capabilities")
        elif advertised != allowed:
            policy_violations.append(
                f"Claude hostile-write profile advertised tools {sorted(advertised)} instead of {sorted(allowed)}"
            )
        observed = set(parsed.tool_names)
        if summary.return_code == 0 and not observed:
            policy_violations.append("Claude hostile-write profile did not emit a Write tool event")
        unexpected_tools = sorted(observed - allowed)
        if unexpected_tools:
            policy_violations.append(f"Claude hostile-write profile emitted unexpected tools: {unexpected_tools}")
    if summary.status == "succeeded" and policy_violations:
        summary.status = "failed"
        summary.error_kind = "policy"
        summary.error = "; ".join(policy_violations)
    if prepared_profile:
        profile_errors: list[str] = []
        if summary.return_code != 0:
            profile_errors.append("target did not complete successfully")
        after_manifest = snapshot_workspace(cwd, strict=True)
        write_manifest_atomic(out_dir / AFTER_MANIFEST_NAME, after_manifest)
        try:
            validation = validate_hostile_write_after(
                cwd, args.hostile_write_nonce, prepared_profile, after_manifest
            )
        except HostileWriteProfileError as exc:
            profile_errors.append(str(exc))
            summary.protected_sentinel_unchanged = sentinel_matches(prepared_profile.sentinel)
            summary.write_profile_changed_paths = [
                item["path"]
                for item in compare_manifests(prepared_profile.before_manifest, after_manifest)
            ]
        else:
            summary.write_profile_changed_paths = list(validation.changed_paths)
            summary.protected_sentinel_unchanged = validation.sentinel_unchanged
        if policy_violations:
            profile_errors.extend(policy_violations)
        if profile_errors:
            summary.write_profile_status = "failed"
            summary.policy_observations.extend(
                error for error in profile_errors if error not in summary.policy_observations
            )
            if summary.status == "succeeded":
                summary.status = "failed"
                summary.error_kind = "write_profile"
                summary.error = "; ".join(profile_errors)
        else:
            summary.write_profile_status = "passed"
    if error_kind == "permission":
        summary.status = "blocked"

    os.replace(events_temp, events_path)
    os.replace(transcript_temp, transcript_path)
    if prepared_profile:
        try:
            validate_hostile_write_receipts(out_dir, prepared_profile)
        except HostileWriteProfileError as exc:
            summary.write_profile_receipt_root_status = "failed"
            summary.write_profile_status = "failed"
            summary.policy_observations.append(str(exc))
            if summary.status == "succeeded":
                summary.status = "failed"
                summary.error_kind = "write_profile"
                summary.error = str(exc)
        else:
            summary.write_profile_receipt_root_status = "passed"
    write_json(summary_path, asdict(summary))
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return int(summary.return_code or (1 if summary.status != "succeeded" else 0))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch a scoped Claude Code session from another local agent.")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="Prompt to pass to Claude Code")
    prompt_group.add_argument("--prompt-file", type=Path, help="UTF-8 text file containing the prompt")
    prompt_group.add_argument(
        "--hostile-write-nonce",
        help="Parent nonce for the typed hostile-workspace-write profile",
    )
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="Target workspace for Claude Code")
    parser.add_argument("--out-dir", type=Path, help="Directory for Cairnspan logs and summary")
    parser.add_argument(
        "--allow-outside-workspace-out-dir",
        action="store_true",
        help="Allow --out-dir to resolve outside --cwd",
    )
    parser.add_argument(
        "--overwrite-out-dir",
        action="store_true",
        help="Allow writing into an existing non-empty --out-dir",
    )
    parser.add_argument("--claude-bin", default="claude", help="Claude executable path or PATH command name")
    parser.add_argument("--expected-cli-version", help="Fail before target launch unless `claude --version` matches exactly")
    parser.add_argument(
        "--allow-shell-wrapper",
        action="store_true",
        help="Allow a .cmd/.bat/.ps1 target executable after explicit review",
    )
    parser.add_argument("--origin-agent", default="unknown", help="Name of the agent or user requesting the run")
    parser.add_argument(
        "--execution-profile",
        choices=("default", HOSTILE_WRITE_PROFILE),
        default="default",
        help="Typed launcher policy profile",
    )
    parser.add_argument(
        "--protected-sentinel",
        type=Path,
        help="Hashed sibling sentinel required by the hostile-workspace-write profile",
    )
    parser.add_argument("--parent-run-id", help="Parent Cairnspan run id for recursive/two-way handoffs")
    parser.add_argument("--run-depth", type=int, default=0, help="Current Cairnspan handoff depth")
    parser.add_argument("--max-depth", type=int, default=1, help="Maximum allowed Cairnspan handoff depth")
    parser.add_argument(
        "--permission-mode",
        choices=("acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"),
        default="dontAsk",
        help="Claude Code permission mode",
    )
    parser.add_argument("--tools", default="", help='Claude Code built-in tools to expose; default "" disables all tools')
    parser.add_argument(
        "--output-format",
        choices=("json", "stream-json"),
        default="stream-json",
        help="Claude Code machine-readable output format",
    )
    parser.add_argument("--max-budget-usd", default="0.25", help="Claude Code spend cap for --print")
    parser.add_argument("--model", help="Optional Claude model override")
    parser.add_argument(
        "--effort",
        choices=EFFORT_LEVELS,
        help="Optional Claude effort override",
    )
    parser.add_argument(
        "--safe-mode",
        dest="safe_mode",
        action="store_true",
        default=True,
        help="Disable Claude Code customizations for this run; enabled by default",
    )
    parser.add_argument(
        "--allow-customizations",
        dest="safe_mode",
        action="store_false",
        help="Allow Claude Code project/user customizations (unsafe)",
    )
    parser.add_argument("--mcp-config", action="append", help="Claude Code MCP config JSON/path; repeatable")
    parser.add_argument(
        "--allow-mcp-config",
        action="store_true",
        help="Allow explicit Claude MCP configuration (requires unsafe acknowledgement)",
    )
    parser.add_argument(
        "--strict-mcp-config",
        dest="strict_mcp_config",
        action="store_true",
        default=True,
        help="Use only MCP servers from --mcp-config; enabled by default for isolation",
    )
    parser.add_argument(
        "--allow-configured-mcp",
        dest="strict_mcp_config",
        action="store_false",
        help="Allow Claude Code's configured MCP servers for this run",
    )
    parser.add_argument("--no-session-persistence", action="store_true", default=True, help="Disable session persistence")
    parser.add_argument("--allow-session-persistence", dest="no_session_persistence", action="store_false")
    parser.add_argument("--claude-arg", action="append", default=[], help="Extra raw Claude Code arg before the prompt")
    parser.add_argument("--allow-raw-claude-arg", action="store_true", help="Allow raw --claude-arg passthrough")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="Process timeout; use 0 for no timeout")
    parser.add_argument(
        "--max-output-bytes",
        type=int,
        default=10_000_000,
        help="Combined stdout/stderr byte limit for the target process; use 0 for no limit",
    )
    parser.add_argument(
        "--max-prompt-bytes",
        type=int,
        default=24_000,
        help="Maximum UTF-8 prompt size accepted before target launch",
    )
    parser.add_argument(
        "--inherit-sensitive-auth-env",
        dest="inherit_sensitive_auth_env",
        action="store_true",
        help="Pass raw API-key/provider-routing environment overrides to the child (unsafe)",
    )
    parser.add_argument("--allow-unsafe", action="store_true", help="Allow explicitly unsafe Claude permission choices")
    parser.add_argument("--unsafe-reason", help="Required explanation when --allow-unsafe is used")
    parser.add_argument("--execute", action="store_true", help="Run Claude Code; default writes a dry-run summary")
    parser.add_argument("--dry-run", action="store_true", help="Explicit no-op alias for the default behavior")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw_argv)
    launcher_command = [sys.executable, str(Path(__file__).resolve()), *raw_argv]
    args.launcher_command_sha256 = sha256_text(
        json.dumps(launcher_command, ensure_ascii=False, separators=(",", ":"))
    )
    if args.dry_run:
        args.execute = False
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
