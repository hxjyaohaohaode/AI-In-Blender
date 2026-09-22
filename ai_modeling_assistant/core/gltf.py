"""Check the self-contained GLB actually written by the exporter before delivery."""

import json
from pathlib import Path
import struct


def inspect_glb(path, *, require_mesh=True):
    path = Path(path)
    size = path.stat().st_size
    with path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12:
            raise ValueError("Truncated GLB header")
        magic, version, declared = struct.unpack("<4sII", header)
        if magic != b"glTF" or version != 2 or declared != size:
            raise ValueError("Invalid GLB magic, version or declared length")
        manifest, binary_bytes = None, 0
        while stream.tell() < size:
            chunk = stream.read(8)
            if len(chunk) != 8:
                raise ValueError("Truncated GLB chunk")
            length, kind = struct.unpack("<I4s", chunk)
            if length % 4 or stream.tell() + length > size:
                raise ValueError("Invalid GLB chunk length")
            if manifest is None:
                if kind != b"JSON" or length > 16_000_000:
                    raise ValueError("GLB requires a bounded first JSON chunk")
                manifest = json.loads(stream.read(length).decode("utf-8"))
            elif kind == b"BIN\x00":
                if binary_bytes:
                    raise ValueError("GLB contains multiple binary chunks")
                binary_bytes = length
                stream.seek(length, 1)
            else:
                stream.seek(length, 1)
    if not isinstance(manifest, dict) or manifest.get("asset", {}).get("version") != "2.0":
        raise ValueError("GLB contains no glTF 2.0 asset")
    buffers = manifest.get("buffers", [])
    if len(buffers) > 1 or any("uri" in b for b in buffers):
        raise ValueError("Delivery GLB must embed its binary buffer")
    if buffers and not 0 <= buffers[0].get("byteLength", -1) <= binary_bytes:
        raise ValueError("GLB buffer exceeds binary chunk")
    views = manifest.get("bufferViews", [])
    for view in views:
        if (
            not buffers
            or view.get("buffer") != 0
            or not (
                0
                <= view.get("byteOffset", 0)
                <= view.get("byteOffset", 0) + view.get("byteLength", -1)
                <= buffers[0]["byteLength"]
            )
        ):
            raise ValueError("GLB buffer view exceeds its embedded buffer")
    for image in manifest.get("images", []):
        index = image.get("bufferView")
        if "uri" in image or type(index) is not int or not 0 <= index < len(views):
            raise ValueError("Delivery GLB contains a missing or external image")
    meshes, nodes, accessors = (manifest.get(k, []) for k in ("meshes", "nodes", "accessors"))
    reachable, pending = set(), []
    scenes = manifest.get("scenes", [])
    active = manifest.get("scene", 0)
    if scenes and type(active) is int and 0 <= active < len(scenes):
        pending = list(scenes[active].get("nodes", []))
    while pending:
        index = pending.pop()
        if type(index) is not int or not 0 <= index < len(nodes):
            raise ValueError("GLB scene references an invalid node")
        if index in reachable:
            continue
        reachable.add(index)
        pending.extend(nodes[index].get("children", []))
    mesh_ids = {nodes[i]["mesh"] for i in reachable if "mesh" in nodes[i]}
    if require_mesh and not mesh_ids:
        raise ValueError("Export produced no reachable mesh in the delivery scene")
    vertices, primitives = 0, 0
    for index in mesh_ids:
        if type(index) is not int or not 0 <= index < len(meshes):
            raise ValueError("GLB node references an invalid mesh")
        for primitive in meshes[index].get("primitives", []):
            accessor_id = primitive.get("attributes", {}).get("POSITION")
            if type(accessor_id) is not int or not 0 <= accessor_id < len(accessors):
                raise ValueError("GLB primitive has no valid vertex positions")
            accessor = accessors[accessor_id]
            if (
                accessor.get("type") != "VEC3"
                or type(accessor.get("count")) is not int
                or accessor["count"] < 3
            ):
                raise ValueError("GLB primitive contains insufficient vertex positions")
            view_id = accessor.get("bufferView")
            if type(view_id) is not int or not 0 <= view_id < len(views):
                raise ValueError("GLB vertex positions have no embedded buffer view")
            component = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}.get(
                accessor.get("componentType")
            )
            view = views[view_id]
            if component is None:
                raise ValueError("GLB vertex component type is invalid")
            stride, offset = view.get("byteStride", component * 3), accessor.get("byteOffset", 0)
            if (
                type(stride) is not int
                or type(offset) is not int
                or stride < component * 3
                or offset < 0
                or (offset + (accessor["count"] - 1) * stride + component * 3 > view["byteLength"])
            ):
                raise ValueError("GLB vertex accessor exceeds its buffer view")
            vertices += accessor["count"]
            primitives += 1
    if require_mesh and not primitives:
        raise ValueError("Export produced empty meshes")
    return {
        "format": "GLB 2.0",
        "bytes": size,
        "reachable_nodes": len(reachable),
        "meshes": len(mesh_ids),
        "primitives": primitives,
        "vertices": vertices,
        "materials": len(manifest.get("materials", [])),
        "animations": len(manifest.get("animations", [])),
        "embedded_images": len(manifest.get("images", [])),
    }
