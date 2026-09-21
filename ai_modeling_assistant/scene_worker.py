"""Independent Blender process: execute on copies, inspect, produce review evidence."""

import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bpy
from mathutils import Vector
from ai_modeling_assistant.blender.execution import CodeExecutor
from ai_modeling_assistant.blender.quality import evaluate
from ai_modeling_assistant.blender.revision import ensure_ids


def render_evidence(objects, path, direction=(1.5, -2.4, 1.6)):
    scene = bpy.context.scene
    points = [
        o.matrix_world @ Vector(corner)
        for o in objects
        if o.type == "MESH"
        for corner in o.bound_box
    ]
    if not points:
        return ""
    center = sum(points, Vector()) / len(points)
    radius = max((p - center).length for p in points) or 1
    data = bpy.data.cameras.new("Quality Camera")
    camera = bpy.data.objects.new("Quality Camera", data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector(direction).normalized() * radius * 3.6
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    data.lens = 45
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    scene.camera = None
    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(data)
    return str(path)


def run(data, folder):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    collection = bpy.data.collections.new("Agent Branch")
    bpy.context.scene.collection.children.link(collection)
    source = folder / "input.blend"
    if source.exists():
        with bpy.data.libraries.load(str(source), link=False) as (src, dest):
            dest.objects = data["objects"]
        for obj in dest.objects:
            collection.objects.link(obj)
            obj.select_set(True)
        if dest.objects:
            bpy.context.view_layer.objects.active = dest.objects[0]
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = data["frames"]
    scene.unit_settings.scale_length = data.get("unit_scale", 1)
    scene.render.fps = data.get("fps", 24)
    scene.render.fps_base = data.get("fps_base", 1.0)
    scene.frame_set(data.get("current_frame", 1))
    success, output = CodeExecutor.execute(
        data["code"], targets=list(collection.objects), collection=collection, timeout=15
    )
    if not success:
        return {"error": output}
    objects = list(collection.all_objects)
    ensure_ids(objects)
    report = evaluate(objects, data.get("contract"))
    for check in data.get("contract_checks", []):
        targets = [o for o in objects if o.get("ama_asset_id") in check["asset_ids"]]
        if len(targets) != len(check["asset_ids"]):
            report["errors"].append("Missing dependency assets: " + check["task"])
        inherited = evaluate(targets, check["contract"])
        report["errors"].extend(check["task"] + ": " + e for e in inherited["errors"])
    report["passed"] = not report["errors"]
    if not report["passed"]:
        return {
            "error": "Native quality gate failed: " + "; ".join(report["errors"]),
            "quality": report,
        }
    output_path = folder / "candidate.blend"
    bpy.data.libraries.write(str(output_path), set(objects))
    previews = []
    if data.get("render", True):
        for name, direction in (
            ("preview.png", (1.5, -2.4, 1.6)),
            ("preview-back.png", (-1.5, 2.4, 1.6)),
            ("preview-top.png", (0.001, 0, 3)),
        ):
            preview = render_evidence(objects, folder / name, direction)
            if preview:
                previews.append(preview)
    preview = previews[0] if previews else ""
    return {
        "output": output,
        "blend": str(output_path),
        "objects": [o.name for o in objects],
        "quality": report,
        "preview": preview,
        "previews": previews,
        "frames": [scene.frame_start, scene.frame_end],
    }


def main():
    folder = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    try:
        data = json.loads((folder / "request.json").read_text(encoding="utf-8"))
        result = run(data, folder)
    except Exception:
        result = {"error": traceback.format_exc(limit=6)}
    temporary = folder / "result.tmp"
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(folder / "result.json")


if __name__ == "__main__":
    main()
