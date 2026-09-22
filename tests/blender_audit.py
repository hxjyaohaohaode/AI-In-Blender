"""Production regressions executed inside each real Blender in the version matrix."""

import json
from pathlib import Path
import random
import bpy
from ai_modeling_assistant.blender import runtime
from ai_modeling_assistant.blender.compat import set_geometry_input
from ai_modeling_assistant.blender.quality import evaluate
from ai_modeling_assistant.blender.revision import (
    fingerprint,
    ensure_ids,
    region_preserved,
    object_dependencies,
)
from ai_modeling_assistant.core.agents import Workflow


class ProductionAuditMixin:
    def test_audit_camera_focus_target_must_be_in_scope(self):
        target = self.cube()
        bpy.ops.object.camera_add()
        camera = bpy.context.object
        camera.data.dof.focus_object = target
        self.assertIn(target, object_dependencies([camera]))

    def test_audit_unsupported_render_settings_are_not_silently_discarded(self):
        from ai_modeling_assistant.blender.staging import SceneJob

        obj = self.cube()
        job = SceneJob(
            "import bpy\nbpy.context.scene.cycles.samples = 123",
            [obj],
            self.directory.name,
            contract={"allow_scene_settings": True},
            render=False,
        )
        result = self.wait_scene_job(job)
        self.assertIn("Unsupported shared scene settings", result["error"])

    def test_audit_material_preview_is_real_and_labeled(self):
        from ai_modeling_assistant.blender.staging import SceneJob

        obj = self.cube()
        mat = bpy.data.materials.new("Rendered Material")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
            0.02,
            0.2,
            0.8,
            1,
        )
        obj.data.materials.append(mat)
        job = SceneJob("pass", [obj], self.directory.name, contract={"require_materials": True})
        result = self.wait_scene_job(job)
        self.assertFalse(result.get("error"), result)
        material = next(v for v in result["evidence_views"] if "Cycles" in v["kind"])
        image = bpy.data.images.load(material["path"])
        try:
            self.assertEqual(tuple(image.size), (384, 384))
            red = list(image.pixels)[::4]  # RNA arrays gained stepped slices only in 5.2.
            self.assertGreater(max(red) - min(red), 0.05)
        finally:
            bpy.data.images.remove(image)

    def test_audit_explicit_lighting_task_commits_world_camera_and_settings(self):
        from ai_modeling_assistant.blender.staging import SceneJob
        from ai_modeling_assistant.blender.scene_state import capture, apply

        obj = self.cube()
        before, old_world = capture(self.scene, [obj]), self.scene.world
        code = """import bpy
bpy.context.scene.render.fps = 30
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.frame_end = 44
bpy.context.scene.world.use_nodes = True
bpy.context.scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.91
bpy.ops.object.camera_add(location=(4,-4,3))
bpy.context.scene.camera = bpy.context.object
"""
        collection = bpy.data.collections.new("Lighting Audit")
        self.scene.collection.children.link(collection)
        try:
            job = SceneJob(
                code,
                [obj],
                self.directory.name,
                contract={"allow_scene_settings": True},
                render=False,
            )
            result = self.wait_scene_job(job)
            self.assertFalse(result.get("error"), result)
            loaded = job.commit(result, collection)
            self.assertEqual(self.scene.render.fps, 30)
            self.assertEqual(self.scene.render.resolution_x, 800)
            self.assertEqual(self.scene.frame_end, 44)
            self.assertIn(self.scene.camera, loaded)
            self.assertAlmostEqual(
                self.scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value,
                0.91,
                places=5,
            )
        finally:
            apply(self.scene, before, [], world=old_world)

    def test_audit_unowned_world_edits_are_reported_not_silently_lost(self):
        from ai_modeling_assistant.blender.staging import SceneJob

        obj = self.cube()
        job = SceneJob(
            "import bpy\nbpy.context.scene.render.fps = 37",
            [obj],
            self.directory.name,
            render=False,
        )
        result = self.wait_scene_job(job)
        self.assertIn("allow_scene_settings", result["error"])
        self.assertNotEqual(self.scene.render.fps, 37)

    def test_audit_native_delivery_retains_scene_and_procedural_shader(self):
        from ai_modeling_assistant.blender.compat import export_native_scene

        obj = self.cube()
        mat = bpy.data.materials.new("Procedural Delivery")
        mat.use_nodes = True
        mat.node_tree.nodes.new("ShaderNodeTexNoise")
        obj.data.materials.append(mat)
        before = fingerprint([obj])
        path = export_native_scene(Path(self.directory.name) / "native.blend", [obj])
        with bpy.data.libraries.load(path, link=False) as (source, target):
            target.scenes = source.scenes
        delivered = target.scenes[0]
        try:
            candidate = next(iter(delivered.objects))
            self.assertTrue(
                any(n.type == "TEX_NOISE" for n in candidate.data.materials[0].node_tree.nodes)
            )
            self.assertEqual(delivered.render.fps, self.scene.render.fps)
            self.assertIsNotNone(delivered.world)
            self.assertEqual(fingerprint([obj]), before)
        finally:
            bpy.data.scenes.remove(delivered)

    def test_audit_failed_glb_export_preserves_previous_delivery(self):
        from unittest.mock import patch
        from ai_modeling_assistant.blender.compat import export_objects

        obj = self.cube()
        path = Path(self.directory.name) / "retained.glb"
        path.write_bytes(b"previous delivery")
        with patch(
            "ai_modeling_assistant.core.gltf.inspect_glb", side_effect=ValueError("invalid export")
        ):
            with self.assertRaisesRegex(ValueError, "invalid export"):
                export_objects(path, [obj])
        self.assertEqual(path.read_bytes(), b"previous delivery")

    def cube(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        ensure_ids([obj])
        return obj

    def geometry_modifier(self, obj, socket_type="NodeSocketFloat"):
        group = bpy.data.node_groups.new("Audit Geometry", "GeometryNodeTree")
        if bpy.app.version >= (4, 0, 0):
            group.interface.new_socket(
                name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
            )
            group.interface.new_socket(
                name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
            )
            socket = group.interface.new_socket(
                name="Control", in_out="INPUT", socket_type=socket_type
            )
        else:
            group.inputs.new("NodeSocketGeometry", "Geometry")
            group.outputs.new("NodeSocketGeometry", "Geometry")
            socket = group.inputs.new(socket_type, "Control")
        source, target = group.nodes.new("NodeGroupInput"), group.nodes.new("NodeGroupOutput")
        group.links.new(source.outputs["Geometry"], target.inputs["Geometry"])
        modifier = obj.modifiers.new("Audit", "NODES")
        modifier.node_group = group
        return modifier, socket.identifier

    def test_audit_geometry_socket_helper_and_revision(self):
        obj = self.cube()
        modifier, identifier = self.geometry_modifier(obj)
        set_geometry_input(modifier, identifier, 1.0)
        before = fingerprint([obj])
        set_geometry_input(modifier, identifier, 2.0)
        self.assertNotEqual(before, fingerprint([obj]))
        with self.assertRaises(ValueError):
            set_geometry_input(modifier, "missing_socket", 1.0)

    def test_audit_geometry_node_object_input_is_a_dependency(self):
        obj = self.cube()
        external = self.cube()
        modifier, identifier = self.geometry_modifier(obj, "NodeSocketObject")
        set_geometry_input(modifier, identifier, external)
        self.assertIn(external, object_dependencies([obj]))

    def test_audit_color_ramp_changes_invalidate_revision(self):
        obj = self.cube()
        mat = bpy.data.materials.new("Audit Ramp")
        mat.use_nodes = True
        obj.data.materials.append(mat)
        node = mat.node_tree.nodes.new("ShaderNodeValToRGB")
        before = fingerprint([obj])
        node.color_ramp.elements[0].color = (0.8, 0.2, 0.4, 1)
        self.assertNotEqual(before, fingerprint([obj]))

    def test_audit_repeated_image_paint_invalidates_revision(self):
        obj = self.cube()
        mat = bpy.data.materials.new("Audit Paint")
        mat.use_nodes = True
        obj.data.materials.append(mat)
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.new("Paint", width=2, height=2)
        node.image.pixels[0] = 0.2
        before = fingerprint([obj])
        node.image.pixels[0] = 0.9
        self.assertNotEqual(before, fingerprint([obj]))

    def test_audit_precise_region_protects_generic_attributes(self):
        obj = self.cube()
        attr = obj.data.attributes.new("production_weight", "FLOAT", "POINT")
        attr.data[7].value = 0.3
        candidate = obj.copy()
        candidate.data = obj.data.copy()
        # Use a replacement layer to avoid shared copy-on-write storage in 3.6.
        candidate.data.attributes.remove(candidate.data.attributes["production_weight"])
        other = candidate.data.attributes.new("production_weight", "FLOAT", "POINT")
        other.data[7].value = 0.7
        with self.assertRaisesRegex(ValueError, "attributes outside"):
            region_preserved(
                [obj], [candidate], [{"asset_id": obj["ama_asset_id"], "vertices": [0]}]
            )

    def test_audit_uv_quality_rejects_existing_but_collapsed_map(self):
        obj = self.cube()
        for point in obj.data.uv_layers.active.data:
            point.uv = (0, 0)
        report = evaluate([obj], {"require_uv": True})
        self.assertFalse(report["passed"])
        self.assertTrue(any("collapsed UV" in e for e in report["errors"]))

    def test_audit_material_gate_rejects_disconnected_output_and_missing_texture(self):
        obj = self.cube()
        mat = bpy.data.materials.new("Audit Material")
        mat.use_nodes = True
        obj.data.materials.append(mat)
        mat.node_tree.links.clear()
        self.assertFalse(evaluate([obj], {"require_materials": True})["passed"])
        tree = mat.node_tree
        bsdf = tree.nodes.get("Principled BSDF")
        tree.links.new(bsdf.outputs[0], tree.nodes.get("Material Output").inputs["Surface"])
        tex = tree.nodes.new("ShaderNodeTexImage")
        tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        report = evaluate([obj], {"require_materials": True})
        self.assertTrue(any("no image" in e for e in report["errors"]))

    def test_audit_animation_gate_requires_real_distinct_bound_keys(self):
        obj = self.cube()
        obj.keyframe_insert("location", frame=1)
        self.assertFalse(evaluate([obj], {"require_animation": True})["passed"])
        obj.location.x = 1
        obj.keyframe_insert("location", frame=10)
        report = evaluate([obj], {"require_animation": True, "animation_range": [1, 10]})
        self.assertTrue(report["passed"], report)
        self.assertFalse(
            evaluate([obj], {"require_animation": True, "animation_range": [1, 20]})["passed"]
        )

    def test_audit_animation_sampling_catches_intermediate_bounds_and_restores_time(self):
        obj = self.cube()
        for frame, scale in ((1, 1), (5, 5), (10, 1)):
            obj.scale = (scale,) * 3
            obj.keyframe_insert("scale", frame=frame)
        self.scene.frame_set(1, subframe=0.25)
        report = evaluate(
            [obj], {"require_animation": True, "animation_range": [1, 10], "max_extent": 3}
        )
        self.assertFalse(report["passed"])
        self.assertIn(5, report["sampled_frames"])
        self.assertEqual(self.scene.frame_current, 1)
        self.assertAlmostEqual(self.scene.frame_subframe, 0.25)
        self.scene.frame_set(1)

    def test_audit_shape_key_animation_is_inspected(self):
        obj = self.cube()
        obj.shape_key_add(name="Basis")
        key = obj.shape_key_add(name="Morph")
        key.value = 0
        key.keyframe_insert("value", frame=1)
        key.value = 1
        key.keyframe_insert("value", frame=10)
        report = evaluate([obj], {"require_animation": True, "animation_range": [1, 10]})
        self.assertTrue(report["passed"], report)

    def test_audit_visual_approval_is_invalidated_by_fps_change(self):
        obj = self.cube()
        workflow = Workflow.from_plan(
            "cube", {"tasks": [{"id": "export", "expert": "exporter", "prompt": "export"}]}
        )
        run = runtime.StudioRun(self.scene, workflow, targets=[obj])
        self.scene.ama_props.require_visual_review = True
        run.start()
        run.tick()
        original = self.scene.render.fps
        try:
            self.scene.render.fps = original + 1
            with self.assertRaisesRegex(ValueError, "scene settings changed"):
                run.approve_quality()
            self.assertFalse((run.folder / "asset.glb").exists())
            self.assertIsNotNone(run.pending_quality)
        finally:
            self.scene.render.fps = original
            run.cancel()

    def test_audit_checkpoint_rejects_scene_setting_changes(self):
        obj = self.cube()
        workflow = Workflow.from_plan(
            "cube", {"tasks": [{"id": "inspect", "expert": "inspector", "prompt": "inspect"}]}
        )
        run = runtime.StudioRun(self.scene, workflow, targets=[obj])
        run.start()
        run.tick()
        run.tick()
        original = self.scene.render.resolution_x
        try:
            self.scene.render.resolution_x = original + 10
            with self.assertRaisesRegex(ValueError, "scene settings differ"):
                runtime.resume_checkpoint(self.scene, str(run.folder / "run.json"))
        finally:
            self.scene.render.resolution_x = original

    def test_audit_terrain_honors_resolution_without_changing_random_state(self):
        before = random.getstate()
        self.assertIn("FINISHED", bpy.ops.ama.generate_terrain(subdivisions=12, size=6))
        obj = bpy.data.objects["Terrain"]
        self.assertEqual(len(obj.data.vertices), 13 * 13)
        self.assertEqual(len(obj.data.polygons), 12 * 12)
        self.assertEqual(random.getstate(), before)

    def test_audit_scatter_follows_actual_sloped_surface(self):
        source = self.cube()
        source.scale = (0.1, 0.2, 0.3)
        mesh = bpy.data.meshes.new("Slope")
        mesh.from_pydata([(0, 0, 0), (3, 0, 3), (0, 3, 0)], [], [(0, 1, 2)])
        target = bpy.data.objects.new("Slope", mesh)
        self.scene.collection.objects.link(target)
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        before = random.getstate()
        self.assertIn("FINISHED", bpy.ops.ama.scatter_objects(count=20, scale_variation=0))
        scattered = [o for o in self.scene.objects if "_scatter_" in o.name]
        self.assertEqual(len(scattered), 20)
        for obj in scattered:
            x, y, z = obj.matrix_world.translation
            self.assertAlmostEqual(z, x, places=5)
            self.assertLessEqual(x + y, 3.00001)
            self.assertAlmostEqual(obj.scale.y, 0.2, places=5)
        self.assertEqual(random.getstate(), before)

    def test_audit_audio_snapshot_detects_changed_source(self):
        path = Path(self.directory.name) / "audit.wav"
        path.write_bytes(b"original audio")
        self.scene.ama_props.input_audio = str(path)
        try:
            workflow = Workflow.from_plan(
                "transcribe",
                {"tasks": [{"id": "speech", "expert": "transcriber", "prompt": "transcribe"}]},
            )
            self.profile("transcription")
            run = runtime.StudioRun(self.scene, workflow)
            path.write_bytes(b"changed audio")
            with self.assertRaisesRegex(ValueError, "attachment changed"):
                run.preflight()
            self.assertEqual(json.loads(json.dumps(run.input_snapshot))["audio"]["bytes"], 14)
        finally:
            self.scene.ama_props.input_audio = ""
