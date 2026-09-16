"""Deterministic offline example: geometry, PBR, rigid rig, animation and GLB export.

This is a bundled example, not a claim of output from a live generative model.
"""
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from .compat import export_objects
from .runtime import output_directory
from .scene import geometry_report


def material(name, color, metallic=0.0, roughness=0.3, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*color, 1)
    node.inputs["Metallic"].default_value = metallic
    node.inputs["Roughness"].default_value = roughness
    if emission:
        emission_input = node.inputs.get("Emission Color") or node.inputs.get("Emission")
        emission_input.default_value = (*color, 1)
        strength = node.inputs.get("Emission Strength")
        if strength:
            strength.default_value = emission
    return mat


def build_demo(scene, folder=None):
    if bpy.context.mode != "OBJECT":
        raise ValueError("Switch to Object Mode to build the demo")
    before = set(bpy.data.objects)
    collection = bpy.data.collections.new("HELIO · Offline Studio Demo")
    scene.collection.children.link(collection)
    bronze = material("HELIO · Brushed Bronze", (0.56, 0.26, 0.07), 0.85, 0.24)
    dark = material("HELIO · Graphite", (0.026, 0.038, 0.05), 0.65, 0.28)
    cyan = material("HELIO · Plasma", (0.035, 0.63, 0.7), 0.18, 0.2, 2.5)
    white = material("HELIO · Porcelain", (0.64, 0.69, 0.7), 0.2, 0.25)

    def finish(name, mat, bevel=0):
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(mat)
        if obj.type == "MESH":
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
            if bevel:
                modifier = obj.modifiers.new("Machined Edges", "BEVEL")
                modifier.width, modifier.segments = bevel, 3
        return obj

    for z, radius, depth, mat in ((0.1, 0.92, 0.2, dark), (0.24, 0.81, 0.09, bronze),
                                  (0.34, 0.69, 0.12, dark), (0.43, 0.58, 0.065, white)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=depth, location=(0, 0, z))
        finish("HELIO_Base", mat, 0.025)
    for z in (0.26, 0.42):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.72 if z < 0.3 else 0.53,
            minor_radius=0.014, major_segments=96, minor_segments=12, location=(0, 0, z))
        finish("HELIO_Indicator", cyan)
    for i in range(8):
        angle = i * math.tau / 8
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.032,
            location=(0.79 * math.cos(angle), 0.79 * math.sin(angle), 0.31))
        finish("HELIO_Fastener", bronze)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.115, depth=0.95, location=(0, 0, 0.91))
    finish("HELIO_Spindle", bronze, 0.025)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.34, location=(0, 0, 1.52))
    core = finish("HELIO_PlasmaCore", cyan)
    core.scale = (1, 1, 1.3)
    rings = []
    for i, radius in enumerate((0.61, 0.78, 0.96)):
        bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=0.035,
            major_segments=96, minor_segments=16, location=(0, 0, 1.52))
        ring = finish(f"HELIO_Orbit_{i + 1}", bronze)
        ring.rotation_euler = (0.3 + i * 0.58, 0.2 + i * 0.4, i * 0.5)
        rings.append(ring)
    # Rigid mechanical rig: ring objects follow the named orbit bone.
    armature = bpy.data.armatures.new("HELIO_Rig")
    rig = bpy.data.objects.new("HELIO_Rig", armature)
    collection.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    bone = armature.edit_bones.new("Orbit")
    bone.head, bone.tail = (0, 0, 1.52), (0, 0, 1.95)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    for ring in rings:
        world = ring.matrix_world.copy()
        ring.parent, ring.parent_type, ring.parent_bone = rig, 'BONE', "Orbit"
        ring.matrix_world = world
    pose = rig.pose.bones["Orbit"]
    pose.rotation_mode = 'XYZ'
    pose.rotation_euler.z = 0
    pose.keyframe_insert(data_path="rotation_euler", frame=1)
    pose.rotation_euler.z = math.tau
    pose.keyframe_insert(data_path="rotation_euler", frame=120)
    scene.frame_start, scene.frame_end = 1, 120
    scene.frame_set(1)
    created = list(set(bpy.data.objects) - before)
    for obj in created:
        if obj.name not in collection.objects:
            collection.objects.link(obj)
        for owner in list(obj.users_collection):
            if owner != collection:
                owner.objects.unlink(obj)
    folder = Path(folder) if folder else output_directory(scene)
    folder.mkdir(parents=True, exist_ok=True)
    export_objects(folder / "HELIO.glb", created)
    report = geometry_report(created)
    report.update(example="HELIO offline procedural example", generated_by_ai=False,
                  rig="One bone driving three orbital rings", animation_frames=[1, 120],
                  export=str((folder / "HELIO.glb").resolve()))
    report_path = folder / "run.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    scene.ama_props.workflow_report = str(report_path.resolve())
    scene.ama_props.workflow_status = "Offline example created: PBR + rig + animation + GLB + report"
    bpy.ops.object.select_all(action='DESELECT')
    for obj in created:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    return collection, folder


def setup_presentation(scene):
    ground = material("Stage · Slate", (0.018, 0.025, 0.033), 0.25, 0.32)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.03))
    bpy.context.object.name = "Presentation Ground"
    bpy.context.object.data.materials.append(ground)
    camera_data = bpy.data.cameras.new("Studio Camera")
    camera = bpy.data.objects.new("Studio Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (4.2, -6.5, 3.4)
    camera.rotation_euler = (Vector((0, 0, 1.05)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.type, camera_data.ortho_scale = 'ORTHO', 3.7
    scene.camera = camera
    for name, position, color, energy, size in (
        ("Key", (1.5, -3, 5), (0.67, 0.85, 1), 1000, 4),
        ("Rim", (-2, 1.5, 3.5), (0.18, 0.8, 1), 1400, 3),
        ("Warm", (3, 2, 2), (1, 0.43, 0.18), 1000, 2)):
        light_data = bpy.data.lights.new(name, 'AREA')
        light_data.energy, light_data.color, light_data.shape, light_data.size = energy, color, 'DISK', size
        light = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light)
        light.location = position
        light.rotation_euler = (Vector((0, 0, 1.2)) - light.location).to_track_quat('-Z', 'Y').to_euler()
    scene.world = bpy.data.worlds.new("Studio World")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.08, 0.12, 0.18, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1100, 1100
    scene.render.resolution_percentage = 100
