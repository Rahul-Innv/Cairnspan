#!/usr/bin/env python3
"""Close one bounded Codex -> Claude -> Codex shared-mailbox route."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mailbox import SchemaError, validate_exchange
from workspace_manifest import compare, read_manifest


SCHEMA_VERSION = "0.2"
STRONG_CONTAINMENT = {"job-object"}


class MailboxRouteError(ValueError):
    """Raised when mailbox route evidence cannot close."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise MailboxRouteError(f"expected one JSON object: {path.name}")
    return value


def write_json_fresh(path: Path, value: dict[str, Any]) -> None:
    target = path.resolve(strict=False)
    if target.exists():
        raise MailboxRouteError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with temp.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, target)


def require_empty(value: Any, label: str) -> None:
    if value not in (None, [], {}):
        raise MailboxRouteError(f"{label} must be empty")


def validate_prompt(summary: dict[str, Any], prompt: Path, label: str) -> None:
    if summary.get("prompt_sha256") != sha256(prompt):
        raise MailboxRouteError(f"{label} prompt hash mismatch")


def validate_target_summary(summary: dict[str, Any], agent: str, sandbox: str) -> None:
    checks = {
        "status": "succeeded",
        "return_code": 0,
        "target_agent": agent,
        "sandbox": sandbox,
        "terminal_event_count": 1,
        "descendant_cleanup_verified": True,
    }
    if agent == "claude-code":
        checks.pop("sandbox")
    for key, expected in checks.items():
        if summary.get(key) != expected:
            raise MailboxRouteError(f"{agent} summary {key} did not satisfy route policy")
    if summary.get("containment") not in STRONG_CONTAINMENT:
        raise MailboxRouteError(f"{agent} summary containment did not satisfy route policy")
    if not isinstance(summary.get("target_cli_version"), str) or not summary["target_cli_version"]:
        raise MailboxRouteError(f"{agent} summary CLI version did not satisfy route policy")
    require_empty(summary.get("parse_warnings"), f"{agent} parse warnings")
    require_empty(summary.get("process_leak_details"), f"{agent} process leak details")
    identity_key = "session_id" if agent == "claude-code" else "thread_id"
    observed_key = "observed_session_ids" if agent == "claude-code" else "observed_thread_ids"
    identity = summary.get(identity_key)
    if not isinstance(identity, str) or not identity or summary.get(observed_key) != [identity]:
        raise MailboxRouteError(f"{agent} identity receipt is inconsistent")


def validate_claude_write(summary: dict[str, Any], budget: Decimal, model: str) -> Decimal:
    validate_target_summary(summary, "claude-code", "workspace-write")
    checks = {
        "permission_mode": "acceptEdits",
        "tools": "Read,Write",
        "safe_mode": True,
        "strict_mcp_config": True,
        "mcp_tool_use_count": 0,
        "requested_model": model,
    }
    for key, expected in checks.items():
        if summary.get(key) != expected:
            raise MailboxRouteError(f"Claude summary {key} did not satisfy mailbox policy")
    capabilities = summary.get("init_capabilities")
    if not isinstance(capabilities, dict) or set(capabilities.get("tools") or []) != {"Read", "Write"}:
        raise MailboxRouteError("Claude advertised tool set is not exactly Read and Write")
    for key in ("mcp_servers", "plugins", "skills", "slash_commands"):
        require_empty(capabilities.get(key), f"Claude init {key}")
    model_usage = summary.get("model_usage")
    if not isinstance(model_usage, dict) or model not in model_usage:
        raise MailboxRouteError("Claude actual model usage omitted the requested model")
    try:
        cost = Decimal(str(summary.get("total_cost_usd")))
    except (InvalidOperation, TypeError) as exc:
        raise MailboxRouteError("Claude cost receipt is invalid") from exc
    if not cost.is_finite() or cost < 0 or cost > budget:
        raise MailboxRouteError("Claude cost exceeds mailbox route budget")
    return cost


def validate_delta(before_path: Path, after_path: Path, expected: set[str], label: str) -> dict[str, Any]:
    before = read_manifest(before_path)
    after = read_manifest(after_path)
    if before.get("strict") is not True or after.get("strict") is not True:
        raise MailboxRouteError(f"{label} manifests must be strict")
    differences = compare(before, after)
    changed = {item["path"] for item in differences}
    if changed != expected:
        raise MailboxRouteError(f"{label} changed paths differ from policy: {sorted(changed)}")
    return {
        "status": "expected-change" if expected else "identical",
        "changed_paths": sorted(changed),
        "before_sha256": sha256(before_path),
        "after_sha256": sha256(after_path),
    }


