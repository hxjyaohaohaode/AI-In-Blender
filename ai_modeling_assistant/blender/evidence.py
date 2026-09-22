"""Bounded real renders with explicit evidence types and restored scene state."""

import bpy
from mathutils import Vector


def render_evidence(objects, path, direction=(1.5, -2.4, 1.6), *, material=False):
    scene = bpy.context.scene
    graph = bpy.context.evaluated_depsgraph_get()
    points = [
        o.evaluated_get(graph).matrix_world @ Vector(corner)
        for o in objects
        if o.type in {"MESH", "CURVE", "SURFACE", "FONT"}
        for corner in o.evaluated_get(graph).bound_box
    ]
    if not points:
        return ""
    center = sum(points, Vector()) / len(points)
    radius = max((p - center).length for p in points) or 1
    saved = {
        "camera": scene.camera,
        "world": scene.world,
        "engine": scene.render.engine,
        "x": scene.render.resolution_x,
        "y": scene.render.resolution_y,
        "percentage": scene.render.resolution_percentage,
        "format": scene.render.image_settings.file_format,
        "path": scene.render.filepath,
        "transparent": scene.render.film_transparent,
        "samples": scene.cycles.samples,
        "device": scene.cycles.device,
        "denoise": scene.cycles.use_denoising,
        "shading": {
            k: getattr(scene.display.shading, k)
            for k in ("light", "color_type", "show_shadows", "show_cavity")
        },
    }
    created, light_data, world = [], [], None
    data = bpy.data.cameras.new("Quality Camera")
    camera = bpy.data.objects.new("Quality Camera", data)
    created.append(camera)
    scene.collection.objects.link(camera)
    camera.location = center + Vector(direction).normalized() * radius * 3.6
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    data.lens = 45
    data.clip_start, data.clip_end = max(0.001, radius / 1000), max(100, radius * 20)
    try:
        scene.camera = camera
        scene.render.engine = "CYCLES" if material else "BLENDER_WORKBENCH"
        if material:
            # CPU works on headless CI and machines without a supported GPU.
            scene.cycles.device, scene.cycles.samples = "CPU", 16
            scene.cycles.use_denoising = False
            world = bpy.data.worlds.new("Material Evidence Studio")
            world.use_nodes = True
            world.node_tree.nodes["Background"].inputs["Color"].default_value = (
                0.15,
                0.15,
                0.15,
                1,
            )
            world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
            scene.world = world
            for offset, energy in (((2, -3, 4), 900), ((-3, -1, 2), 500), ((0, 3, 3), 700)):
                light = bpy.data.lights.new("Evidence Softbox", "AREA")
                light_data.append(light)
                light.energy, light.shape, light.size = energy * radius * radius, "DISK", radius * 3
                obj = bpy.data.objects.new(light.name, light)
                created.append(obj)
                scene.collection.objects.link(obj)
                obj.location = center + Vector(offset) * radius
                obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()
        else:
            scene.display.shading.light = "STUDIO"
            scene.display.shading.color_type = "MATERIAL"
            scene.display.shading.show_shadows = scene.display.shading.show_cavity = True
        scene.render.resolution_x = scene.render.resolution_y = 384 if material else 512
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return str(path)
    finally:
        scene.camera, scene.world = saved["camera"], saved["world"]
        scene.render.engine = saved["engine"]
        scene.render.resolution_x, scene.render.resolution_y = saved["x"], saved["y"]
        scene.render.resolution_percentage = saved["percentage"]
        scene.render.image_settings.file_format, scene.render.filepath = (
            saved["format"],
            saved["path"],
        )
        scene.render.film_transparent = saved["transparent"]
        scene.cycles.samples, scene.cycles.device = saved["samples"], saved["device"]
        scene.cycles.use_denoising = saved["denoise"]
        for key, value in saved["shading"].items():
            setattr(scene.display.shading, key, value)
        for obj in created:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.cameras.remove(data)
        for light in light_data:
            bpy.data.lights.remove(light)
        if world:
            bpy.data.worlds.remove(world)
