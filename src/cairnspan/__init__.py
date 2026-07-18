"""Cairnspan: bounded, receipt-producing delegation between local coding agents.

Cairnspan launches the user's already-authenticated local agent clients
(Claude Code, Codex) for scoped, parent-controlled handoffs and records
structured receipts. It does not broker OAuth tokens or wrap raw model APIs.

The session tooling ships as standalone stdlib-only scripts under
``cairnspan.scripts``. Use the ``cairnspan`` console command (see
:mod:`cairnspan.cli`) or run the scripts directly with ``python``.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
