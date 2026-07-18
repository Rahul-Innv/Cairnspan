"""Console dispatcher for the Cairnspan session tools.

Each tool is a standalone, stdlib-only script shipped in
``cairnspan.scripts``. The dispatcher executes the selected script in a
child interpreter exactly as it would run from a checkout, so the scripts'
documented command-line contracts, receipts, and fail-closed behavior are
unchanged. Run ``cairnspan <tool> --help`` for a tool's own options.
"""

from __future__ import annotations

import subprocess
import sys
from importlib.resources import as_file, files

from . import __version__

#: console tool name -> module filename (without ``.py``) in cairnspan.scripts
TOOLS: dict[str, str] = {
    "launch-codex": "start_codex_session",
    "launch-claude": "start_claude_session",
    "run-two-way": "run_two_way_route",
    "doctor": "doctor",
    "scan-artifacts": "scan_artifacts",
    "release-readiness": "release_readiness",
    "mailbox": "mailbox",
    "mailbox-route-receipt": "mailbox_route_receipt",
    "workspace-manifest": "workspace_manifest",
    "hostile-write-case": "hostile_write_case",
    "synthetic-probe-case": "synthetic_probe_case",
    "synthetic-image-pilot": "synthetic_image_pilot",
    "prepare-tracked-snapshot": "prepare_tracked_snapshot",
    "prepare-critique-handoff": "prepare_critique_handoff",
    "critique-route-receipt": "critique_route_receipt",
    "prepare-artifact-handoff": "prepare_artifact_handoff",
    "artifact-manifest": "artifact_manifest",
    "artifact-route-receipt": "artifact_route_receipt",
}


def usage() -> str:
    lines = [
        f"cairnspan {__version__}",
        "",
        "Usage: cairnspan <tool> [tool options...]",
        "       cairnspan <tool> --help",
        "",
        "Tools:",
    ]
    lines.extend(f"  {name}" for name in sorted(TOOLS))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(usage())
        return 0
    if args[0] == "--version":
        print(__version__)
        return 0
    tool = args[0]
    module = TOOLS.get(tool)
    if module is None:
        print(f"cairnspan: unknown tool {tool!r}", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 2
    resource = files("cairnspan.scripts").joinpath(f"{module}.py")
    with as_file(resource) as script_path:
        completed = subprocess.run([sys.executable, str(script_path), *args[1:]], check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
