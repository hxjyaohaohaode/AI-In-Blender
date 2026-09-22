"""blender / quality — extracted from the original add-on."""

from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
import bpy


def evaluate(objects, contract=None, *, name_map=None):
    """Validate the evaluated deliverable at bounded temporal samples, restoring time."""
    from .quality_checks import animation_evidence, sample_frames
    from .revision import fingerprint

    objects, contract = list(objects), contract or {}
    scene = bpy.context.scene
    original_frame, original_subframe = scene.frame_current, scene.frame_subframe
    animation = animation_evidence(objects)
    frames = sample_frames(scene, contract, animation)
    results = []
    try:
        for frame in frames:
            scene.frame_set(frame)
            results.append((frame, _evaluate_frame(objects, contract, name_map=name_map)))
    finally:
        scene.frame_set(original_frame, subframe=original_subframe)
    report = dict(results[0][1])
    report["fingerprint"] = fingerprint(objects)
    report["sampled_frames"] = frames
    report["animation"] = animation
    report["errors"] = list(animation["errors"])
    report["warnings"] = []
    report["temporal_checks"] = []
    for frame, item in results:
        report["temporal_checks"].append(
            {"frame": frame, "passed": item["passed"], "meshes": item["meshes"]}
        )
        for level in ("errors", "warnings"):
            report[level].extend(
                (f"Frame {frame}: " if len(frames) > 1 else "") + e for e in item[level]
            )
    if contract.get("require_animation"):
        start, end = contract.get("animation_range", [scene.frame_start, scene.frame_end])
        times = animation["keyframe_times"]
        if len(times) < 2:
            report["errors"].append(
                "No animation keyframes across at least two distinct times in the deliverable"
            )
        elif times[0] > start or times[-1] < end:
            report["errors"].append("Animation keyframes do not cover the required delivery range")
    report["passed"] = not report["errors"]
    return report


