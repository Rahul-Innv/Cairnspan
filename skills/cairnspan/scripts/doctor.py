"""Non-destructive environment checks for Cairnspan."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cli_version import VersionProbeError, probe_cli_version, version_probe_env


STATUS_ORDER = {"ok": 0, "warn": 1, "fail": 2}
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
MAX_HELP_BYTES = 64_000


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    message: str
    detail: str | None = None


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def has_path_separator(value: str) -> bool:
    return any(separator in value for separator in (os.sep, os.altsep) if separator)


def worst_status(checks: list[Check]) -> str:
    if not checks:
        return "ok"
    return max((check.status for check in checks), key=lambda status: STATUS_ORDER[status])


def resolve_executable(value: str) -> Path | None:
    if has_path_separator(value):
        path = Path(value).expanduser()
        return path.resolve() if path.is_file() else None
    resolved = shutil.which(value)
    if not resolved:
        return None
    resolved_path = Path(resolved).resolve()
    return resolved_path if resolved_path.is_file() else None


def check_python() -> Check:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info < (3, 10):
        return Check("python", "fail", "Python 3.10 or newer is recommended for Cairnspan.", version)
    return Check("python", "ok", "Python version is usable.", version)


def check_cwd(cwd: Path) -> Check:
    resolved = cwd.resolve()
    if not resolved.exists():
        return Check("cwd", "fail", "Target workspace does not exist.", str(resolved))
    if not resolved.is_dir():
        return Check("cwd", "fail", "Target workspace is not a directory.", str(resolved))
    return Check("cwd", "ok", "Target workspace exists.", str(resolved))


def check_out_dir(cwd: Path, out_dir: Path | None) -> Check:
    resolved_cwd = cwd.resolve()
    resolved_out = (out_dir or (resolved_cwd / ".cairnspan" / "doctor-check")).resolve()
    if resolved_out.exists() and not resolved_out.is_dir():
        return Check("out_dir", "fail", "Output path exists and is not a directory.", str(resolved_out))
    if not path_is_within(resolved_out, resolved_cwd):
        return Check("out_dir", "warn", "Output directory resolves outside the target workspace.", str(resolved_out))
    if resolved_out.exists() and any(resolved_out.iterdir()):
        return Check("out_dir", "warn", "Output directory already exists and is not empty.", str(resolved_out))
    return Check("out_dir", "ok", "Output directory policy looks safe.", str(resolved_out))


def check_executable(name: str, value: str, cwd: Path) -> Check:
    resolved = resolve_executable(value)
    if resolved is None:
        return Check(name, "fail", f"{name} executable was not found.", value)
    lowered = str(resolved).lower()
    if name == "codex_bin" and "windowsapps" in lowered:
        return Check(
            name,
            "warn",
            "Codex resolves to WindowsApps; unattended subprocess launch may fail with Access is denied.",
            str(resolved),
        )
    if not has_path_separator(value) and path_is_within(resolved, cwd):
        return Check(
            name,
            "fail",
            f"{name} command-name resolution selected an executable inside the target workspace.",
            str(resolved),
        )
    if not has_path_separator(value) and resolved.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        return Check(
            name,
            "warn",
            f"{name} resolves to a shell wrapper; prefer an explicit trusted native executable path.",
            str(resolved),
        )
    return Check(name, "ok", f"{name} executable resolved.", str(resolved))


def check_cli_version(agent: str, value: str, cwd: Path) -> Check:
    name = f"{agent}_version"
    resolved = resolve_executable(value)
    if resolved is None:
        return Check(
            name,
            "warn",
            f"{agent.title()} version could not be inspected because the executable is unavailable.",
            "unknown(runtime_unverified)",
        )
    try:
        version = probe_cli_version(
            resolved,
            cwd if cwd.is_dir() else resolved.parent,
            version_probe_env(),
        )
    except VersionProbeError as exc:
        return Check(
            name,
            "warn",
            f"{agent.title()} version probe did not produce a bounded version string: {exc}",
            "unknown(runtime_unverified)",
        )
    return Check(name, "ok", f"{agent.title()} version probe succeeded.", version)


def probe_cli_help(agent: str, executable: Path, cwd: Path) -> tuple[str | None, str | None]:
    command = [str(executable), "exec", "--help"] if agent == "codex" else [str(executable), "--help"]
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd if cwd.is_dir() else executable.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
            env=version_probe_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"help_probe_failed:{type(exc).__name__}"
    output = result.stdout + result.stderr
    if result.returncode != 0:
        return None, f"help_probe_exit_{result.returncode}"
    if not output or len(output) > MAX_HELP_BYTES:
        return None, "help_output_empty_or_oversized"
    try:
        return output.decode("utf-8", errors="strict"), None
    except UnicodeDecodeError:
        return None, "help_output_not_utf8"


def check_typed_capabilities(agent: str, value: str, cwd: Path) -> list[Check]:
    model_name = f"{agent}_typed_model"
    effort_name = f"{agent}_typed_effort"
    resolved = resolve_executable(value)
    if resolved is None:
        return [
            Check(
                model_name,
                "warn",
                f"{agent.title()} typed model support could not be inspected.",
                "unknown(runtime_unverified)",
            ),
            Check(
                effort_name,
                "warn",
                f"{agent.title()} typed effort support could not be inspected.",
                "unknown(runtime_unverified)",
            ),
        ]

    help_text, failure = probe_cli_help(agent, resolved, cwd)
    if help_text is None:
        reason = failure or "help_probe_failed"
        return [
            Check(
                model_name,
                "warn",
                f"{agent.title()} typed model support could not be proved by the bounded help probe ({reason}).",
                "unknown(runtime_unverified)",
            ),
            Check(
                effort_name,
                "warn",
                f"{agent.title()} typed effort support could not be proved by the bounded help probe ({reason}).",
                "unknown(runtime_unverified)",
            ),
        ]

    lowered = help_text.casefold()
    model_advertised = "--model" in lowered
    model_check = Check(
        model_name,
        "ok" if model_advertised else "warn",
        (
            f"{agent.title()} advertises the launcher-owned typed model option."
            if model_advertised
            else f"{agent.title()} does not advertise the launcher-owned typed model option."
        ),
        "advertised(--model)" if model_advertised else "missing(--model)",
    )

    effort_flag = "model_reasoning_effort" if agent == "codex" else "--effort"
    help_lines = help_text.splitlines()
    effort_indexes = [
        index for index, line in enumerate(help_lines) if effort_flag in line.casefold()
    ]
    effort_advertised = bool(effort_indexes)
    effort_surface = " ".join(
        line.casefold()
        for index in effort_indexes
        for line in help_lines[index : index + 3]
    )
    advertised_values = [
        value
        for value in EFFORT_LEVELS
        if re.search(rf"(?<![a-z0-9_]){re.escape(value)}(?![a-z0-9_])", effort_surface)
    ]
    all_values_advertised = advertised_values == list(EFFORT_LEVELS)
    if effort_advertised and all_values_advertised:
        effort_check = Check(
            effort_name,
            "ok",
            f"{agent.title()} advertises the typed effort transport and every accepted value.",
            f"advertised({','.join(EFFORT_LEVELS)})",
        )
    elif effort_advertised:
        effort_check = Check(
            effort_name,
            "warn",
            f"{agent.title()} advertises the typed effort transport, but not every accepted value.",
            "unknown(accepted_values_unverified)",
        )
    else:
        effort_check = Check(
            effort_name,
            "warn",
            f"{agent.title()} does not advertise the launcher-owned typed effort transport.",
            f"missing({effort_flag})",
        )
    return [model_check, effort_check]


def check_codex_image_tools(value: str, cwd: Path) -> Check:
    resolved = resolve_executable(value)
    if resolved is None:
        return Check(
            "codex_image_tools", "warn",
            "Codex image-tool capability could not be inspected because the executable is unavailable.",
            "missing(codex_executable)",
        )
    try:
        result = subprocess.run(
            [str(resolved), "features", "list"],
            cwd=str(cwd if cwd.is_dir() else resolved.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            env=version_probe_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check(
            "codex_image_tools", "warn",
            "Codex image-tool feature inspection could not run.",
            f"missing(feature_probe_failed:{type(exc).__name__})",
        )
    if result.returncode != 0:
        return Check(
            "codex_image_tools", "warn",
            "Codex image-tool feature inspection returned a nonzero status.",
            f"missing(feature_probe_exit_{result.returncode})",
        )

    flags: dict[str, bool] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in {"code_mode_host", "image_generation"}:
            flags[parts[0]] = parts[-1].casefold() == "true"
    missing = [name for name in ("code_mode_host", "image_generation") if not flags.get(name, False)]
    if missing:
        return Check(
            "codex_image_tools", "warn",
            "Codex does not advertise every required image-tool feature.",
            f"missing({'+'.join(missing)})",
        )
    return Check(
        "codex_image_tools", "warn",
        "Codex advertises image-tool features, but offline inspection cannot prove the runtime host starts.",
        "unknown(runtime_unverified)",
    )


def check_gitignore(root: Path) -> Check:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return Check("gitignore", "warn", ".gitignore is missing; runtime artifacts may be committed.", str(gitignore))
    ignored = False
    for raw_line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        normalized = line[1:] if negated else line
        normalized = normalized.lstrip("/")
        if normalized in {".cairnspan", ".cairnspan/", ".cairnspan/**"}:
            ignored = not negated
    if not ignored:
        return Check("gitignore", "warn", ".cairnspan/ is not ignored.", str(gitignore))
    return Check("gitignore", "ok", "Runtime artifact directory is ignored.", str(gitignore))


def run_checks(args: argparse.Namespace) -> list[Check]:
    cwd = args.cwd.resolve()
    checks = [
        check_python(),
        check_cwd(args.cwd),
        check_out_dir(cwd, args.out_dir),
        check_executable("codex_bin", args.codex_bin, cwd),
    ]
    checks.extend(check_typed_capabilities("codex", args.codex_bin, cwd))
    checks.extend(
        [
            check_cli_version("codex", args.codex_bin, cwd),
            check_codex_image_tools(args.codex_bin, cwd),
            check_executable("claude_bin", args.claude_bin, cwd),
        ]
    )
    checks.extend(check_typed_capabilities("claude", args.claude_bin, cwd))
    checks.extend(
        [
            check_cli_version("claude", args.claude_bin, cwd),
            check_gitignore(cwd),
        ]
    )
    return checks


def make_payload(checks: list[Check]) -> dict[str, Any]:
    return {
        "status": worst_status(checks),
        "checks": [asdict(check) for check in checks],
    }


def print_text(checks: list[Check]) -> None:
    payload = make_payload(checks)
    print(f"cairnspan-doctor-{payload['status']}")
    for check in checks:
        detail = f" ({check.detail})" if check.detail else ""
        print(f"{check.status.upper()} {check.name}: {check.message}{detail}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run non-destructive Cairnspan setup checks.")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="Target workspace to inspect")
    parser.add_argument("--out-dir", type=Path, help="Optional output directory policy check")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable path or PATH command name")
    parser.add_argument("--claude-bin", default="claude", help="Claude executable path or PATH command name")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checks = run_checks(args)
    payload = make_payload(checks)
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_text(checks)
    return 1 if payload["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
