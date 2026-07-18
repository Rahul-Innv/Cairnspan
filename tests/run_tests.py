from __future__ import annotations

import argparse
import sys
import unittest
from collections.abc import Iterator
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
PROCESS_INTEGRATION_MODULES = {
    "test_hostile_write_case",
    "test_hostile_write_profiles",
    "test_start_claude_session",
    "test_start_codex_session",
    "test_two_way_route",
}


def iter_cases(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_cases(item)
        else:
            yield item


def load_group(group: str) -> unittest.TestSuite:
    discovered = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    if group == "full":
        return discovered
    cases = [
        case
        for case in iter_cases(discovered)
        if case.__class__.__module__.rsplit(".", 1)[-1] not in PROCESS_INTEGRATION_MODULES
    ]
    return unittest.TestSuite(cases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the fast deterministic tier or the complete Cairnspan regression gate."
    )
    parser.add_argument("group", choices=("fast", "full"))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    suite = load_group(args.group)
    print(
        f"cairnspan-test-group={args.group} tests={suite.countTestCases()}",
        flush=True,
    )
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
