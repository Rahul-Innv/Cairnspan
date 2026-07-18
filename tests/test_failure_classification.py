from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str) -> ModuleType:
    module_name = f"cairnspan_{name}"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FailureClassificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.codex = load_script("start_codex_session")
        cls.claude = load_script("start_claude_session")

    def test_rate_limit_signals_are_classified(self) -> None:
        self.assertEqual(self.codex.classify_failure(1, "HTTP 429: rate limit exceeded")[0], "rate_limit")
        parsed = self.claude.ParsedEvents(is_error=True, api_error_status=429)
        self.assertEqual(self.claude.classify_failure(1, "", parsed)[0], "rate_limit")

    def test_quota_signals_are_classified(self) -> None:
        self.assertEqual(self.codex.classify_failure(1, "usage quota exhausted")[0], "quota")
        self.assertEqual(self.claude.classify_failure(1, "insufficient credits")[0], "quota")

    def test_native_crash_signals_are_classified(self) -> None:
        self.assertEqual(self.codex.classify_failure(-11, "")[0], "crash")
        self.assertEqual(self.claude.classify_failure(0xC0000005, "access violation")[0], "crash")


if __name__ == "__main__":
    unittest.main()
