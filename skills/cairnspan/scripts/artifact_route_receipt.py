#!/usr/bin/env python3
"""Close a bounded Claude-design to Codex-image route from parent-owned evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from prepare_artifact_handoff import SpecError, build_prompt, validate_spec
from workspace_manifest import compare, read_manifest


SCHEMA_VERSION = "0.2"
STRONG_CONTAINMENT = {"job-object"}


class ArtifactRouteError(ValueError):
    """Raised when artifact-route evidence does not satisfy policy."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise ArtifactRouteError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_fresh(path: Path, value: dict[str, Any]) -> None:
    target = path.resolve(strict=False)
    if target.exists():
        raise ArtifactRouteError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()


def validate_success(summary: dict[str, Any], agent: str) -> None:
    if summary.get("status") != "succeeded" or summary.get("return_code") != 0:
        raise ArtifactRouteError(f"{agent} summary is not successful")
    if summary.get("target_agent") != agent:
        raise ArtifactRouteError(f"{agent} target identity does not match")
    if summary.get("descendant_cleanup_verified") is not True:
        raise ArtifactRouteError(f"{agent} descendant cleanup is not verified")
    if summary.get("containment") not in STRONG_CONTAINMENT:
        raise ArtifactRouteError(f"{agent} process containment is not verified")
    if not isinstance(summary.get("target_cli_version"), str) or not summary["target_cli_version"]:
        raise ArtifactRouteError(f"{agent} CLI version is not verified")
    if summary.get("run_depth") != 0 or summary.get("max_depth") != 1:
        raise ArtifactRouteError(f"{agent} route depth policy does not match")


def validate_prompt(summary: dict[str, Any], prompt: Path, label: str) -> None:
    if summary.get("prompt_sha256") != sha256(prompt):
        raise ArtifactRouteError(f"{label} prompt hash does not match")


def validate_identical_manifests(before_path: Path, after_path: Path) -> dict[str, str]:
    before = read_manifest(before_path)
    after = read_manifest(after_path)
    if before.get("strict") is not True or after.get("strict") is not True:
        raise ArtifactRouteError("design manifests must be strict")
    if before.get("root") != after.get("root"):
        raise ArtifactRouteError("design manifest roots differ")
    if compare(before, after):
        raise ArtifactRouteError("Claude design workspace changed")
    return {"status": "identical", "before_sha256": sha256(before_path), "after_sha256": sha256(after_path)}


def validate_claude(summary: dict[str, Any], expected_model: str, max_budget: Decimal) -> Decimal:
    if summary.get("requested_model") != expected_model:
        raise ArtifactRouteError("Claude requested model does not match")
    if summary.get("safe_mode") is not True or summary.get("strict_mcp_config") is not True:
        raise ArtifactRouteError("Claude isolation policy does not match")
    if summary.get("tools") != "" or summary.get("tool_use_count") != 0 or summary.get("mcp_tool_use_count") != 0:
        raise ArtifactRouteError("Claude design edge used tools")
    if summary.get("tool_names") not in ([], None):
        raise ArtifactRouteError("Claude design edge reports tool names")
    capabilities = summary.get("init_capabilities")
    if not isinstance(capabilities, dict) or capabilities.get("tools") != [] or capabilities.get("mcp_servers") != []:
        raise ArtifactRouteError("Claude initialized tools or MCP servers")
    try:
        cost = Decimal(str(summary.get("total_cost_usd")))
    except InvalidOperation as exc:
        raise ArtifactRouteError("Claude cost is invalid") from exc
    if cost < 0 or cost > max_budget:
        raise ArtifactRouteError("Claude cost exceeds route budget")
    usage = summary.get("usage", {})
    server_tools = usage.get("server_tool_use", {}) if isinstance(usage, dict) else {}
    if server_tools.get("web_search_requests", 0) != 0 or server_tools.get("web_fetch_requests", 0) != 0:
        raise ArtifactRouteError("Claude design edge used web tools")
    return cost


