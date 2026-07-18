#!/usr/bin/env python3
"""Prepare and close a parent-linked Codex visual -> Claude synthesis route."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from prepare_critique_handoff import HandoffError, require_exact_keys, require_text, require_text_list, validate_critique
from workspace_manifest import compare as compare_manifests
from workspace_manifest import read_manifest


SCHEMA_VERSION = "0.1"
SYNTHESIS_KEYS = {
    "status",
    "accepted_findings",
    "rejected_or_deferred",
    "needs_source_verification",
    "recommended_first_slice",
    "risk_notes",
    "next_codex_review_prompt",
}
ACCEPTED_KEYS = {"finding", "reason", "priority"}
DEFERRED_KEYS = {"finding", "reason"}
VERIFY_KEYS = {"question", "likely_location"}
SYNTHESIS_SLICE_KEYS = {"goal", "scope", "non_goals", "acceptance_checks", "owner_approval_needed"}
PRIORITIES = {"P0", "P1", "P2"}
REQUIRED_CODEX_DISABLED = {"apps", "image_generation", "plugins", "shell_tool", "web_search"}


class RouteReceiptError(ValueError):
    """Raised when an edge cannot enter or close the critique route."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise RouteReceiptError(f"expected one JSON object: {path.name}")
    return value


def write_json_fresh(path: Path, value: dict[str, Any]) -> None:
    target = path.resolve(strict=False)
    if target.exists():
        raise RouteReceiptError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with temp.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temp, target)


def require_empty(value: Any, label: str) -> None:
    if value not in (None, [], {}):
        raise RouteReceiptError(f"{label} must be empty")


def validate_identical_manifests(before_path: Path, after_path: Path, label: str) -> dict[str, Any]:
    before = read_manifest(before_path)
    after = read_manifest(after_path)
    differences = compare_manifests(before, after)
    if differences:
        raise RouteReceiptError(f"{label} manifests differ at {len(differences)} path(s)")
    if before.get("strict") is not True:
        raise RouteReceiptError(f"{label} manifests are not strict")
    return {
        "status": "identical",
        "before_sha256": file_sha256(before_path),
        "after_sha256": file_sha256(after_path),
        "entry_count": len(before.get("entries", [])),
    }


def validate_codex_summary(summary: dict[str, Any]) -> None:
    checks = {
        "status": "succeeded",
        "return_code": 0,
        "sandbox": "read-only",
        "strict_isolation": True,
        "tool_use_count": 0,
        "mcp_tool_use_count": 0,
        "terminal_event_count": 1,
        "descendant_cleanup_verified": True,
    }
    for key, expected in checks.items():
        if summary.get(key) != expected:
            raise RouteReceiptError(f"Codex summary {key} did not satisfy route policy")
    if summary.get("containment") != "job-object":
        raise RouteReceiptError("Codex summary containment did not satisfy route policy")
    if not isinstance(summary.get("target_cli_version"), str) or not summary["target_cli_version"]:
        raise RouteReceiptError("Codex summary CLI version did not satisfy route policy")
    if not isinstance(summary.get("thread_id"), str) or not summary["thread_id"]:
        raise RouteReceiptError("Codex thread identity is missing")
    if summary.get("observed_thread_ids") != [summary["thread_id"]]:
        raise RouteReceiptError("Codex observed thread identities are inconsistent")
    require_empty(summary.get("parse_warnings"), "Codex parse warnings")
    require_empty(summary.get("process_leak_details"), "Codex process leak details")
    disabled = set(summary.get("disabled_features") or [])
    if not {"apps", "image_generation", "plugins", "shell_tool"}.issubset(disabled):
        raise RouteReceiptError("Codex strict disabled-feature receipt is incomplete")


