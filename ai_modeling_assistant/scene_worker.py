"""Independent Blender process: execute on copies, inspect, produce review evidence."""

import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bpy
from ai_modeling_assistant.blender.execution import CodeExecutor
from ai_modeling_assistant.blender.quality import evaluate
from ai_modeling_assistant.blender.revision import ensure_ids
from ai_modeling_assistant.blender.evidence import render_evidence
from ai_modeling_assistant.blender.scene_state import capture, apply, protected_settings


def run(data, folder):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    collection = bpy.data.collections.new("Agent Branch")
    bpy.context.scene.collection.children.link(collection)
    source = folder / "input.blend"
    if source.exists():
        with bpy.data.libraries.load(str(source), link=False) as (src, dest):
            dest.objects = data["objects"]
            dest.worlds = [data["world"]] if data.get("world") else []
        for obj in dest.objects:
            collection.objects.link(obj)
            obj.select_set(True)
        if dest.objects:
            bpy.context.view_layer.objects.active = dest.objects[0]
    scene = bpy.context.scene
    world = dest.worlds[0] if source.exists() and dest.worlds else None
    apply(scene, data["settings"], list(collection.objects), world=world)
    scene.frame_set(data.get("current_frame", 1), subframe=data.get("current_subframe", 0))
    before = capture(scene, list(collection.objects))
    protected = protected_settings(scene)
    success, output = CodeExecutor.execute(
        data["code"], targets=list(collection.objects), collection=collection, timeout=15
    )
    if not success:
        return {"error": output}
    after_protected = protected_settings(scene)
    unsupported = [key for key in protected if protected[key] != after_protected[key]]
    if unsupported:
        return {
            "error": "Unsupported shared scene settings changed; use Blender's native controls: "
            + ", ".join(unsupported)
        }
    objects = list(collection.all_objects)
    ensure_ids(objects)
    settings = capture(scene, objects)
    if not data.get("contract", {}).get("allow_scene_settings"):
        changed = [key for key in before if key != "frames" and before[key] != settings[key]]
        if changed:
            return {
                "error": "Task changed shared scene settings without allow_scene_settings: "
                + ", ".join(changed)
            }
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
    bpy.data.libraries.write(
        str(output_path), set(objects) | ({scene.world} if scene.world else set())
    )
    previews, evidence_views = [], []

    def evidence(name, direction, kind, *, material=False):
        path = render_evidence(objects, folder / name, direction, material=material)
        if path:
            previews.append(path)
            evidence_views.append({"path": path, "kind": kind, "frame": scene.frame_current})

    if data.get("render", True):
        contracts = [data.get("contract", {})] + [
            c["contract"] for c in data.get("contract_checks", [])
        ]
        if any(c.get("require_materials") for c in contracts):
            evidence(
                "preview-material.png",
                (1.5, -2.4, 1.6),
                "Cycles CPU studio material preview",
                material=True,
            )
        for name, direction in (
            ("preview.png", (1.5, -2.4, 1.6)),
            ("preview-back.png", (-1.5, 2.4, 1.6)),
            ("preview-top.png", (0.001, 0, 3)),
        ):
            evidence(name, direction, "Workbench geometry preview")
        frame, subframe = scene.frame_current, scene.frame_subframe
        try:
            for contract in contracts:
                if contract.get("require_animation"):
                    for sample in contract.get("animation_range", data["frames"]):
                        scene.frame_set(sample)
                        evidence(
                            f"preview-frame-{sample}.png",
                            (1.5, -2.4, 1.6),
                            "Workbench animation sample",
                        )
                    break
        finally:
            scene.frame_set(frame, subframe=subframe)
    preview = str(folder / "preview.png") if previews else ""
    return {
        "output": output,
        "blend": str(output_path),
        "objects": [o.name for o in objects],
        "quality": report,
        "preview": preview,
        "previews": previews,
        "evidence_views": evidence_views,
        "frames": [scene.frame_start, scene.frame_end],
        "settings": settings,
        "world": scene.world.name if scene.world else None,
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
