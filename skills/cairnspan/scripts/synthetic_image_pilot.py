#!/usr/bin/env python3
"""Prepare, execute, and verify one finite three-item synthetic image pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from hostile_write_profile import path_is_reparse
from synthetic_probe_case import (
    AFTER_MANIFEST_NAME,
    APPROVAL_PATTERN,
    CLOSURE_NAME,
    PLAN_NAME as ITEM_PLAN_NAME,
    SyntheticProbeError,
    close_case,
    load_case,
    prepare_case,
    read_json_regular,
    sha256_file,
    verify_closed_case,
)
from workspace_manifest import write_json_atomic


SCHEMA_VERSION = "0.1"
MARKER_NAME = ".cairnspan-synthetic-image-pilot.json"
PLAN_NAME = "batch-plan.json"
STATE_NAME = "batch-state.json"
RESULT_NAME = "batch-result.json"
ITEM_COUNT = 3
DAILY_LEDGER_SCHEMA = "0.1"
SENSITIVE_PARTS = {".git", ".hg", ".svn", ".agents", ".claude", ".codex", ".cairnspan"}
BATCH_ROOT_NAMES = {MARKER_NAME, PLAN_NAME, STATE_NAME, RESULT_NAME, "items"}
ITEM_SPECS = (
    {
        "item_id": "paper-boat",
        "role": "probe",
        "description": "a small blue paper boat centered on a white background",
    },
    {
        "item_id": "geometric-sunrise",
        "role": "probe",
        "description": "an orange geometric sunrise above two simple navy hills on a white background",
    },
    {
        "item_id": "green-leaf",
        "role": "probe",
        "description": "one simple green leaf with a dark green stem centered on a white background",
    },
)


class PilotError(ValueError):
    """Raised when a pilot plan, execution, or receipt cannot be trusted."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json_fresh(path: Path, value: dict[str, Any]) -> None:
    if os.path.lexists(path):
        raise PilotError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, value)


def write_json_replace(path: Path, value: dict[str, Any]) -> None:
    if path_is_reparse(path.parent):
        raise PilotError(f"output parent is reparse-backed: {path.parent}")
    write_json_atomic(path, value)


def validate_fresh_root(root: Path) -> Path:
    if not root.is_absolute():
        raise PilotError("--batch-root must be absolute")
    if any(part.casefold() in SENSITIVE_PARTS for part in root.parts):
        raise PilotError("--batch-root cannot be inside a control or runtime directory")
    if os.path.lexists(root):
        raise PilotError("--batch-root must be fresh and must not already exist")
    if not root.parent.resolve().is_dir() or path_is_reparse(root.parent):
        raise PilotError("--batch-root parent must be one regular existing directory")
    return root


def validate_ledger_path(path: Path, batch_root: Path) -> Path:
    if not path.is_absolute():
        raise PilotError("--daily-ledger must be absolute")
    resolved = path.resolve(strict=False)
    if resolved == batch_root or batch_root in resolved.parents:
        raise PilotError("daily ledger must remain outside the disposable batch root")
    if not resolved.parent.is_dir() or path_is_reparse(resolved.parent):
        raise PilotError("daily ledger parent must be one regular existing directory")
    if os.path.lexists(resolved):
        if path_is_reparse(resolved) or not resolved.is_file() or resolved.stat().st_nlink != 1:
            raise PilotError("daily ledger must be one regular non-hardlinked file")
        load_daily_ledger(resolved)
    return resolved


def pilot_prompt(spec: dict[str, str]) -> str:
    return (
        "This is one item in a finite synthetic public-data Cairnspan image pilot.\n\n"
        "Use only the launched Codex session's built-in image generation capability.\n"
        "Do not use CLI/API fallback, web search, MCP, shell, or OPENAI_API_KEY.\n"
        "Create exactly one small static PNG and no other workspace file.\n"
        "Required output: .cairnspan-imagegen/probe-image.png\n"
        f"Requested image: {spec['description']}.\n"
        "Style: clean flat illustration. No text, logo, watermark, QR code, or URL.\n"
        "Verify the declared PNG exists and is nonempty.\n"
        "Return a concise report whose final nonempty line is exactly:\n"
        "imagegen-ok\n"
    )