def validate_synthesis(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RouteReceiptError("Claude synthesis must be one JSON object")
    try:
        require_exact_keys(value, SYNTHESIS_KEYS, "synthesis")
        if value.get("status") != "synthesis-complete":
            raise RouteReceiptError("synthesis status must be synthesis-complete")

        accepted_raw = value.get("accepted_findings")
        if not isinstance(accepted_raw, list) or not 1 <= len(accepted_raw) <= 30:
            raise RouteReceiptError("accepted_findings must contain 1-30 items")
        accepted: list[dict[str, str]] = []
        for index, item in enumerate(accepted_raw):
            if not isinstance(item, dict):
                raise RouteReceiptError(f"accepted_findings[{index}] must be an object")
            require_exact_keys(item, ACCEPTED_KEYS, f"accepted_findings[{index}]")
            priority = require_text(item.get("priority"), f"accepted_findings[{index}].priority", max_chars=2)
            if priority not in PRIORITIES:
                raise RouteReceiptError(f"accepted_findings[{index}].priority is invalid")
            accepted.append({
                "finding": require_text(item.get("finding"), f"accepted_findings[{index}].finding"),
                "reason": require_text(item.get("reason"), f"accepted_findings[{index}].reason"),
                "priority": priority,
            })

        deferred: list[dict[str, str]] = []
        deferred_raw = value.get("rejected_or_deferred")
        if not isinstance(deferred_raw, list) or len(deferred_raw) > 30:
            raise RouteReceiptError("rejected_or_deferred must contain 0-30 items")
        for index, item in enumerate(deferred_raw):
            if not isinstance(item, dict):
                raise RouteReceiptError(f"rejected_or_deferred[{index}] must be an object")
            require_exact_keys(item, DEFERRED_KEYS, f"rejected_or_deferred[{index}]")
            deferred.append({
                "finding": require_text(item.get("finding"), f"rejected_or_deferred[{index}].finding"),
                "reason": require_text(item.get("reason"), f"rejected_or_deferred[{index}].reason"),
            })

        verification: list[dict[str, str]] = []
        verification_raw = value.get("needs_source_verification")
        if not isinstance(verification_raw, list) or len(verification_raw) > 30:
            raise RouteReceiptError("needs_source_verification must contain 0-30 items")
        for index, item in enumerate(verification_raw):
            if not isinstance(item, dict):
                raise RouteReceiptError(f"needs_source_verification[{index}] must be an object")
            require_exact_keys(item, VERIFY_KEYS, f"needs_source_verification[{index}]")
            verification.append({
                "question": require_text(item.get("question"), f"needs_source_verification[{index}].question"),
                "likely_location": require_text(
                    item.get("likely_location"), f"needs_source_verification[{index}].likely_location"
                ),
            })

        first_slice = value.get("recommended_first_slice")
        if not isinstance(first_slice, dict):
            raise RouteReceiptError("recommended_first_slice must be an object")
        require_exact_keys(first_slice, SYNTHESIS_SLICE_KEYS, "recommended_first_slice")
        normalized_slice = {
            "goal": require_text(first_slice.get("goal"), "recommended_first_slice.goal"),
            "scope": require_text_list(first_slice.get("scope"), "recommended_first_slice.scope", maximum=20),
            "non_goals": require_text_list(
                first_slice.get("non_goals"), "recommended_first_slice.non_goals", maximum=20
            ),
            "acceptance_checks": require_text_list(
                first_slice.get("acceptance_checks"), "recommended_first_slice.acceptance_checks", maximum=30
            ),
            "owner_approval_needed": require_text_list(
                first_slice.get("owner_approval_needed"),
                "recommended_first_slice.owner_approval_needed",
                minimum=0,
                maximum=20,
            ),
        }
        return {
            "status": "synthesis-complete",
            "accepted_findings": accepted,
            "rejected_or_deferred": deferred,
            "needs_source_verification": verification,
            "recommended_first_slice": normalized_slice,
            "risk_notes": require_text_list(value.get("risk_notes"), "risk_notes", maximum=20),
            "next_codex_review_prompt": require_text(
                value.get("next_codex_review_prompt"), "next_codex_review_prompt", max_chars=5_000
            ),
        }
    except HandoffError as exc:
        raise RouteReceiptError(str(exc)) from exc


def validate_claude_summary(summary: dict[str, Any], plan: dict[str, Any]) -> Decimal:
    checks = {
        "status": "succeeded",
        "return_code": 0,
        "safe_mode": True,
        "strict_mcp_config": True,
        "tools": "",
        "tool_use_count": 0,
        "mcp_tool_use_count": 0,
        "terminal_event_count": 1,
        "descendant_cleanup_verified": True,
        "parent_run_id": plan["codex_edge"]["run_id"],
        "run_depth": 1,
        "max_depth": 1,
        "prompt_sha256": plan["claude_edge_policy"]["prompt_sha256"],
        "requested_model": plan["claude_edge_policy"]["model"],
    }
    for key, expected in checks.items():
        if summary.get(key) != expected:
            raise RouteReceiptError(f"Claude summary {key} did not satisfy route policy")
    if summary.get("containment") != "job-object":
        raise RouteReceiptError("Claude summary containment did not satisfy route policy")
    if not isinstance(summary.get("target_cli_version"), str) or not summary["target_cli_version"]:
        raise RouteReceiptError("Claude summary CLI version did not satisfy route policy")
    if not isinstance(summary.get("session_id"), str) or not summary["session_id"]:
        raise RouteReceiptError("Claude session identity is missing")
    if summary.get("observed_session_ids") != [summary["session_id"]]:
        raise RouteReceiptError("Claude observed session identities are inconsistent")
    require_empty(summary.get("parse_warnings"), "Claude parse warnings")
    require_empty(summary.get("process_leak_details"), "Claude process leak details")
    capabilities = summary.get("init_capabilities")
    if not isinstance(capabilities, dict):
        raise RouteReceiptError("Claude init capabilities are missing")
    for key in ("tools", "mcp_servers", "plugins", "skills", "slash_commands"):
        require_empty(capabilities.get(key), f"Claude init {key}")
    model_usage = summary.get("model_usage")
    expected_model = plan["claude_edge_policy"]["model"]
    if not isinstance(model_usage, dict) or expected_model not in model_usage:
        raise RouteReceiptError("Claude actual model usage does not include the requested route model")
    try:
        cost = Decimal(str(summary.get("total_cost_usd")))
        budget = Decimal(str(plan["claude_edge_policy"]["max_budget_usd"]))
    except (InvalidOperation, TypeError) as exc:
        raise RouteReceiptError("Claude cost receipt is invalid") from exc
    if not math.isfinite(float(cost)) or cost < 0 or cost > budget:
        raise RouteReceiptError("Claude cost exceeded route policy")
    return cost


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    summary = read_json(args.codex_summary)
    validate_codex_summary(summary)
    if file_sha256(args.codex_prompt) != summary.get("prompt_sha256"):
        raise RouteReceiptError("Codex prompt hash does not match its summary")
    critique = validate_critique(json.loads(args.codex_final.read_text(encoding="utf-8", errors="strict")))
    packet = validate_identical_manifests(args.packet_before, args.packet_after, "Codex packet")
    snapshot = read_json(args.snapshot_manifest)
    if snapshot.get("status") != "succeeded" or snapshot.get("source_commit") is None:
        raise RouteReceiptError("snapshot manifest is not successful")
    try:
        budget = Decimal(args.max_claude_budget_usd)
    except InvalidOperation as exc:
        raise RouteReceiptError("Claude budget is invalid") from exc
    if budget <= 0:
        raise RouteReceiptError("Claude budget must be positive")
    plan = {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "route_type": "codex-visual-to-claude-synthesis",
        "created_at": utc_now(),
        "source_commit": snapshot["source_commit"],
        "snapshot_manifest_sha256": file_sha256(args.snapshot_manifest),
        "packet_manifest": packet,
        "codex_edge": {
            "run_id": summary.get("run_id"),
            "thread_id": summary.get("thread_id"),
            "summary_sha256": file_sha256(args.codex_summary),
            "prompt_sha256": summary.get("prompt_sha256"),
            "final_sha256": file_sha256(args.codex_final),
            "critique_status": critique["status"],
            "issue_count": len(critique["issues"]),
            "containment": summary.get("containment"),
            "target_cli_version": summary.get("target_cli_version"),
        },
        "claude_edge_policy": {
            "prompt_sha256": file_sha256(args.claude_prompt),
            "max_budget_usd": str(budget),
            "model": args.claude_model,
            "max_depth": 1,
            "run_depth": 1,
            "tools": "",
            "strict_mcp_config": True,
            "safe_mode": True,
            "timeout_seconds": 120,
            "max_output_bytes": 1_048_576,
        },
    }
    if not isinstance(plan["codex_edge"]["run_id"], str) or not plan["codex_edge"]["run_id"]:
        raise RouteReceiptError("Codex run id is missing")
    return plan


def close(args: argparse.Namespace) -> dict[str, Any]:
    plan = read_json(args.plan)
    if plan.get("schema_version") != SCHEMA_VERSION or plan.get("status") != "prepared":
        raise RouteReceiptError("route plan is not a prepared critique plan")
    summary = read_json(args.claude_summary)
    cost = validate_claude_summary(summary, plan)
    synthesis = validate_synthesis(json.loads(args.claude_final.read_text(encoding="utf-8", errors="strict")))
    workspace = validate_identical_manifests(args.claude_before, args.claude_after, "Claude workspace")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "closed",
        "route_type": plan["route_type"],
        "closed_at": utc_now(),
        "route_plan_sha256": file_sha256(args.plan),
        "source_commit": plan["source_commit"],
        "packet_manifest": plan["packet_manifest"],
        "claude_workspace_manifest": workspace,
        "edges": [
            plan["codex_edge"],
            {
                "run_id": summary.get("run_id"),
                "session_id": summary.get("session_id"),
                "summary_sha256": file_sha256(args.claude_summary),
                "prompt_sha256": summary.get("prompt_sha256"),
                "final_sha256": file_sha256(args.claude_final),
                "total_cost_usd": str(cost),
                "synthesis_status": synthesis["status"],
                "accepted_finding_count": len(synthesis["accepted_findings"]),
                "containment": summary.get("containment"),
                "target_cli_version": summary.get("target_cli_version"),
            },
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--codex-summary", type=Path, required=True)
    prepare_parser.add_argument("--codex-final", type=Path, required=True)
    prepare_parser.add_argument("--codex-prompt", type=Path, required=True)
    prepare_parser.add_argument("--snapshot-manifest", type=Path, required=True)
    prepare_parser.add_argument("--packet-before", type=Path, required=True)
    prepare_parser.add_argument("--packet-after", type=Path, required=True)
    prepare_parser.add_argument("--claude-prompt", type=Path, required=True)
    prepare_parser.add_argument("--max-claude-budget-usd", default="0.05")
    prepare_parser.add_argument("--claude-model", default="claude-sonnet-5")
    prepare_parser.add_argument("--out", type=Path, required=True)
    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("--plan", type=Path, required=True)
    close_parser.add_argument("--claude-summary", type=Path, required=True)
    close_parser.add_argument("--claude-final", type=Path, required=True)
    close_parser.add_argument("--claude-before", type=Path, required=True)
    close_parser.add_argument("--claude-after", type=Path, required=True)
    close_parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        value = prepare(args) if args.command == "prepare" else close(args)
        write_json_fresh(args.out, value)
    except (
        FileNotFoundError,
        HandoffError,
        InvalidOperation,
        json.JSONDecodeError,
        OSError,
        RouteReceiptError,
        UnicodeError,
        ValueError,
    ) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"status": value["status"], "output": str(args.out.resolve(strict=False))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
