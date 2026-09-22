"""Explicit transferable scene settings for serialized lighting/presentation tasks."""

import hashlib
import json
from .revision import node_values, animation_values, rna_values


def protected_settings(scene):
    """Reject unsupported global mutations instead of reporting success then losing them."""
    render = rna_values(scene.render)
    for key in (
        "fps",
        "fps_base",
        "resolution_x",
        "resolution_y",
        "resolution_percentage",
        "engine",
        "film_transparent",
    ):
        render.pop(key, None)
    editor = scene.sequence_editor
    strips = (editor.strips if hasattr(editor, "strips") else editor.sequences) if editor else []
    return {
        "render_output": render,
        "cycles": rna_values(scene.cycles),
        "eevee": rna_values(scene.eevee) if hasattr(scene, "eevee") else None,
        "compositor": node_values(
            scene.compositing_node_group
            if hasattr(scene, "compositing_node_group")
            else scene.node_tree
        ),
        "use_nodes": scene.use_nodes if hasattr(scene, "node_tree") else None,
        "sequencer": [rna_values(s) for s in strips],
    }


def capture(scene, objects):
    world = scene.world
    world_data = (
        (list(world.color), world.use_nodes, node_values(world.node_tree), animation_values(world))
        if world
        else None
    )
    return {
        "frames": [scene.frame_start, scene.frame_end],
        "fps": scene.render.fps,
        "fps_base": scene.render.fps_base,
        "unit_scale": scene.unit_settings.scale_length,
        "unit_system": scene.unit_settings.system,
        "resolution": [
            scene.render.resolution_x,
            scene.render.resolution_y,
            scene.render.resolution_percentage,
        ],
        "engine": scene.render.engine,
        "film_transparent": scene.render.film_transparent,
        "view_transform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": scene.view_settings.exposure,
        "gamma": scene.view_settings.gamma,
        "camera_id": scene.camera.get("ama_asset_id") if scene.camera in objects else None,
        "world_revision": hashlib.sha256(
            json.dumps(world_data, sort_keys=True, default=str).encode()
        ).hexdigest(),
    }


def apply(scene, values, objects, *, world=None):
    """Call first in a disposable scene; invalid enums/ranges never reach the user's scene."""
    scene.frame_start, scene.frame_end = values["frames"]
    scene.render.fps, scene.render.fps_base = values["fps"], values["fps_base"]
    scene.unit_settings.scale_length, scene.unit_settings.system = (
        values["unit_scale"],
        values["unit_system"],
    )
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = (
        values["resolution"]
    )
    scene.render.engine, scene.render.film_transparent = (
        values["engine"],
        values["film_transparent"],
    )
    scene.view_settings.view_transform = values["view_transform"]
    scene.view_settings.look = values["look"]
    scene.view_settings.exposure, scene.view_settings.gamma = values["exposure"], values["gamma"]
    camera = next(
        (o for o in objects if o.get("ama_asset_id") == values["camera_id"] and o.type == "CAMERA"),
        None,
    )
    if values["camera_id"] and camera is None:
        raise ValueError("Scene camera must belong to the task's object scope")
    scene.camera, scene.world = camera, world
