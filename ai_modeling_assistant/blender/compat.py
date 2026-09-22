"""Version-dependent Blender operations kept behind a small boundary."""

from contextlib import contextmanager
from pathlib import Path
import re
import uuid
import bpy
import bmesh


def set_geometry_input(modifier, identifier, value):
    """Set a Geometry Nodes interface socket on both 3.6-5.1 and 5.2+."""
    if modifier.type != "NODES" or modifier.node_group is None:
        raise ValueError("A Geometry Nodes modifier with a node group is required")
    if hasattr(modifier, "properties"):
        entry = getattr(modifier.properties.inputs, identifier, None)
        if entry is None or not hasattr(entry, "value"):
            raise ValueError("Unknown Geometry Nodes input identifier: " + identifier)
        entry.value = value
    else:
        if identifier not in modifier:
            raise ValueError("Unknown Geometry Nodes input identifier: " + identifier)
        modifier[identifier] = value
    modifier.id_data.update_tag()


def safe_filename(value):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:100]
    if name.upper().split(".")[0] in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(10)),
        *(f"LPT{i}" for i in range(10)),
    }:
        name = "asset_" + name
    return name or "asset"


@contextmanager
def selected_only(objects):
    if bpy.context.mode != "OBJECT":
        raise RuntimeError("Switch to Object Mode first")
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    try:
        for obj in selected:
            obj.select_set(False)
        for obj in objects:
            obj.select_set(True)
        if objects:
            bpy.context.view_layer.objects.active = objects[0]
        yield
    finally:
        for obj in list(bpy.context.selected_objects):
            obj.select_set(False)
        for obj in selected:
            if obj.name in bpy.context.view_layer.objects:
                obj.select_set(True)
        if active and active.name in bpy.context.view_layer.objects:
            bpy.context.view_layer.objects.active = active


def recalculate_normals(obj=None):
    obj = obj or bpy.context.active_object
    if not obj or obj.type != "MESH":
        return
    editing = obj.mode == "EDIT"
    mesh = bmesh.from_edit_mesh(obj.data) if editing else bmesh.new()
    try:
        if not editing:
            mesh.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
        if editing:
            bmesh.update_edit_mesh(obj.data)
        else:
            mesh.to_mesh(obj.data)
            obj.data.update()
    finally:
        if not editing:
            mesh.free()


def export_objects(path, objects, fmt="glb", engine=""):
    objects = list(objects)
    if not objects:
        raise ValueError("No objects to export")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    from .quality import evaluate

    geometry = any(o.type in {"MESH", "CURVE", "SURFACE", "FONT", "META"} for o in objects)
    quality = evaluate(objects, {"require_geometry": geometry})
    if not quality["passed"]:
        raise ValueError("Export blocked by native quality: " + "; ".join(quality["errors"]))
    with selected_only(objects):
        if fmt in {"glb", "gltf"}:
            from ..core.gltf import inspect_glb

            temporary = path.with_name(path.stem + "-" + uuid.uuid4().hex[:12] + ".glb")
            try:
                result = bpy.ops.export_scene.gltf(
                    filepath=str(temporary),
                    export_format="GLB",
                    use_selection=True,
                    export_cameras=True,
                    export_lights=True,
                )
                if "FINISHED" not in result or not temporary.is_file():
                    raise RuntimeError("GLB exporter did not produce a candidate")
                inspect_glb(temporary, require_mesh=geometry)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        elif fmt == "fbx":
            options = {"filepath": str(path), "use_selection": True, "use_mesh_modifiers": True}
            if engine == "unreal":
                options.update(axis_forward="X", axis_up="Z", global_scale=1.0)
            else:
                options.update(axis_forward="-Z", axis_up="Y")
            result = bpy.ops.export_scene.fbx(**options)
        elif fmt == "obj":
            if bpy.app.version >= (4, 0, 0):
                result = bpy.ops.wm.obj_export(filepath=str(path), export_selected_objects=True)
            else:
                result = bpy.ops.export_scene.obj(filepath=str(path), use_selection=True)
        elif fmt == "stl":
            if bpy.app.version >= (4, 1, 0):
                result = bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
            else:
                result = bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
    if "FINISHED" not in result or not path.is_file():
        raise RuntimeError("Exporter did not produce the requested file")
    return str(path.resolve())