def _evaluate_frame(objects, contract=None, *, name_map=None):
    """Mandatory native gates. Artistic judgement is a separate evidence type."""
    import bmesh
    import math
    from mathutils import Vector

    contract = contract or {}
    objects = list(objects)
    name_map = name_map or {}
    report = {
        "passed": True,
        "errors": [],
        "warnings": [],
        "meshes": [],
        "visual_review": "unverified",
    }
    meshes = [o for o in objects if o.type in {"MESH", "CURVE", "SURFACE", "FONT", "META"}]
    for obj in objects:
        if not all(math.isfinite(c) for row in obj.matrix_world for c in row):
            report["errors"].append(obj.name + ": non-finite transform")
    if contract.get("require_geometry", True) and not meshes:
        report["errors"].append("No mesh output")
    for obj in meshes:
        mesh = bmesh.new()
        evaluated = None
        try:
            source = obj.data
            if obj.name in bpy.context.view_layer.objects:
                evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                source = evaluated.to_mesh()
            mesh.from_mesh(source)
            invalid = sum(not all(math.isfinite(c) for c in v.co) for v in mesh.verts)
            degenerate = sum(f.calc_area() <= 1e-12 for f in mesh.faces)
            non_manifold = sum(not e.is_manifold for e in mesh.edges)
            winding = sum(
                len(e.link_loops) == 2 and e.link_loops[0].vert == e.link_loops[1].vert
                for e in mesh.edges
            )
            item = {
                "name": obj.name,
                "vertices": len(mesh.verts),
                "faces": len(mesh.faces),
                "invalid_vertices": invalid,
                "degenerate_faces": degenerate,
                "non_manifold_edges": non_manifold,
                "inconsistent_winding_edges": winding,
            }
            report["meshes"].append(item)
            if not mesh.verts or not mesh.faces:
                report["errors"].append(obj.name + ": empty geometry")
            if invalid or degenerate:
                report["errors"].append(
                    f"{obj.name}: {invalid} invalid vertices, {degenerate} degenerate faces"
                )
            if winding:
                report["errors"].append(
                    f"{obj.name}: {winding} edges have inconsistent face winding"
                )
            if not all(math.isfinite(c) for row in obj.matrix_world for c in row):
                report["errors"].append(obj.name + ": non-finite transform")
            if non_manifold:
                destination = "errors" if contract.get("closed_mesh") else "warnings"
                report[destination].append(f"{obj.name}: {non_manifold} open/non-manifold edges")
            if not any(source.materials):
                report["errors" if contract.get("require_materials") else "warnings"].append(
                    obj.name + ": no material"
                )
            if contract.get("require_materials") and any(
                p.material_index >= len(source.materials)
                or source.materials[p.material_index] is None
                for p in source.polygons
            ):
                report["errors"].append(obj.name + ": unassigned material faces")
            if contract.get("require_uv") and not source.uv_layers:
                report["errors"].append(obj.name + ": missing UV map")
            elif contract.get("require_uv"):
                uv = source.uv_layers.active.data
                collapsed = 0
                for face in source.polygons:
                    coords = [uv[i].uv for i in face.loop_indices]
                    area = (
                        abs(
                            sum(
                                a.x * b.y - b.x * a.y
                                for a, b in zip(coords, coords[1:] + coords[:1])
                            )
                        )
                        / 2
                    )
                    collapsed += area <= 1e-12
                if collapsed:
                    report["errors"].append(f"{obj.name}: {collapsed} faces have collapsed UVs")
            from .quality_checks import material_issues

            for material in set(m for m in source.materials if m):
                report["errors" if contract.get("require_materials") else "warnings"].extend(
                    obj.name + ": " + material.name + ": " + error
                    for error in material_issues(material)
                )
            if any(
                not math.isfinite(c)
                for layer in source.uv_layers
                for uv in layer.data
                for c in uv.uv
            ):
                report["errors"].append(obj.name + ": non-finite UV coordinates")
            matrix = evaluated.matrix_world if evaluated else obj.matrix_world
            positions = [matrix @ vertex.co for vertex in source.vertices]
            low = [min((p[i] for p in positions), default=0) for i in range(3)]
            high = [max((p[i] for p in positions), default=0) for i in range(3)]
            if max(high[i] - low[i] for i in range(3)) > contract.get("max_extent", 1e9):
                report["errors"].append(obj.name + ": exceeds dimension limit")
            if any(
                low[i] < contract.get("bounds_min", [-1e30] * 3)[i] - 1e-5
                or high[i] > contract.get("bounds_max", [1e30] * 3)[i] + 1e-5
                for i in range(3)
            ):
                report["errors"].append(obj.name + ": exceeds assigned assembly bounds")
        finally:
            mesh.free()
            if evaluated:
                evaluated.to_mesh_clear()
    total = sum(m["vertices"] for m in report["meshes"])
    if total < contract.get("min_vertices", 0) or total > contract.get("max_vertices", 10_000_000):
        report["errors"].append("Vertex count violates the task contract")
    faces = sum(m["faces"] for m in report["meshes"])
    if not contract.get("min_faces", 0) <= faces <= contract.get("max_faces", 10_000_000):
        report["errors"].append("Face count violates the task contract")
    if contract.get("require_rig") and not any(
        o.type == "ARMATURE" and o.data.bones for o in objects
    ):
        report["errors"].append("No nonempty armature in the deliverable")
    for name in contract.get("required_objects", []):
        if not any(name_map.get(o.name, o.name) == name for o in objects):
            report["errors"].append("Missing required object: " + name)
    if "anchor_position" in contract:
        anchor = next(
            (o for o in objects if name_map.get(o.name, o.name) == contract["anchor_object"]), None
        )
        if anchor is None or (
            anchor.matrix_world.translation - Vector(contract["anchor_position"])
        ).length > contract.get("anchor_tolerance", 0.001):
            report["errors"].append(
                "Assembly anchor missing or outside tolerance: " + contract["anchor_object"]
            )
    report["passed"] = not report["errors"]
    return report


