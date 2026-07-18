#!/usr/bin/env python3
"""Validate one static PNG and emit a parent-owned typed artifact manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from workspace_manifest import compare, is_reparse_point, read_manifest


SCHEMA_VERSION = "0.3"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
ROLE_VALUES = {"hero", "product", "texture", "reference", "social-card", "probe"}
CORE_CHUNKS = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
APNG_CHUNKS = {b"acTL", b"fcTL", b"fdAT"}
SAFE_DISPLAY_CHUNKS = {b"gAMA", b"pHYs", b"sRGB"}
STRONG_CONTAINMENT = {"job-object"}
COLOR_MODES = {0: "grayscale", 2: "rgb", 3: "palette", 4: "grayscale-alpha", 6: "rgba"}
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL", "CLOCK$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class ArtifactError(ValueError):
    """Raised when an artifact cannot enter the typed route."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise ArtifactError(f"expected one JSON object: {path.name}")
    return value


def write_json_fresh(path: Path, value: dict[str, Any]) -> None:
    target = path.resolve(strict=False)
    if target.exists():
        raise ArtifactError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with temp.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, target)


def validate_id(value: str, label: str) -> None:
    if not ID_PATTERN.fullmatch(value):
        raise ArtifactError(f"{label} must match {ID_PATTERN.pattern}")


def validate_relative_path(path: Path, root: Path) -> tuple[Path, str]:
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ArtifactError("artifact escapes staging root") from exc
    normalized = PurePosixPath(relative.as_posix())
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise ArtifactError("artifact path is not a normalized relative path")
    for part in normalized.parts:
        if ":" in part or part.split(".", 1)[0].upper() in WINDOWS_RESERVED:
            raise ArtifactError("artifact path contains an unsafe Windows name")
    if is_reparse_point(root) or is_reparse_point(path):
        raise ArtifactError("staging root and artifact must not be links or reparse points")
    if not resolved.is_file() or resolved.stat().st_nlink != 1:
        raise ArtifactError("artifact must be one regular non-hardlinked file")
    return resolved, normalized.as_posix()


