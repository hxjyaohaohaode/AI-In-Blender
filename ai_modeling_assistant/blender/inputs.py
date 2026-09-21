"""Blender input capture and explicit multimodal provider conditioning."""

import json
import uuid
import bpy
from ..core.attachments import attachment, vision_parts


def items(scene):
    return json.loads(scene.ama_props.attachments_json or "[]")


def add(scene, path, role="reference"):
    refs = items(scene)
    if len(refs) >= 8:
        raise ValueError("At most eight input attachments per request")
    value = attachment(bpy.path.abspath(str(path)), role=role)
    if not any(i["sha256"] == value["sha256"] for i in refs):
        refs.append(value)
    scene.ama_props.attachments_json = json.dumps(refs, ensure_ascii=False)
    return value


def attach_to_messages(scene, messages, config, *, snapshot=None):
    refs = snapshot["attachments"] if snapshot is not None else items(scene)
    if refs:
        original = messages[-1]["content"]
        parts = original if isinstance(original, list) else [{"type": "text", "text": original}]
        messages[-1]["content"] = parts + vision_parts(
            refs, enabled=config.options.get("vision", False)
        )
    regions = (
        snapshot["region"]
        if snapshot is not None
        else json.loads(scene.ama_props.region_json or "[]")
    )
    if regions:
        region = (
            "\nSelected edit region (scope, not permission to modify other regions):\n"
            + json.dumps(regions)
        )
        if isinstance(messages[-1]["content"], list):
            messages[-1]["content"].append({"type": "text", "text": region})
        else:
            messages[-1]["content"] += region


def capture_region(context):
    import bmesh
    from .revision import fingerprint, ensure_ids

    objects = (
        list(context.objects_in_mode)
        if context.mode == "EDIT_MESH"
        else list(context.selected_objects)
    )
    if not objects:
        raise ValueError("Select an object or mesh vertices/faces first")
    ensure_ids(objects)
    result = []
    for obj in objects:
        record = {
            "object": obj.name,
            "asset_id": obj["ama_asset_id"],
            "fingerprint": fingerprint([obj]),
        }
        if obj.type == "MESH" and obj.mode == "EDIT":
            mesh = bmesh.from_edit_mesh(obj.data)
            mesh.verts.ensure_lookup_table()
            mesh.faces.ensure_lookup_table()
            record["vertices"] = [v.index for v in mesh.verts if v.select]
            record["faces"] = [f.index for f in mesh.faces if f.select]
            if len(record["vertices"]) > 3000:
                raise ValueError("Select a smaller edit region (at most 3000 vertices)")
        result.append(record)
    context.scene.ama_props.region_json = json.dumps(result)
    return result


def capture_view(context):
    if bpy.app.background:
        raise ValueError("Viewport capture requires an interactive Blender window")
    area = next((a for a in context.screen.areas if a.type == "VIEW_3D"), None)
    if not area:
        raise ValueError("Open a 3D viewport before capturing a reference")
    from .conversation import database_path

    folder = database_path().parent / "references"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (uuid.uuid4().hex + ".png")
    scene = context.scene
    saved = (
        scene.render.filepath,
        scene.render.image_settings.file_format,
        scene.render.resolution_x,
        scene.render.resolution_y,
        scene.render.resolution_percentage,
    )
    try:
        scene.render.filepath = str(path)
        scene.render.image_settings.file_format = "PNG"
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = (
            768,
            768,
            100,
        )
        region = next(r for r in area.regions if r.type == "WINDOW")
        with context.temp_override(area=area, region=region):
            bpy.ops.render.opengl(write_still=True, view_context=True)
    finally:
        (
            scene.render.filepath,
            scene.render.image_settings.file_format,
            scene.render.resolution_x,
            scene.render.resolution_y,
            scene.render.resolution_percentage,
        ) = saved
    return add(scene, path, role="sketch_or_viewport")


def new_sketch():
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    if bpy.app.version >= (4, 3, 0):
        bpy.ops.object.grease_pencil_add(type="EMPTY")
    else:
        bpy.ops.object.gpencil_add(type="EMPTY")
    bpy.context.object.name = "AI Sketch Reference"
    mode = "PAINT_GREASE_PENCIL" if bpy.app.version >= (4, 3, 0) else "PAINT_GPENCIL"
    bpy.ops.object.mode_set(mode=mode)
    return bpy.context.object