def close(args: argparse.Namespace) -> dict[str, Any]:
    design_summary = read_json(args.design_summary)
    producer_summary = read_json(args.producer_summary)
    manifest = read_json(args.artifact_manifest)
    validate_success(design_summary, "claude-code")
    validate_success(producer_summary, "codex")
    validate_prompt(design_summary, args.design_prompt, "Claude design")
    validate_prompt(producer_summary, args.generation_prompt, "Codex generation")

    try:
        budget = Decimal(args.max_claude_budget_usd)
        max_elapsed = Decimal(args.max_route_elapsed_seconds)
    except InvalidOperation as exc:
        raise ArtifactRouteError("route budget is invalid") from exc
    claude_cost = validate_claude(design_summary, args.claude_model, budget)
    elapsed = Decimal(str(design_summary.get("elapsed_seconds"))) + Decimal(str(producer_summary.get("elapsed_seconds")))
    if elapsed > max_elapsed:
        raise ArtifactRouteError("aggregate route elapsed time exceeds policy")

    spec = validate_spec(read_json(args.design_final))
    if args.producer_final.read_text(encoding="utf-8", errors="strict").strip() != args.producer_marker:
        raise ArtifactRouteError("Codex producer final marker does not match")
    if manifest.get("status") != "accepted" or manifest.get("final_disposition") != "accepted-for-human-review":
        raise ArtifactRouteError("typed artifact manifest is not accepted for review")
    if manifest.get("producer_run_id") != producer_summary.get("run_id"):
        raise ArtifactRouteError("artifact producer run id does not match")
    if manifest.get("producer_summary_sha256") != sha256(args.producer_summary):
        raise ArtifactRouteError("artifact producer summary hash does not match")
    if manifest.get("producer_cli_version") != producer_summary.get("target_cli_version"):
        raise ArtifactRouteError("artifact producer CLI version does not match")
    if manifest.get("generation_prompt_sha256") != sha256(args.generation_prompt):
        raise ArtifactRouteError("artifact generation prompt hash does not match")
    relative_path = manifest.get("relative_path")
    if not isinstance(relative_path, str):
        raise ArtifactRouteError("artifact relative path is missing")
    expected_generation_prompt = build_prompt(spec, relative_path)
    actual_generation_prompt = args.generation_prompt.read_text(encoding="utf-8", errors="strict")
    if actual_generation_prompt != expected_generation_prompt:
        raise ArtifactRouteError("artifact generation prompt is not the exact prompt derived from the validated design spec")
    artifact = args.staging_root / relative_path
    if not artifact.is_file() or sha256(artifact) != manifest.get("sha256"):
        raise ArtifactRouteError("reviewed artifact bytes do not match the typed manifest")
    if manifest.get("validation", {}).get("width") != spec["width"] or manifest.get("validation", {}).get("height") != spec["height"]:
        raise ArtifactRouteError("artifact dimensions do not match the design spec")
    if args.visual_review_status != "passed":
        raise ArtifactRouteError("visual review did not pass")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "closed",
        "route_type": "claude-design-to-codex-image",
        "disposition": "validated-awaiting-separate-human-integration-approval",
        "product_integration": "not-run",
        "visual_review": {
            "status": args.visual_review_status,
            "note": args.visual_review_note,
            "artifact_sha256": manifest["sha256"],
        },
        "design": {
            "run_id": design_summary["run_id"],
            "summary_sha256": sha256(args.design_summary),
            "spec_sha256": sha256(args.design_final),
            "workspace": validate_identical_manifests(args.design_before_manifest, args.design_after_manifest),
            "cost_usd": str(claude_cost),
            "containment": design_summary["containment"],
            "target_cli_version": design_summary["target_cli_version"],
        },
        "producer": {
            "run_id": producer_summary["run_id"],
            "summary_sha256": sha256(args.producer_summary),
            "artifact_manifest_sha256": sha256(args.artifact_manifest),
            "containment": producer_summary["containment"],
            "target_cli_version": producer_summary["target_cli_version"],
        },
        "aggregate_elapsed_seconds": str(elapsed),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design-summary", type=Path, required=True)
    parser.add_argument("--design-final", type=Path, required=True)
    parser.add_argument("--design-prompt", type=Path, required=True)
    parser.add_argument("--design-before-manifest", type=Path, required=True)
    parser.add_argument("--design-after-manifest", type=Path, required=True)
    parser.add_argument("--producer-summary", type=Path, required=True)
    parser.add_argument("--producer-final", type=Path, required=True)
    parser.add_argument("--generation-prompt", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--claude-model", default="claude-sonnet-5")
    parser.add_argument("--max-claude-budget-usd", default="0.05")
    parser.add_argument("--max-route-elapsed-seconds", default="300")
    parser.add_argument("--producer-marker", default="image-artifact-ready")
    parser.add_argument("--visual-review-status", choices=("passed", "failed"), required=True)
    parser.add_argument("--visual-review-note", required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        value = close(args)
        write_json_fresh(args.out, value)
    except (ArtifactRouteError, FileNotFoundError, InvalidOperation, json.JSONDecodeError, OSError, SpecError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"status": value["status"], "output": str(args.out.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