class MeshAnalyzer:
    """Detailed mesh quality analysis tools."""

    @staticmethod
    def analyze(obj: bpy.types.Object) -> Dict[str, Any]:
        """Comprehensive mesh analysis for an object."""
        if obj.type != "MESH":
            return {"error": f"{obj.name} is not a mesh"}

        mesh = obj.data
        result = {
            "name": obj.name,
            "vertices": len(mesh.vertices),
            "edges": len(mesh.edges),
            "faces": len(mesh.polygons),
            "materials": len(mesh.materials),
            "has_uvs": len(mesh.uv_layers) > 0,
            "uv_layers": len(mesh.uv_layers),
        }

        # Check for non-manifold
        import bmesh

        bm = bmesh.new()
        bm.from_mesh(mesh)

        non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
        loose_verts = [v for v in bm.verts if not v.link_edges]
        loose_edges = [e for e in bm.edges if not e.link_faces]
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        tris = [f for f in bm.faces if len(f.verts) == 3]

        result["non_manifold_edges"] = len(non_manifold_edges)
        result["loose_vertices"] = len(loose_verts)
        result["loose_edges"] = len(loose_edges)
        result["ngons"] = len(ngons)
        result["triangles"] = len(tris)
        result["quads"] = result["faces"] - len(ngons) - len(tris)

        # Downward-facing polygons are valid. Check inconsistent winding across shared edges.
        inconsistent = set()
        for edge in bm.edges:
            loops = list(edge.link_loops)
            if len(loops) == 2 and loops[0].vert == loops[1].vert:
                inconsistent.update(loop.face for loop in loops)
        result["possibly_flipped_faces"] = len(inconsistent)

        bm.free()

        # Bounding box
        from mathutils import Vector

        bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        if bbox:
            xs = [v.x for v in bbox]
            ys = [v.y for v in bbox]
            zs = [v.z for v in bbox]
            result["bbox_min"] = (min(xs), min(ys), min(zs))
            result["bbox_max"] = (max(xs), max(ys), max(zs))
            result["dimensions"] = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

        return result


class QualityChecker:
    """Automated quality detection and repair."""

    @staticmethod
    def check_all() -> List[Dict[str, Any]]:
        """Check all mesh objects in the scene."""
        issues = []
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH":
                continue
            analysis = MeshAnalyzer.analyze(obj)
            if "error" in analysis:
                continue

            if analysis["loose_vertices"] > 0:
                issues.append(
                    {
                        "object": obj.name,
                        "type": "loose_vertices",
                        "count": analysis["loose_vertices"],
                        "severity": "warning",
                    }
                )
            if analysis["loose_edges"] > 0:
                issues.append(
                    {
                        "object": obj.name,
                        "type": "loose_edges",
                        "count": analysis["loose_edges"],
                        "severity": "warning",
                    }
                )
            if analysis["non_manifold_edges"] > 0:
                issues.append(
                    {
                        "object": obj.name,
                        "type": "non_manifold",
                        "count": analysis["non_manifold_edges"],
                        "severity": "warning",
                    }
                )
            if analysis["possibly_flipped_faces"] > 0:
                issues.append(
                    {
                        "object": obj.name,
                        "type": "flipped_normals",
                        "count": analysis["possibly_flipped_faces"],
                        "severity": "error",
                    }
                )
            if analysis["ngons"] > 0:
                issues.append(
                    {
                        "object": obj.name,
                        "type": "ngons",
                        "count": analysis["ngons"],
                        "severity": "info",
                    }
                )
            if analysis["materials"] == 0:
                issues.append(
                    {"object": obj.name, "type": "no_material", "count": 1, "severity": "info"}
                )
        return issues

    @staticmethod
    def fix_object(obj_name: str) -> Tuple[bool, str]:
        """Attempt to fix common mesh issues."""
        obj = bpy.context.scene.objects.get(obj_name)
        if not obj or obj.type != "MESH":
            return False, "Object not found or not a mesh"
        if obj.mode != "OBJECT":
            return False, "Switch to Object Mode before repairing the mesh"
        if obj.data.users > 1:
            obj.data = obj.data.copy()

        fixes = []
        import bmesh

        bm = bmesh.new()
        bm.from_mesh(obj.data)

        # Remove loose vertices
        loose = [v for v in bm.verts if not v.link_edges]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
            fixes.append(f"Removed {len(loose)} loose vertices")

        # Remove loose edges
        loose_e = [e for e in bm.edges if not e.link_faces]
        if loose_e:
            bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
            fixes.append(f"Removed {len(loose_e)} loose edges")

        # Recalculate normals
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        fixes.append("Recalculated normals")

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

        return True, "; ".join(fixes) if fixes else "No issues found"