def verified_capability(root: Path, expected: str) -> dict[str, Any]:
    try:
        verified = verify_closed_case(root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise PilotError(f"required {expected} capability closure did not verify: {exc}") from exc
    if verified.get("probe_name") != expected or verified.get("result", {}).get("capability") != f"ok({expected})":
        raise PilotError(f"required {expected} capability closure has the wrong disposition")
    return verified


def prepare_batch(args: argparse.Namespace) -> dict[str, Any]:
    root = validate_fresh_root(args.batch_root)
    ledger = validate_ledger_path(args.daily_ledger, root)
    generation = verified_capability(args.image_generation_case_root, "image-generation")
    viewing = verified_capability(args.image_view_case_root, "image-view")
    if generation["executable"] != viewing["executable"]:
        raise PilotError("image capability closures do not bind the same native executable identity")
    if args.daily_item_ceiling != ITEM_COUNT:
        raise PilotError(f"the first pilot requires --daily-item-ceiling={ITEM_COUNT}")
    if args.max_batch_seconds < ITEM_COUNT * 420 or args.max_batch_seconds > 3600:
        raise PilotError("--max-batch-seconds must be between 1260 and 3600")
    if args.max_batch_output_bytes < ITEM_COUNT * 1_048_576:
        raise PilotError("--max-batch-output-bytes is below the three declared per-run ceilings")
    if args.max_disk_bytes < ITEM_COUNT * 5_000_000:
        raise PilotError("--max-disk-bytes is below the three declared artifact ceilings")
    if args.retention_hours <= 0 or args.retention_hours > 24 * 30:
        raise PilotError("--retention-hours must be between 1 and 720")

    batch_id = uuid.uuid4().hex
    root.mkdir()
    items_root = root / "items"
    items_root.mkdir()
    item_plans: list[dict[str, Any]] = []
    executable = generation["executable"]
    for index, spec in enumerate(ITEM_SPECS, 1):
        item_root = items_root / f"{index:02d}-{spec['item_id']}"
        item_args = argparse.Namespace(
            case_root=item_root,
            probe="image-generation",
            codex_bin=Path(executable["path"]),
            expected_cli_version=executable["version"],
        )
        item_plan = prepare_case(
            item_args,
            prompt_text=pilot_prompt(spec),
            proposal_context={
                "batch_id": batch_id,
                "item_id": spec["item_id"],
                "item_index": index,
                "item_count": ITEM_COUNT,
                "role": spec["role"],
            },
        )
        item_plans.append({
            "item_id": spec["item_id"],
            "item_index": index,
            "role": spec["role"],
            "description": spec["description"],
            "case_root": item_plan["paths"]["case_root"],
            "proposal_id": item_plan["proposal_id"],
            "plan_sha256": sha256_file(item_root / ITEM_PLAN_NAME),
            "prompt_sha256": item_plan["request"]["prompt_sha256"],
            "expected_output": item_plan["request"]["expected_output"],
            "dry_run_command_sha256": item_plan["dry_run_command_sha256"],
            "execute_command_sha256": item_plan["execute_command_sha256"],
        })

    plan = {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "approval_state": "not-granted",
        "batch_id": batch_id,
        "created_at": utc_now(),
        "paths": {
            "batch_root": str(root),
            "items_root": str(items_root),
            "daily_ledger": str(ledger),
            "state": str(root / STATE_NAME),
            "result": str(root / RESULT_NAME),
        },
        "capability_prerequisites": {
            "image_generation": {
                "case_root": generation["case_root"],
                "proposal_id": generation["proposal_id"],
                "closure_sha256": generation["closure_sha256"],
            },
            "image_view": {
                "case_root": viewing["case_root"],
                "proposal_id": viewing["proposal_id"],
                "closure_sha256": viewing["closure_sha256"],
            },
        },
        "executable": executable,
        "policy": {
            "item_count": ITEM_COUNT,
            "concurrency": 1,
            "automatic_retries": 0,
            "max_batch_seconds": args.max_batch_seconds,
            "max_batch_output_bytes": args.max_batch_output_bytes,
            "max_disk_bytes": args.max_disk_bytes,
            "daily_item_ceiling": args.daily_item_ceiling,
            "retention_hours": args.retention_hours,
            "stop_before_next_on_any_failure": True,
            "resume_allowed": False,
            "product_integration": "not-authorized",
        },
        "items": item_plans,
    }
    write_json_fresh(root / PLAN_NAME, plan)
    marker = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "batch_root": str(root),
        "plan_sha256": sha256_file(root / PLAN_NAME),
    }
    write_json_fresh(root / MARKER_NAME, marker)
    return plan