def inspect_png(path: Path, *, max_width: int, max_height: int, max_pixels: int, allow_metadata: bool) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise ArtifactError("artifact does not have a PNG signature")
    offset = len(PNG_SIGNATURE)
    ihdr: tuple[int, int, int, int, int] | None = None
    idat = bytearray()
    metadata: list[str] = []
    retained_ancillary: list[str] = []
    saw_iend = False
    saw_plte = False
    saw_idat = False
    idat_ended = False
    chunk_index = 0
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ArtifactError("PNG chunk header is truncated")
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        chunk_type = raw[offset + 4:offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(raw):
            raise ArtifactError("PNG chunk payload is truncated")
        data = raw[data_start:data_end]
        expected_crc = struct.unpack(">I", raw[data_end:crc_end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(data, actual_crc) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ArtifactError(f"PNG chunk CRC mismatch: {chunk_type.decode('ascii', 'replace')}")
        if chunk_type == b"IHDR":
            if chunk_index != 0 or ihdr is not None or length != 13:
                raise ArtifactError("PNG must contain one valid IHDR")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", data)
            if compression != 0 or filter_method != 0 or interlace != 0:
                raise ArtifactError("only non-interlaced standard-compression PNG is supported")
            if bit_depth != 8 or color_type not in COLOR_MODES:
                raise ArtifactError("only 8-bit supported PNG color modes are accepted")
            ihdr = (width, height, bit_depth, color_type, interlace)
        elif chunk_type == b"PLTE":
            if ihdr is None or saw_plte or saw_idat or length == 0 or length > 768 or length % 3:
                raise ArtifactError("PNG contains an invalid PLTE chunk")
            if ihdr[3] in {0, 4}:
                raise ArtifactError("PNG color mode does not permit PLTE")
            saw_plte = True
        elif chunk_type == b"IDAT":
            if ihdr is None or idat_ended:
                raise ArtifactError("PNG IDAT chunks are not in one valid sequence")
            if ihdr[3] == 3 and not saw_plte:
                raise ArtifactError("palette PNG is missing PLTE before IDAT")
            saw_idat = True
            idat.extend(data)
        elif chunk_type in APNG_CHUNKS:
            raise ArtifactError("APNG chunks are not allowed")
        elif chunk_type in SAFE_DISPLAY_CHUNKS:
            if ihdr is None or saw_idat:
                raise ArtifactError("PNG display chunk is not before image data")
            if chunk_type == b"gAMA":
                if length != 4 or struct.unpack(">I", data)[0] == 0:
                    raise ArtifactError("PNG contains an invalid gAMA chunk")
            elif chunk_type == b"pHYs":
                if length != 9 or data[8] not in {0, 1}:
                    raise ArtifactError("PNG contains an invalid pHYs chunk")
            elif length != 1 or data[0] > 3:
                raise ArtifactError("PNG contains an invalid sRGB chunk")
            retained_ancillary.append(chunk_type.decode("ascii"))
        elif chunk_type == b"IEND":
            if length != 0 or not saw_idat:
                raise ArtifactError("invalid PNG IEND")
            saw_iend = True
            offset = crc_end
            break
        elif chunk_type not in CORE_CHUNKS:
            try:
                chunk_name = chunk_type.decode("ascii", errors="strict")
            except UnicodeDecodeError as exc:
                raise ArtifactError("PNG chunk type is not ASCII") from exc
            if not (chunk_type[0] & 0x20):
                raise ArtifactError(f"unsupported critical PNG chunk: {chunk_name}")
            metadata.append(chunk_name)
        if saw_idat and chunk_type not in {b"IDAT", b"IEND"}:
            idat_ended = True
        offset = crc_end
        chunk_index += 1
    if not saw_iend or offset != len(raw) or ihdr is None or not idat:
        raise ArtifactError("PNG structure is incomplete or has trailing bytes")
    width, height, bit_depth, color_type, _ = ihdr
    pixels = width * height
    if width <= 0 or height <= 0 or width > max_width or height > max_height or pixels > max_pixels:
        raise ArtifactError("PNG dimensions exceed route policy")
    if metadata and not allow_metadata:
        raise ArtifactError(f"PNG ancillary chunks are not allowed: {', '.join(sorted(set(metadata)))}")
    row_bytes = math.ceil(width * CHANNELS[color_type] * bit_depth / 8)
    expected_decoded = height * (row_bytes + 1)
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(bytes(idat), expected_decoded + 1)
        if len(decoded) > expected_decoded or decompressor.unconsumed_tail:
            raise ArtifactError("PNG image data exceeds the declared scanline size")
        decoded += decompressor.flush()
    except zlib.error as exc:
        raise ArtifactError("PNG image data does not fully decompress") from exc
    if not decompressor.eof or decompressor.unused_data or len(decoded) != expected_decoded:
        raise ArtifactError("PNG decompressed scanline length is inconsistent with IHDR")
    for row in range(height):
        if decoded[row * (row_bytes + 1)] > 4:
            raise ArtifactError("PNG contains an invalid scanline filter")
    return {
        "detected_media_type": "image/png",
        "file_signature_hex": PNG_SIGNATURE.hex(),
        "width": width,
        "height": height,
        "pixel_count": pixels,
        "bit_depth": bit_depth,
        "color_mode": COLOR_MODES[color_type],
        "frame_count": 1,
        "metadata_chunks": sorted(set(metadata)),
        "retained_ancillary_chunks": sorted(set(retained_ancillary)),
        "decoder_validation": "crc-and-bounded-zlib-scanline-validation",
    }


def validate_manifest_delta(before_path: Path, after_path: Path, artifact_relative: str) -> dict[str, Any]:
    before = read_manifest(before_path)
    after = read_manifest(after_path)
    if before.get("strict") is not True or after.get("strict") is not True or before.get("root") != after.get("root"):
        raise ArtifactError("staging manifests must be strict and use the same root")
    differences = compare(before, after)
    parent = str(PurePosixPath(artifact_relative).parent)
    expected = {artifact_relative}
    if parent != ".":
        expected.add(parent)
    changed = {item["path"] for item in differences}
    allowed = expected | {"<manifest:root_metadata>"}
    if not expected.issubset(changed) or not changed.issubset(allowed):
        raise ArtifactError(f"unexpected staging changes: {sorted(changed)}")
    return {
        "status": "expected-change",
        "changed_paths": sorted(changed),
        "before_sha256": sha256(before_path),
        "after_sha256": sha256(after_path),
    }


def validate(args: argparse.Namespace) -> dict[str, Any]:
    validate_id(args.artifact_id, "artifact id")
    validate_id(args.route_id, "route id")
    if args.role not in ROLE_VALUES:
        raise ArtifactError(f"role must be one of: {', '.join(sorted(ROLE_VALUES))}")
    artifact, relative = validate_relative_path(args.artifact, args.staging_root)
    size = artifact.stat().st_size
    if size <= 0 or size > args.max_bytes:
        raise ArtifactError("artifact byte length exceeds route policy")
    producer = read_json(args.producer_summary)
    if producer.get("status") != "succeeded" or producer.get("return_code") != 0:
        raise ArtifactError("producer summary is not successful")
    if producer.get("descendant_cleanup_verified") is not True:
        raise ArtifactError("producer process cleanup is not verified")
    if producer.get("containment") not in STRONG_CONTAINMENT:
        raise ArtifactError("producer process containment is not verified")
    if not isinstance(producer.get("target_cli_version"), str) or not producer["target_cli_version"]:
        raise ArtifactError("producer CLI version is not verified")
    image = inspect_png(
        artifact,
        max_width=args.max_width,
        max_height=args.max_height,
        max_pixels=args.max_pixels,
        allow_metadata=args.allow_metadata,
    )
    manifest_delta = validate_manifest_delta(args.before_manifest, args.after_manifest, relative)
    executable = args.producer_executable.resolve(strict=True)
    if not executable.is_file():
        raise ArtifactError("producer executable is not a file")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "accepted",
        "artifact_id": args.artifact_id,
        "route_id": args.route_id,
        "created_at": utc_now(),
        "producer_adapter": producer.get("target_agent"),
        "producer_run_id": producer.get("run_id"),
        "producer_containment": producer.get("containment"),
        "producer_cli_version": producer.get("target_cli_version"),
        "producer_summary_sha256": sha256(args.producer_summary),
        "producer_executable_sha256": sha256(executable),
        "relative_path": relative,
        "sha256": sha256(artifact),
        "byte_length": size,
        "artifact_role": args.role,
        "generation_prompt_sha256": sha256(args.generation_prompt),
        "input_reference_hashes": [],
        "policy_version": SCHEMA_VERSION,
        "validation": {**image, "staging_manifest": manifest_delta},
        "provenance_rights_note": args.provenance_note,
        "final_disposition": "accepted-for-human-review",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--before-manifest", type=Path, required=True)
    parser.add_argument("--after-manifest", type=Path, required=True)
    parser.add_argument("--producer-summary", type=Path, required=True)
    parser.add_argument("--producer-executable", type=Path, required=True)
    parser.add_argument("--generation-prompt", type=Path, required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--route-id", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--provenance-note", required=True)
    parser.add_argument("--max-bytes", type=int, default=5_000_000)
    parser.add_argument("--max-width", type=int, default=4096)
    parser.add_argument("--max-height", type=int, default=4096)
    parser.add_argument("--max-pixels", type=int, default=16_777_216)
    parser.add_argument("--allow-metadata", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        value = validate(args)
        write_json_fresh(args.out, value)
    except (ArtifactError, FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"status": value["status"], "output": str(args.out.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