def close(args: argparse.Namespace) -> dict[str, Any]:
    exchange = validate_exchange(args.mailbox_dir, args.request, args.response)
    write_summary = read_json(args.codex_write_summary)
    claude_summary = read_json(args.claude_summary)
    consume_summary = read_json(args.codex_consume_summary)
    validate_target_summary(write_summary, "codex", "workspace-write")
    validate_target_summary(consume_summary, "codex", "read-only")
    validate_prompt(write_summary, args.codex_write_prompt, "Codex write")
    validate_prompt(claude_summary, args.claude_prompt, "Claude write")
    validate_prompt(consume_summary, args.codex_consume_prompt, "Codex consume")
    try:
        budget = Decimal(args.max_claude_budget_usd)
    except InvalidOperation as exc:
        raise MailboxRouteError("Claude budget is invalid") from exc
    claude_cost = validate_claude_write(claude_summary, budget, args.claude_model)

    if not args.codex_write_final.read_text(encoding="utf-8").rstrip().endswith(args.write_marker):
        raise MailboxRouteError("Codex write final marker is missing")
    if args.claude_final.read_text(encoding="utf-8").strip() != args.claude_marker:
        raise MailboxRouteError("Claude final marker does not match")
    if args.codex_consume_final.read_text(encoding="utf-8").strip() != args.expected_consume_final:
        raise MailboxRouteError("Codex consume final does not match")

    shared_root = Path(read_manifest(args.before_write_manifest)["root"])
    request_relative = args.request.resolve().relative_to(shared_root.resolve()).as_posix()
    response_relative = args.response.resolve().relative_to(shared_root.resolve()).as_posix()
    request_parent = str(Path(request_relative).parent).replace("\\", "/")
    response_parent = str(Path(response_relative).parent).replace("\\", "/")
    manifests = {
        "codex_write": validate_delta(
            args.before_write_manifest,
            args.after_request_manifest,
            {request_parent, request_relative},
            "Codex write",
        ),
        "claude_write": validate_delta(
            args.after_request_manifest,
            args.after_response_manifest,
            {response_parent, response_relative},
            "Claude write",
        ),
        "codex_consume": validate_delta(
            args.after_response_manifest,
            args.after_consume_manifest,
            set(),
            "Codex consume",
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "closed",
        "route_type": "shared-mailbox-codex-claude-codex",
        "closed_at": utc_now(),
        "exchange": exchange,
        "claude_cost_usd": str(claude_cost),
        "manifests": manifests,
        "edges": [
            {"run_id": write_summary["run_id"], "agent": "codex", "containment": write_summary["containment"], "target_cli_version": write_summary["target_cli_version"], "summary_sha256": sha256(args.codex_write_summary)},
            {"run_id": claude_summary["run_id"], "agent": "claude-code", "containment": claude_summary["containment"], "target_cli_version": claude_summary["target_cli_version"], "summary_sha256": sha256(args.claude_summary)},
            {"run_id": consume_summary["run_id"], "agent": "codex", "containment": consume_summary["containment"], "target_cli_version": consume_summary["target_cli_version"], "summary_sha256": sha256(args.codex_consume_summary)},
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mailbox-dir", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--codex-write-summary", type=Path, required=True)
    parser.add_argument("--codex-write-final", type=Path, required=True)
    parser.add_argument("--codex-write-prompt", type=Path, required=True)
    parser.add_argument("--claude-summary", type=Path, required=True)
    parser.add_argument("--claude-final", type=Path, required=True)
    parser.add_argument("--claude-prompt", type=Path, required=True)
    parser.add_argument("--codex-consume-summary", type=Path, required=True)
    parser.add_argument("--codex-consume-final", type=Path, required=True)
    parser.add_argument("--codex-consume-prompt", type=Path, required=True)
    parser.add_argument("--before-write-manifest", type=Path, required=True)
    parser.add_argument("--after-request-manifest", type=Path, required=True)
    parser.add_argument("--after-response-manifest", type=Path, required=True)
    parser.add_argument("--after-consume-manifest", type=Path, required=True)
    parser.add_argument("--write-marker", default="mailbox-request-written")
    parser.add_argument("--claude-marker", default="mailbox-response-written")
    parser.add_argument("--expected-consume-final", required=True)
    parser.add_argument("--claude-model", default="claude-sonnet-5")
    parser.add_argument("--max-claude-budget-usd", default="0.05")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        value = close(args)
        write_json_fresh(args.out, value)
    except (FileNotFoundError, InvalidOperation, json.JSONDecodeError, MailboxRouteError, OSError, SchemaError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"status": value["status"], "output": str(args.out.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
