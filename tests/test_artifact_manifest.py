from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cairnspan" / "scripts"
SCRIPT = SCRIPTS / "artifact_manifest.py"
sys.path.insert(0, str(SCRIPTS))

from workspace_manifest import snapshot  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(data, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def make_png(path: Path, *, metadata: bool = False) -> None:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)
    scanline = b"\x00\xff\x00\x00\x00\xff\x00"
    parts = [signature, chunk(b"IHDR", ihdr)]
    if metadata:
        parts.append(chunk(b"tEXt", b"Comment\x00instruction-like metadata"))
    parts.extend([chunk(b"IDAT", zlib.compress(scanline)), chunk(b"IEND", b"")])
    path.write_bytes(b"".join(parts))


class ArtifactManifestTest(unittest.TestCase):
    def make_fixture(self, root: Path, *, metadata: bool = False, extra: bool = False) -> dict[str, Path]:
        staging = root / "staging"
        output_dir = staging / "output"
        output_dir.mkdir(parents=True)
        before = root / "before.json"
        write_json(before, snapshot(staging, strict=True))
        artifact = output_dir / "probe.png"
        make_png(artifact, metadata=metadata)
        if extra:
            (staging / "unexpected.txt").write_text("bad", encoding="utf-8")
        after = root / "after.json"
        write_json(after, snapshot(staging, strict=True))
        producer_summary = root / "producer.json"
        write_json(producer_summary, {
            "status": "succeeded", "return_code": 0, "descendant_cleanup_verified": True,
            "containment": "job-object", "target_cli_version": "fake-codex 1.0",
            "target_agent": "codex", "run_id": "producer-run",
        })
        producer_executable = root / "codex.exe"
        producer_executable.write_bytes(b"synthetic executable fixture")
        generation_prompt = root / "prompt.txt"
        generation_prompt.write_text("Generate one synthetic public probe image.", encoding="utf-8")
        return locals()

    def run_validator(self, fixture: dict[str, Path], out: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable, str(SCRIPT), "--staging-root", str(fixture["staging"]),
            "--artifact", str(fixture["artifact"]), "--before-manifest", str(fixture["before"]),
            "--after-manifest", str(fixture["after"]), "--producer-summary", str(fixture["producer_summary"]),
            "--producer-executable", str(fixture["producer_executable"]),
            "--generation-prompt", str(fixture["generation_prompt"]),
            "--artifact-id", "artifact-1", "--route-id", "route-1", "--role", "probe",
            "--provenance-note", "Synthetic test image with no references.", "--out", str(out), *extra,
        ]
        return subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, check=False)

    def test_accepts_valid_static_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            out = root / "manifest.json"

            result = self.run_validator(fixture, out)

            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "accepted")
            self.assertEqual(value["validation"]["width"], 2)
            self.assertEqual(value["validation"]["frame_count"], 1)

    def test_accepts_root_metadata_change_caused_by_declared_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            after = json.loads(fixture["after"].read_text(encoding="utf-8"))
            after["root_metadata"]["mtime_ns"] += 1
            write_json(fixture["after"], after)
            out = root / "manifest.json"

            result = self.run_validator(fixture, out)

            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("<manifest:root_metadata>", value["validation"]["staging_manifest"]["changed_paths"])

    def test_rejects_metadata_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root, metadata=True)
            out = root / "manifest.json"

            result = self.run_validator(fixture, out)

            self.assertEqual(result.returncode, 2)
            self.assertIn("ancillary chunks", result.stderr)
            self.assertFalse(out.exists())

    def test_rejects_unexpected_staging_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root, extra=True)
            out = root / "manifest.json"

            result = self.run_validator(fixture, out)

            self.assertEqual(result.returncode, 2)
            self.assertIn("unexpected staging changes", result.stderr)

    def test_rejects_corrupt_png_crc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            raw = bytearray(fixture["artifact"].read_bytes())
            raw[-8] ^= 1
            fixture["artifact"].write_bytes(raw)
            write_json(fixture["after"], snapshot(fixture["staging"], strict=True))
            out = root / "manifest.json"

            result = self.run_validator(fixture, out)

            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())

    def test_rejects_png_inflate_bomb_before_unbounded_decode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            inflated = b"\x00" * 2_000_000
            fixture["artifact"].write_bytes(
                b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(inflated)) + chunk(b"IEND", b"")
            )
            write_json(fixture["after"], snapshot(fixture["staging"], strict=True))

            result = self.run_validator(fixture, root / "manifest.json")

            self.assertEqual(result.returncode, 2)
            self.assertIn("exceeds the declared scanline size", result.stderr)

    def test_rejects_unknown_ancillary_chunk_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            raw = fixture["artifact"].read_bytes()
            insertion = raw.rfind(chunk(b"IEND", b""))
            fixture["artifact"].write_bytes(raw[:insertion] + chunk(b"vpAg", b"opaque") + raw[insertion:])
            write_json(fixture["after"], snapshot(fixture["staging"], strict=True))

            result = self.run_validator(fixture, root / "manifest.json")

            self.assertEqual(result.returncode, 2)
            self.assertIn("ancillary chunks", result.stderr)

    def test_accepts_strict_standard_display_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            raw = fixture["artifact"].read_bytes()
            ihdr_end = len(b"\x89PNG\r\n\x1a\n") + 12 + 13
            display = (
                chunk(b"gAMA", struct.pack(">I", 45455))
                + chunk(b"sRGB", b"\x00")
                + chunk(b"pHYs", struct.pack(">IIB", 3780, 3780, 1))
            )
            fixture["artifact"].write_bytes(raw[:ihdr_end] + display + raw[ihdr_end:])
            write_json(fixture["after"], snapshot(fixture["staging"], strict=True))
            out = root / "manifest.json"

            result = self.run_validator(fixture, out)

            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(value["validation"]["retained_ancillary_chunks"], ["gAMA", "pHYs", "sRGB"])

    def test_rejects_malformed_standard_display_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            raw = fixture["artifact"].read_bytes()
            ihdr_end = len(b"\x89PNG\r\n\x1a\n") + 12 + 13
            fixture["artifact"].write_bytes(raw[:ihdr_end] + chunk(b"sRGB", b"\x09") + raw[ihdr_end:])
            write_json(fixture["after"], snapshot(fixture["staging"], strict=True))

            result = self.run_validator(fixture, root / "manifest.json")

            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid sRGB", result.stderr)

    def test_rejects_apng_control_even_when_one_frame(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            raw = fixture["artifact"].read_bytes()
            ihdr_end = len(b"\x89PNG\r\n\x1a\n") + 12 + 13
            fixture["artifact"].write_bytes(
                raw[:ihdr_end] + chunk(b"acTL", struct.pack(">II", 1, 0)) + raw[ihdr_end:]
            )
            write_json(fixture["after"], snapshot(fixture["staging"], strict=True))

            result = self.run_validator(fixture, root / "manifest.json")

            self.assertEqual(result.returncode, 2)
            self.assertIn("APNG", result.stderr)

    def test_rejects_malformed_core_palette_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.make_fixture(root)
            raw = fixture["artifact"].read_bytes()
            ihdr_end = len(b"\x89PNG\r\n\x1a\n") + 12 + 13
            fixture["artifact"].write_bytes(raw[:ihdr_end] + chunk(b"PLTE", b"hide") + raw[ihdr_end:])
            write_json(fixture["after"], snapshot(fixture["staging"], strict=True))

            result = self.run_validator(fixture, root / "manifest.json")

            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid PLTE", result.stderr)


if __name__ == "__main__":
    unittest.main()
