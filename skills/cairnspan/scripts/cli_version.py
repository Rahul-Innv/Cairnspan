"""Bounded local target-CLI version probing for Cairnspan receipts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


MAX_VERSION_BYTES = 512


class VersionProbeError(ValueError):
    """Raised when a target CLI cannot provide one bounded version string."""


def probe_cli_version(executable: Path, cwd: Path, env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VersionProbeError(f"target CLI version probe failed: {exc}") from exc
    output = result.stdout.strip() or result.stderr.strip()
    if result.returncode != 0:
        raise VersionProbeError(f"target CLI version probe exited with {result.returncode}")
    if not output or len(output) > MAX_VERSION_BYTES:
        raise VersionProbeError("target CLI version output is empty or exceeds 512 bytes")
    try:
        version = output.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise VersionProbeError("target CLI version output is not strict UTF-8") from exc
    if any(ord(char) < 32 and char not in "\t" for char in version):
        raise VersionProbeError("target CLI version output contains control characters")
    normalized = " ".join(version.split())
    if not normalized:
        raise VersionProbeError("target CLI version output is empty")
    return normalized


def version_probe_env(source: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(source or os.environ)
    sensitive_fragments = ("API_KEY", "AUTH_TOKEN", "ACCESS_TOKEN", "REFRESH_TOKEN", "SECRET", "COOKIE")
    for name in list(env):
        if any(fragment in name.upper() for fragment in sensitive_fragments):
            env.pop(name, None)
    return env