def load_batch(root: Path, *, require_fresh_items: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    if not root.is_absolute() or path_is_reparse(root) or not root.is_dir():
        raise PilotError("--batch-root must be one existing regular absolute directory")
    marker = read_json_regular(root / MARKER_NAME)
    plan = read_json_regular(root / PLAN_NAME)
    root_names: set[str] = set()
    for path in root.iterdir():
        if path_is_reparse(path):
            raise PilotError(f"batch root contains a reparse entry: {path.name}")
        root_names.add(path.name)
    unexpected = root_names - BATCH_ROOT_NAMES
    if unexpected:
        raise PilotError(f"batch root contains unexpected entries: {sorted(unexpected)}")
    if marker.get("schema_version") != SCHEMA_VERSION or plan.get("schema_version") != SCHEMA_VERSION:
        raise PilotError("unsupported or mismatched batch schema")
    if plan.get("status") != "prepared" or plan.get("approval_state") != "not-granted":
        raise PilotError("batch is not in the immutable prepared state")
    if marker.get("batch_id") != plan.get("batch_id") or marker.get("batch_root") != str(root):
        raise PilotError("batch marker identity mismatch")
    if marker.get("plan_sha256") != sha256_file(root / PLAN_NAME):
        raise PilotError("batch plan hash mismatch")
    expected_paths = {
        "batch_root": str(root),
        "items_root": str(root / "items"),
        "state": str(root / STATE_NAME),
        "result": str(root / RESULT_NAME),
    }
    for name, value in expected_paths.items():
        if plan.get("paths", {}).get(name) != value:
            raise PilotError(f"batch path drift: {name}")
    policy = plan.get("policy", {})
    fixed = {
        "item_count": ITEM_COUNT,
        "concurrency": 1,
        "automatic_retries": 0,
        "daily_item_ceiling": ITEM_COUNT,
        "stop_before_next_on_any_failure": True,
        "resume_allowed": False,
        "product_integration": "not-authorized",
    }
    for name, value in fixed.items():
        if policy.get(name) != value:
            raise PilotError(f"batch policy drift: {name}")
    if not 1260 <= int(policy.get("max_batch_seconds", 0)) <= 3600:
        raise PilotError("batch runtime ceiling is outside the allowed range")
    if not 3_145_728 <= int(policy.get("max_batch_output_bytes", 0)) <= 12_000_000:
        raise PilotError("batch output ceiling is outside the allowed range")
    if not 15_000_000 <= int(policy.get("max_disk_bytes", 0)) <= 100_000_000:
        raise PilotError("batch disk ceiling is outside the allowed range")
    if not 1 <= int(policy.get("retention_hours", 0)) <= 720:
        raise PilotError("batch retention policy is outside the allowed range")
    generation = verified_capability(
        Path(plan["capability_prerequisites"]["image_generation"]["case_root"]),
        "image-generation",
    )
    viewing = verified_capability(
        Path(plan["capability_prerequisites"]["image_view"]["case_root"]),
        "image-view",
    )
    for name, verified in (("image_generation", generation), ("image_view", viewing)):
        recorded = plan["capability_prerequisites"][name]
        if recorded.get("proposal_id") != verified["proposal_id"] or recorded.get("closure_sha256") != verified["closure_sha256"]:
            raise PilotError(f"capability prerequisite drift: {name}")
    if generation["executable"] != viewing["executable"] or generation["executable"] != plan.get("executable"):
        raise PilotError("batch executable identity drift")
    if len(plan.get("items", [])) != ITEM_COUNT:
        raise PilotError("batch must contain exactly three items")
    items_root = Path(plan["paths"]["items_root"])
    if path_is_reparse(items_root) or not items_root.is_dir():
        raise PilotError("batch items root is missing or reparse-backed")
    expected_item_dirs = {Path(item["case_root"]).name for item in plan["items"]}
    actual_item_dirs = {path.name for path in items_root.iterdir()}
    if actual_item_dirs != expected_item_dirs:
        raise PilotError("batch items root contains missing or unexpected entries")
    for expected_index, item in enumerate(plan["items"], 1):
        if item.get("item_index") != expected_index or item.get("item_id") != ITEM_SPECS[expected_index - 1]["item_id"]:
            raise PilotError("batch item order or identity drift")
        item_root = Path(item["case_root"])
        _, item_plan = load_case(item_root)
        context = item_plan.get("proposal_context")
        expected_context = {
            "batch_id": plan["batch_id"],
            "item_id": item["item_id"],
            "item_index": expected_index,
            "item_count": ITEM_COUNT,
            "role": item["role"],
        }
        if context != expected_context or sha256_file(item_root / ITEM_PLAN_NAME) != item.get("plan_sha256"):
            raise PilotError("batch item proposal binding drift")
        if item_plan["executable"] != plan["executable"]:
            raise PilotError("batch item executable identity drift")
        if require_fresh_items:
            for name in ("dry_run_receipts", "receipts", "closure", "after_manifest"):
                if os.path.lexists(Path(item_plan["paths"][name])):
                    raise PilotError(f"batch item is not fresh: {item['item_id']}:{name}")
    validate_ledger_path(Path(plan["paths"]["daily_ledger"]), root)
    return marker, plan


def load_daily_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": DAILY_LEDGER_SCHEMA, "events": []}
    value = read_json_regular(path)
    if value.get("schema_version") != DAILY_LEDGER_SCHEMA or not isinstance(value.get("events"), list):
        raise PilotError("daily ledger schema is invalid")
    for event in value["events"]:
        if not isinstance(event, dict) or not isinstance(event.get("utc_day"), str):
            raise PilotError("daily ledger contains an invalid event")
    return value


def reserve_daily_item(plan: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    ledger_path = Path(plan["paths"]["daily_ledger"])
    lock = ledger_path.with_name(f"{ledger_path.name}.lock")
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise PilotError("daily ledger is locked by another controller") from exc
    try:
        ledger = load_daily_ledger(ledger_path)
        day = utc_day()
        today = [event for event in ledger["events"] if event.get("utc_day") == day]
        if len(today) >= plan["policy"]["daily_item_ceiling"]:
            raise PilotError("daily provider-use ceiling is exhausted")
        if any(
            event.get("batch_id") == plan["batch_id"] and event.get("item_id") == item["item_id"]
            for event in ledger["events"]
        ):
            raise PilotError("daily ledger already contains this batch item")
        event = {
            "utc_day": day,
            "attempted_at": utc_now(),
            "batch_id": plan["batch_id"],
            "item_id": item["item_id"],
            "item_index": item["item_index"],
        }
        ledger["events"].append(event)
        write_json_replace(ledger_path, ledger)
        return event
    finally:
        lock.rmdir()


def directory_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and not path_is_reparse(path):
            total += path.stat().st_size
    return total


def receipt_output_bytes(item_plan: dict[str, Any]) -> int:
    root = Path(item_plan["paths"]["receipts"])
    return sum(path.stat().st_size for path in root.iterdir() if path.is_file())


def run_launcher(command: list[str], timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=str(Path(command[1]).resolve().parents[3]),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PilotError(f"launcher controller timeout after {timeout}s") from exc
    return {
        "return_code": result.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "stdout_sha256": sha256_bytes(result.stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(result.stderr.encode("utf-8")),
        "stdout_bytes": len(result.stdout.encode("utf-8")),
        "stderr_bytes": len(result.stderr.encode("utf-8")),
    }


def execute_item(item: dict[str, Any], batch_plan: dict[str, Any], approval_reference: str) -> dict[str, Any]:
    item_root = Path(item["case_root"])
    _, item_plan = load_case(item_root)
    dry = run_launcher(item_plan["dry_run_command"], timeout=90)
    if dry["return_code"] != 0:
        raise PilotError(f"item {item['item_id']} dry run failed with return code {dry['return_code']}")
    live = run_launcher(
        item_plan["execute_command"],
        timeout=item_plan["policy"]["timeout_seconds"] + 90,
    )
    if live["return_code"] != 0:
        raise PilotError(f"item {item['item_id']} live run failed with return code {live['return_code']}")
    item_approval = f"{approval_reference}.item-{item['item_index']}"
    close_case(argparse.Namespace(
        case_root=item_root,
        approval_reference=item_approval,
        approved_plan_sha256=item["plan_sha256"],
    ))
    verified = verify_closed_case(item_root)
    summary = read_json_regular(Path(item_plan["paths"]["receipts"]) / "cairnspan-summary.json")
    return {
        "item_id": item["item_id"],
        "item_index": item["item_index"],
        "proposal_id": item["proposal_id"],
        "dry_run": dry,
        "live_run": live,
        "target_elapsed_seconds": summary.get("elapsed_seconds"),
        "receipt_output_bytes": receipt_output_bytes(item_plan),
        "closure_sha256": verified["closure_sha256"],
        "artifact": verified["result"].get("artifact"),
    }


def make_state(plan: dict[str, Any], approval_reference: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "batch_id": plan["batch_id"],
        "approval_reference": approval_reference,
        "approval_attestation": "operator-supplied-reference-not-independently-verifiable",
        "started_at": utc_now(),
        "last_stage": "prepared",
        "last_item_index": 0,
        "attempted_items": [],
        "completed_items": [],
        "aggregate_receipt_output_bytes": 0,
        "aggregate_target_elapsed_seconds": 0.0,
    }


def execute_batch(
    args: argparse.Namespace,
    *,
    item_executor: Callable[[dict[str, Any], dict[str, Any], str], dict[str, Any]] = execute_item,
) -> dict[str, Any]:
    if not APPROVAL_PATTERN.fullmatch(args.approval_reference):
        raise PilotError(f"--approval-reference must match {APPROVAL_PATTERN.pattern}")
    root = args.batch_root.resolve()
    _, plan = load_batch(root, require_fresh_items=True)
    plan_sha256 = sha256_file(root / PLAN_NAME)
    if args.approved_plan_sha256 != plan_sha256:
        raise PilotError("--approved-plan-sha256 does not match the immutable batch plan")
    state_path = root / STATE_NAME
    result_path = root / RESULT_NAME
    if os.path.lexists(state_path) or os.path.lexists(result_path):
        raise PilotError("batch execution cannot resume or overwrite prior state")
    state = make_state(plan, args.approval_reference)
    state["approved_plan_sha256"] = args.approved_plan_sha256
    write_json_fresh(state_path, state)
    started = time.monotonic()
    failed_item: dict[str, Any] | None = None
    failure: str | None = None
    try:
        for item in plan["items"]:
            if time.monotonic() - started > plan["policy"]["max_batch_seconds"]:
                raise PilotError("aggregate batch runtime ceiling reached before the next item")
            if directory_bytes(root) > plan["policy"]["max_disk_bytes"]:
                raise PilotError("aggregate batch disk ceiling reached before the next item")
            reservation = reserve_daily_item(plan, item)
            failed_item = item
            state["last_stage"] = "item-attempt-reserved"
            state["last_item_index"] = item["item_index"]
            state["attempted_items"].append({"item_id": item["item_id"], "reservation": reservation})
            write_json_replace(state_path, state)
            outcome = item_executor(item, plan, args.approval_reference)
            state["completed_items"].append(outcome)
            state["aggregate_receipt_output_bytes"] += int(outcome["receipt_output_bytes"])
            state["aggregate_target_elapsed_seconds"] += float(outcome.get("target_elapsed_seconds") or 0.0)
            state["last_stage"] = "item-closed"
            write_json_replace(state_path, state)
            failed_item = None
            if state["aggregate_receipt_output_bytes"] > plan["policy"]["max_batch_output_bytes"]:
                raise PilotError("aggregate batch output ceiling exceeded")
            if state["aggregate_target_elapsed_seconds"] > plan["policy"]["max_batch_seconds"]:
                raise PilotError("aggregate target runtime ceiling exceeded")
            if directory_bytes(root) > plan["policy"]["max_disk_bytes"]:
                raise PilotError("aggregate batch disk ceiling exceeded")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        failure = str(exc)

    elapsed = round(time.monotonic() - started, 3)
    state["status"] = "failed" if failure else "closed"
    state["last_stage"] = "failed" if failure else "closed"
    state["finished_at"] = utc_now()
    write_json_replace(state_path, state)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": state["status"],
        "batch_id": plan["batch_id"],
        "finished_at": state["finished_at"],
        "approval_reference": args.approval_reference,
        "approved_plan_sha256": args.approved_plan_sha256,
        "plan_sha256": plan_sha256,
        "state_sha256": sha256_file(state_path),
        "attempted_item_ids": [entry["item_id"] for entry in state["attempted_items"]],
        "completed_item_ids": [entry["item_id"] for entry in state["completed_items"]],
        "failed_item_id": failed_item["item_id"] if failed_item else None,
        "failure": failure,
        "aggregate_elapsed_seconds": elapsed,
        "aggregate_target_elapsed_seconds": state["aggregate_target_elapsed_seconds"],
        "aggregate_receipt_output_bytes": state["aggregate_receipt_output_bytes"],
        "aggregate_disk_bytes": directory_bytes(root),
        "product_integration": "not-run",
        "automatic_retries": 0,
    }
    write_json_fresh(result_path, result)
    return result


def verify_batch(root: Path) -> dict[str, Any]:
    _, plan = load_batch(root, require_fresh_items=False)
    state = read_json_regular(root / STATE_NAME)
    result = read_json_regular(root / RESULT_NAME)
    if state.get("batch_id") != plan["batch_id"] or result.get("batch_id") != plan["batch_id"]:
        raise PilotError("batch state/result identity mismatch")
    if result.get("state_sha256") != sha256_file(root / STATE_NAME):
        raise PilotError("batch state hash mismatch")
    if result.get("plan_sha256") != sha256_file(root / PLAN_NAME):
        raise PilotError("batch result plan hash mismatch")
    if result.get("approved_plan_sha256") != result.get("plan_sha256"):
        raise PilotError("batch approval is not bound to the terminal plan hash")
    if state.get("approved_plan_sha256") != result.get("approved_plan_sha256"):
        raise PilotError("batch state approval hash mismatch")
    attempted = result.get("attempted_item_ids")
    completed = result.get("completed_item_ids")
    if not isinstance(attempted, list) or not isinstance(completed, list):
        raise PilotError("batch result item lists are invalid")
    declared = [item["item_id"] for item in plan["items"]]
    if attempted != declared[:len(attempted)] or completed != declared[:len(completed)]:
        raise PilotError("batch attempted/completed order is not a declared prefix")
    if len(completed) > len(attempted):
        raise PilotError("batch completed more items than it attempted")
    state_attempted = [entry.get("item_id") for entry in state.get("attempted_items", [])]
    state_completed = [entry.get("item_id") for entry in state.get("completed_items", [])]
    if state_attempted != attempted or state_completed != completed:
        raise PilotError("batch state and result disagree on item order")
    for name in ("aggregate_target_elapsed_seconds", "aggregate_receipt_output_bytes"):
        if result.get(name) != state.get(name):
            raise PilotError(f"batch state and result disagree on {name}")
    if result.get("status") != state.get("status"):
        raise PilotError("batch state and result terminal statuses disagree")
    if result.get("product_integration") != "not-run" or result.get("automatic_retries") != 0:
        raise PilotError("batch result widened integration or retry policy")
    verified_items: list[dict[str, Any]] = []
    for item, outcome in zip(plan["items"][:len(completed)], state["completed_items"]):
        verified = verify_closed_case(Path(item["case_root"]))
        if verified.get("proposal_id") != item["proposal_id"]:
            raise PilotError("verified item closure has the wrong proposal identity")
        if verified.get("probe_name") != "image-generation" or verified.get("result", {}).get("capability") != "ok(image-generation)":
            raise PilotError("verified item closure lacks image-generation capability evidence")
        if verified.get("closure_sha256") != outcome.get("closure_sha256"):
            raise PilotError("verified item closure hash disagrees with batch state")
        if verified.get("result", {}).get("artifact", {}).get("sha256") != outcome.get("artifact", {}).get("sha256"):
            raise PilotError("verified item artifact hash disagrees with batch state")
        verified_items.append(verified)
    if result.get("status") == "closed":
        if attempted != declared or completed != declared or result.get("failed_item_id") is not None or result.get("failure") is not None:
            raise PilotError("closed batch does not contain all three ordered closures")
    elif result.get("status") == "failed":
        if not isinstance(result.get("failure"), str) or not result["failure"]:
            raise PilotError("failed batch lacks a failure reason")
        if len(completed) < len(attempted):
            if result.get("failed_item_id") != attempted[-1]:
                raise PilotError("failed batch does not identify the incomplete attempted item")
        elif result.get("failed_item_id") is not None:
            raise PilotError("batch-level failure incorrectly blames a completed item")
        failed_index = len(attempted)
        for item in plan["items"][failed_index:]:
            _, item_plan = load_case(Path(item["case_root"]))
            for name in ("dry_run_receipts", "receipts", "closure", "after_manifest"):
                if os.path.lexists(Path(item_plan["paths"][name])):
                    raise PilotError("a later batch item ran after the recorded failure")
    else:
        raise PilotError("batch result status is not terminal")
    ledger = load_daily_ledger(Path(plan["paths"]["daily_ledger"]))
    ledger_ids = [
        event.get("item_id") for event in ledger["events"]
        if event.get("batch_id") == plan["batch_id"]
    ]
    if ledger_ids != attempted:
        raise PilotError("daily ledger does not match attempted item order")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "verified",
        "batch_id": plan["batch_id"],
        "terminal_status": result["status"],
        "attempted_item_ids": attempted,
        "completed_item_ids": completed,
        "verified_item_closures": [item["closure_sha256"] for item in verified_items],
        "result_sha256": sha256_file(root / RESULT_NAME),
        "product_integration": "not-run",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--batch-root", type=Path, required=True)
    prepare.add_argument("--image-generation-case-root", type=Path, required=True)
    prepare.add_argument("--image-view-case-root", type=Path, required=True)
    prepare.add_argument("--daily-ledger", type=Path, required=True)
    prepare.add_argument("--max-batch-seconds", type=int, default=1800)
    prepare.add_argument("--max-batch-output-bytes", type=int, default=3_145_728)
    prepare.add_argument("--max-disk-bytes", type=int, default=30_000_000)
    prepare.add_argument("--daily-item-ceiling", type=int, default=ITEM_COUNT)
    prepare.add_argument("--retention-hours", type=int, default=168)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--batch-root", type=Path, required=True)
    execute.add_argument("--approval-reference", required=True)
    execute.add_argument("--approved-plan-sha256", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--batch-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "prepare":
            value = prepare_batch(args)
        elif args.action == "execute":
            value = execute_batch(args)
        else:
            value = verify_batch(args.batch_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value.get("status") not in {"error", "failed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
