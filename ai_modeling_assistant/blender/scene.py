"""Bounded scene descriptions and context-independent mesh cleanup."""
import bpy
import bmesh


class SceneContextGenerator:
    @staticmethod
    def generate(objects=None):
        scene = bpy.context.scene
        objects = list(scene.objects if objects is None else objects)
        lines = [f"Blender {bpy.app.version_string}; scene {scene.name}; Z up; unit system {scene.unit_settings.system}; meters per scene unit {scene.unit_settings.scale_length}.",
                 f"Objects: {len(objects)}; frames {scene.frame_start}-{scene.frame_end}; current {scene.frame_current}.",
                 "Selected: " + ", ".join(o.name for o in bpy.context.selected_objects[:30])]
        for obj in objects[:80]:
            lines.append(SceneContextGenerator._describe_object(obj))
        if len(objects) > 80:
            lines.append(f"{len(objects) - 80} additional objects omitted from context.")
        return "\n".join(lines)[:24000]

    @staticmethod
    def _describe_object(obj, indent=""):
        text = (f"{indent}{obj.name!r} [{obj.type}] location={tuple(round(v, 3) for v in obj.location)} "
                f"dimensions={tuple(round(v, 3) for v in obj.dimensions)}")
        if obj.type == "MESH":
            text += f" vertices={len(obj.data.vertices)} faces={len(obj.data.polygons)} UVs={len(obj.data.uv_layers)}"
            text += " materials=" + ",".join(m.name for m in obj.data.materials if m)
        if obj.modifiers:
            text += " modifiers=" + ",".join(m.type for m in obj.modifiers)
        return text


class PostProcessor:
    @staticmethod
    def process_all():
        results = [f"{o.name}: {PostProcessor.process_object(o)}"
                   for o in bpy.context.scene.objects if o.type == "MESH"]
        return True, "\n".join(results) if results else "No meshes to clean"

    @staticmethod
    def process_object(obj):
        if obj.type != "MESH" or obj.mode != "OBJECT":
            return "Switch the mesh to Object Mode to clean it"
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        mesh = bmesh.new()
        try:
            mesh.from_mesh(obj.data)
            bmesh.ops.remove_doubles(mesh, verts=list(mesh.verts), dist=0.00001)
            bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
            mesh.to_mesh(obj.data)
            obj.data.update()
        finally:
            mesh.free()
        return "Merged coincident vertices and recalculated normals"


def geometry_report(objects):
    report = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        mesh = bmesh.new()
        try:
            mesh.from_mesh(obj.data)
            report.append({"name": obj.name, "vertices": len(mesh.verts), "faces": len(mesh.faces),
                "loose_vertices": sum(not v.link_edges for v in mesh.verts),
                "non_manifold_edges": sum(not e.is_manifold for e in mesh.edges),
                "ngons": sum(len(f.verts) > 4 for f in mesh.faces),
                "materials": len(obj.data.materials), "uv_layers": len(obj.data.uv_layers)})
        finally:
            mesh.free()
    return {"meshes": report, "mesh_count": len(report),
            "note": "Open boundaries and n-gons may be intentional; these are diagnostics, not visual quality scores."}
