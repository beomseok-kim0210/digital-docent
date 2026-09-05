"""Embed a PNG albedo in a GLB and bind it to each mesh primitive."""

from __future__ import annotations

import argparse
import json
import os
import struct
import tempfile
from typing import Any


JSON_CHUNK = b"JSON"
BIN_CHUNK = b"BIN\x00"


def parse_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    if len(data) < 12:
        raise ValueError("GLB header is truncated")

    magic, version, declared_length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or declared_length != len(data):
        raise ValueError("Input must be a valid glTF 2.0 binary")

    chunks: dict[bytes, bytes] = {}
    offset = 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("GLB chunk header is truncated")
        chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunk_end = offset + chunk_length
        if chunk_end > len(data):
            raise ValueError("GLB chunk is truncated")
        if chunk_type in chunks:
            raise ValueError(f"Duplicate GLB chunk: {chunk_type!r}")
        chunks[chunk_type] = data[offset:chunk_end]
        offset = chunk_end

    if JSON_CHUNK not in chunks or BIN_CHUNK not in chunks:
        raise ValueError("Input GLB must contain JSON and BIN chunks")

    document = json.loads(chunks[JSON_CHUNK].decode("utf8").rstrip(" \t\r\n\x00"))
    return document, chunks[BIN_CHUNK]


def pad(data: bytes, fill: bytes) -> bytes:
    return data + fill * ((-len(data)) % 4)


def position_bounds(document: dict[str, Any]) -> tuple[list[float], list[float]]:
    accessors = document.get("accessors")
    if not isinstance(accessors, list):
        raise ValueError("GLB does not declare accessors")

    bounds = []
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            position = primitive.get("attributes", {}).get("POSITION")
            if not isinstance(position, int) or not 0 <= position < len(accessors):
                raise ValueError("Every mesh primitive must carry a valid POSITION accessor")
            accessor = accessors[position]
            minimum = accessor.get("min")
            maximum = accessor.get("max")
            if (
                not isinstance(minimum, list)
                or not isinstance(maximum, list)
                or len(minimum) != 3
                or len(maximum) != 3
            ):
                raise ValueError("Every POSITION accessor must declare three-dimensional bounds")
            bounds.append((minimum, maximum))

    if not bounds:
        raise ValueError("GLB contains no bounded mesh primitives")
    return (
        [min(float(minimum[axis]) for minimum, _ in bounds) for axis in range(3)],
        [max(float(maximum[axis]) for _, maximum in bounds) for axis in range(3)],
    )


def normalize_head(document: dict[str, Any], baseline: dict[str, Any]) -> None:
    source_minimum, source_maximum = position_bounds(document)
    target_minimum, target_maximum = position_bounds(baseline)
    source_height = source_maximum[1] - source_minimum[1]
    target_height = target_maximum[1] - target_minimum[1]
    if source_height <= 0 or target_height <= 0:
        raise ValueError("Avatar bounds must have positive height")

    nodes = document.get("nodes")
    head_nodes = (
        [node for node in nodes if node.get("name") == "DocentHead" and "mesh" in node]
        if isinstance(nodes, list)
        else []
    )
    if len(head_nodes) != 1:
        raise ValueError("Input GLB must contain exactly one DocentHead mesh node")
    head = head_nodes[0]
    if any(key in head for key in ("matrix", "rotation", "scale", "translation")):
        raise ValueError("DocentHead node must not already carry a transform")

    scale = target_height / source_height
    source_center_y = (source_minimum[1] + source_maximum[1]) / 2
    target_center_y = (target_minimum[1] + target_maximum[1]) / 2
    head["scale"] = [scale, scale, scale]
    head["translation"] = [0, target_center_y - source_center_y * scale, 0]


def embed_albedo(glb_data: bytes, png_data: bytes, baseline_data: bytes) -> bytes:
    if not png_data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Albedo input is not a PNG")

    document, binary = parse_glb(glb_data)
    baseline, _ = parse_glb(baseline_data)
    if any(document.get(key) for key in ("images", "textures", "materials")):
        raise ValueError("Input GLB already contains image, texture, or material data")

    buffers = document.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise ValueError("Input GLB must declare exactly one buffer")

    binary = pad(binary, b"\x00")
    image_offset = len(binary)
    image_view = len(document.setdefault("bufferViews", []))
    document["bufferViews"].append(
        {
            "buffer": 0,
            "byteOffset": image_offset,
            "byteLength": len(png_data),
        }
    )
    document["images"] = [{"bufferView": image_view, "mimeType": "image/png"}]
    document["textures"] = [{"source": 0}]
    document["materials"] = [
        {
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0},
                "metallicFactor": 0,
                "roughnessFactor": 1,
            }
        }
    ]

    primitives = [
        primitive
        for mesh in document.get("meshes", [])
        for primitive in mesh.get("primitives", [])
    ]
    if not primitives:
        raise ValueError("Input GLB contains no mesh primitives")
    for primitive in primitives:
        if "TEXCOORD_0" not in primitive.get("attributes", {}):
            raise ValueError("Every mesh primitive must carry TEXCOORD_0")
        primitive["material"] = 0

    normalize_head(document, baseline)

    binary = pad(binary + png_data, b"\x00")
    buffers[0]["byteLength"] = len(binary)
    json_data = pad(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf8"),
        b" ",
    )
    total_length = 12 + 8 + len(json_data) + 8 + len(binary)
    return b"".join(
        (
            struct.pack("<4sII", b"glTF", 2, total_length),
            struct.pack("<I4s", len(json_data), JSON_CHUNK),
            json_data,
            struct.pack("<I4s", len(binary), BIN_CHUNK),
            binary,
        )
    )


def write_atomically(path: str, data: bytes) -> None:
    output_dir = os.path.dirname(path) or "."
    os.makedirs(output_dir, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        dir=output_dir,
        prefix=os.path.basename(path) + ".",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
        os.replace(temporary_path, path)
    except BaseException:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise


def main() -> None:
    repository = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "glb",
        nargs="?",
        default=os.path.join(repository, "assets", "qka2", "docent-qka2-textured.glb"),
    )
    parser.add_argument(
        "albedo",
        nargs="?",
        default=os.path.join(repository, "assets", "qka2", "docent-qka2-albedo.png"),
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=os.path.join(repository, "public", "models", "docent-qka2.glb"),
    )
    parser.add_argument(
        "--baseline",
        default=os.path.join(repository, "public", "models", "docent.glb"),
        help="baseline GLB whose bounds define the published avatar scale and vertical position",
    )
    args = parser.parse_args()

    input_paths = {
        os.path.abspath(args.glb),
        os.path.abspath(args.albedo),
        os.path.abspath(args.baseline),
    }
    if os.path.abspath(args.output) in input_paths:
        raise ValueError("Output path must not overwrite an input")

    with open(args.glb, "rb") as source:
        glb_data = source.read()
    with open(args.albedo, "rb") as source:
        png_data = source.read()
    with open(args.baseline, "rb") as source:
        baseline_data = source.read()
    write_atomically(args.output, embed_albedo(glb_data, png_data, baseline_data))


if __name__ == "__main__":
    main()