def export_native_scene(path, objects):
    """Preserve Blender-native shaders, world and actions alongside the interchange file."""
    from .scene_state import capture, apply

    objects = list(objects)
    source = bpy.context.scene
    path = Path(path).resolve()
    temporary = path.with_name(path.stem + "-" + uuid.uuid4().hex[:12] + ".blend")
    scene = bpy.data.scenes.new("AI Studio Deliverable")
    try:
        for obj in objects:
            scene.collection.objects.link(obj)
        apply(scene, capture(source, objects), objects, world=source.world)
        scene.frame_set(source.frame_current, subframe=source.frame_subframe)
        bpy.data.libraries.write(str(temporary), {scene}, path_remap="ABSOLUTE", compress=True)
        if not temporary.is_file() or temporary.stat().st_size < 12:
            raise RuntimeError("Native scene exporter produced no file")
        temporary.replace(path)
        return str(path)
    finally:
        bpy.data.scenes.remove(scene)
        temporary.unlink(missing_ok=True)


def import_artifact(artifact, collection=None):
    path = Path(artifact["path"])
    kind = artifact["kind"]
    before = set(bpy.data.objects)
    if kind in {"model3d", "world"}:
        if path.suffix == ".glb":
            result = bpy.ops.import_scene.gltf(filepath=str(path))
        elif path.suffix == ".fbx":
            result = bpy.ops.import_scene.fbx(filepath=str(path))
        elif path.suffix == ".obj":
            result = (
                bpy.ops.wm.obj_import(filepath=str(path))
                if bpy.app.version >= (4, 0, 0)
                else bpy.ops.import_scene.obj(filepath=str(path))
            )
        elif path.suffix == ".stl":
            result = (
                bpy.ops.wm.stl_import(filepath=str(path))
                if bpy.app.version >= (4, 1, 0)
                else bpy.ops.import_mesh.stl(filepath=str(path))
            )
        else:
            raise ValueError("Unsupported 3D artifact")
        if "FINISHED" not in result:
            raise RuntimeError("Blender could not import the generated model")
    elif kind == "image":
        image = bpy.data.images.load(str(path), check_existing=True)
        if not all(image.size):
            raise ValueError("Blender could not decode the generated image")
        obj = bpy.data.objects.new(artifact.get("name", "AI Reference"), None)
        obj.empty_display_type = "IMAGE"
        obj.data = image
        (collection or bpy.context.scene.collection).objects.link(obj)
    elif kind in {"video", "speech"}:
        editor = bpy.context.scene.sequence_editor_create()
        strips = editor.strips if hasattr(editor, "strips") else editor.sequences
        channel = max([s.channel for s in strips] + [0]) + 1
        frame = bpy.context.scene.frame_current
        if kind == "video":
            strips.new_movie(path.stem, str(path), channel, frame)
        else:
            strips.new_sound(path.stem, str(path), channel, frame)
    else:
        raise ValueError(f"Unknown artifact type: {kind}")
    created = list(set(bpy.data.objects) - before)
    if collection:
        for obj in created:
            if obj.name not in collection.objects:
                collection.objects.link(obj)
            for owner in list(obj.users_collection):
                if owner != collection:
                    owner.objects.unlink(obj)
    return created


@contextmanager
def import_transaction(scene):
    """Compensate only this import's new datablocks/strips when validation fails."""
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    registries = (
        "objects",
        "collections",
        "meshes",
        "materials",
        "images",
        "sounds",
        "actions",
        "armatures",
        "cameras",
        "lights",
    )
    before = {name: set(getattr(bpy.data, name)) for name in registries}

    def strips():
        editor = scene.sequence_editor
        return (editor.strips if hasattr(editor, "strips") else editor.sequences) if editor else ()

    previous_strips = set(strips())
    try:
        yield
    except Exception:
        current_strips = strips()
        for strip in set(current_strips) - previous_strips:
            current_strips.remove(strip)
        for name in registries:
            registry = getattr(bpy.data, name)
            for item in set(registry) - before[name]:
                if name in {"objects", "collections"}:
                    registry.remove(item, do_unlink=True)
                elif item.users == 0:
                    registry.remove(item)
        raise
    finally:
        for obj in list(bpy.context.selected_objects):
            obj.select_set(False)
        for obj in selected:
            if obj.name in bpy.context.view_layer.objects:
                obj.select_set(True)
        if active and active.name in bpy.context.view_layer.objects:
            bpy.context.view_layer.objects.active = active
