"""Run with blender --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from blender_audit import ProductionAuditMixin
import bpy
import addon_utils
import ai_modeling_assistant as addon
from ai_modeling_assistant.blender import runtime, state
from ai_modeling_assistant.blender.registration import ALL_CLASSES
from ai_modeling_assistant.blender.execution import CodeExecutor
from ai_modeling_assistant.blender.compat import export_objects
from ai_modeling_assistant.blender.quality import MeshAnalyzer
from ai_modeling_assistant.core.agents import Workflow
from ai_modeling_assistant.core.process import python_executable
from ai_modeling_assistant.data.catalog import QUICK_BUILDS, MATERIAL_PRESETS


def pump(run, until=None):
    deadline = time.monotonic() + 100
    while run.running and time.monotonic() < deadline:
        run.tick()
        if until and until():
            return
        time.sleep(0.02)
    if run.running:
        run.cancel()
        raise AssertionError("Workflow exceeded the local integration-test deadline")


class LayoutProbe:
    icons = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())

    def __getattr__(self, name):
        def call(*args, **kwargs):
            icon = kwargs.get("icon")
            if icon is not None and icon not in self.icons:
                raise AssertionError(f"Unknown UI icon: {icon}")
            if name == "prop" and not hasattr(args[0], args[1]):
                raise AssertionError(f"Unknown UI property: {args[1]}")
            if name == "operator":
                module, operator = args[0].split(".")
                getattr(getattr(bpy.ops, module), operator).get_rna_type()
                return SimpleNamespace()
            return LayoutProbe()

        return call


class BlenderTests(ProductionAuditMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addon_utils.enable("ai_modeling_assistant", default_set=True)
        cls.server = subprocess.Popen(
            [python_executable(), str(ROOT / "tests/fixtures/provider_server.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        cls.base = f"http://127.0.0.1:{int(cls.server.stdout.readline())}"
        cls.directory = tempfile.TemporaryDirectory(prefix="ai_blender_validation_")
        os.environ["AI_IN_BLENDER_MEMORY_DB"] = str(Path(cls.directory.name) / "memory.sqlite3")

    @classmethod
    def tearDownClass(cls):
        runtime.shutdown()
        # VSE decoders retain open video handles on Windows until strips are released.
        for scene in bpy.data.scenes:
            if scene.sequence_editor:
                scene.sequence_editor_clear()
        cls.server.terminate()
        cls.server.wait(timeout=5)
        cls.server.stdout.close()
        addon_utils.disable("ai_modeling_assistant", default_set=True)
        cls.directory.cleanup()
        os.environ.pop("AI_IN_BLENDER_MEMORY_DB", None)

    def setUp(self):
        runtime.shutdown()
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        self.scene = bpy.context.scene
        if self.scene.sequence_editor:
            self.scene.sequence_editor_clear()
        props = self.scene.ama_props
        props.api_preset = "custom"
        props.api_url, props.model, props.api_key = self.base, "fixture", "fixture-secret"
        props.artifact_dir = self.directory.name
        props.review_code = False
        props.require_visual_review = False
        props.attachments_json = "[]"
        props.region_json = ""
        props.context_budget = 12000
        props.memory_enabled = True
        props.auto_run_plan = False
        props.include_history = False
        props.auto_fix, props.max_repairs = True, 2
        state.preferences().providers.clear()

    def test_persistent_dialogue_delivers_real_multiturn_context(self):
        from ai_modeling_assistant.blender import conversation

        props = self.scene.ama_props
        props.project_id = props.thread_id = ""
        for text in ("Use a blue material", "Make the stand 20 cm wide"):
            dialogue = conversation.send(self.scene, text)
            deadline = time.monotonic() + 10
            while dialogue.tick() and time.monotonic() < deadline:
                time.sleep(0.02)
            conversation._jobs.pop(self.scene.as_pointer(), None)
        with conversation.store() as db:
            turns = db.turns(props.thread_id)
        self.assertEqual(len(turns), 4)
        self.assertIn("received 5 messages", turns[-1]["content"])

    def test_isolated_commit_rejects_human_edit_without_overwriting(self):
        from ai_modeling_assistant.blender.staging import SceneJob

        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        collection = bpy.data.collections.new("ConflictTest")
        self.scene.collection.children.link(collection)
        job = SceneJob(
            "import bpy\nbpy.context.object.scale.x=2", [obj], self.directory.name, render=False
        )
        obj.location.x = 7
        result = None
        deadline = time.monotonic() + 30
        while result is None and time.monotonic() < deadline:
            result = job.poll()
            time.sleep(0.03)
        self.assertIsNotNone(result)
        self.assertNotIn("error", result)
        with self.assertRaisesRegex(ValueError, "Human edit conflict"):
            job.commit(result, collection)
        self.assertEqual(obj.location.x, 7)
        self.assertEqual(obj.scale.x, 1)

    def test_native_quality_blocks_empty_mesh_and_contract_violation(self):
        from ai_modeling_assistant.blender.quality import evaluate

        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        self.assertFalse(evaluate([obj], {"max_vertices": 4})["passed"])
        self.assertFalse(
            evaluate([obj], {"bounds_min": [-0.5, -0.5, -0.5], "bounds_max": [0.5, 0.5, 0.5]})[
                "passed"
            ]
        )
        self.assertFalse(
            evaluate([obj], {"anchor_object": obj.name, "anchor_position": [9, 0, 0]})["passed"]
        )
        obj.data.clear_geometry()
        self.assertFalse(evaluate([obj], {})["passed"])

    def test_visual_gate_binds_to_current_revision(self):
        props = self.scene.ama_props
        props.require_visual_review = True
        workflow = Workflow.from_plan(
            "cube",
            {
                "tasks": [
                    {"id": "mesh", "expert": "modeler", "prompt": "cube"},
                    {
                        "id": "export",
                        "expert": "exporter",
                        "prompt": "export",
                        "depends_on": ["mesh"],
                    },
                ]
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run, until=lambda: run.pending_quality is not None)
        self.assertFalse((run.folder / "asset.glb").exists())
        run.objects()[0].scale.x = 1.5
        bpy.context.view_layer.update()
        with self.assertRaisesRegex(ValueError, "changed since inspection"):
            run.approve_quality()
        run.approve_quality()
        pump(run)
        self.assertTrue((run.folder / "asset.glb").exists())

    def test_independent_parts_run_concurrently_and_assemble(self):
        workflow = Workflow.from_plan(
            "two independent components",
            {
                "assembly": {"units": "meters", "up": "Z"},
                "tasks": [
                    {
                        "id": "left",
                        "expert": "modeler",
                        "prompt": "cube",
                        "contract": {"part_id": "left"},
                    },
                    {
                        "id": "right",
                        "expert": "modeler",
                        "prompt": "cube",
                        "contract": {"part_id": "right"},
                    },
                    {
                        "id": "inspect",
                        "expert": "inspector",
                        "prompt": "both parts",
                        "depends_on": ["left", "right"],
                    },
                ],
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertTrue(workflow.complete, self.scene.ama_props.workflow_status)
        self.assertEqual(len(run.objects()), 2)
        self.assertEqual(run.peak_parallel, 2)
        self.assertEqual(run.calls, 2)

    def test_precise_region_rejects_out_of_bounds_vertex_edit(self):
        from ai_modeling_assistant.blender.revision import ensure_ids, region_preserved

        bpy.ops.mesh.primitive_cube_add()
        source = bpy.context.object
        ensure_ids([source])
        candidate = source.copy()
        candidate.data = source.data.copy()
        candidate.data.vertices[1].co.x += 1
        with self.assertRaisesRegex(ValueError, "outside the selected region"):
            region_preserved(
                [source], [candidate], [{"asset_id": source["ama_asset_id"], "vertices": [0]}]
            )

    def test_sketch_uses_native_grease_pencil(self):
        from ai_modeling_assistant.blender.inputs import new_sketch

        obj = new_sketch()
        self.assertIn(obj.type, {"GREASEPENCIL", "GPENCIL"})
        bpy.ops.object.mode_set(mode="OBJECT")

    def test_multiple_workflows_keep_separate_assets_and_focus(self):
        workflow = lambda: Workflow.from_plan(
            "separate cube", {"tasks": [{"id": "mesh", "expert": "modeler", "prompt": "cube"}]}
        )
        first = runtime.StudioRun(self.scene, workflow())
        first.start()
        second = runtime.StudioRun(self.scene, workflow())
        second.start()
        self.assertIs(runtime.current(self.scene), second)
        deadline = time.monotonic() + 40
        while runtime.busy() and time.monotonic() < deadline:
            runtime._tick()
            time.sleep(0.03)
        self.assertTrue(first.workflow.complete)
        self.assertTrue(second.workflow.complete)
        self.assertEqual(len(first.objects()), 1)
        self.assertEqual(len(second.objects()), 1)
        self.assertNotEqual(first.objects()[0], second.objects()[0])
        runtime.focus(first)
        self.assertIs(runtime.current(self.scene), first)

    def test_vision_reviewer_receives_real_render_evidence(self):
        profile = self.profile("chat")
        profile.capabilities = {"chat", "vision"}
        workflow = Workflow.from_plan(
            "cube",
            {
                "tasks": [
                    {"id": "mesh", "expert": "modeler", "prompt": "cube"},
                    {
                        "id": "review",
                        "expert": "reviewer",
                        "prompt": "check geometry",
                        "depends_on": ["mesh"],
                    },
                ]
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertTrue(workflow.complete, self.scene.ama_props.workflow_status)
        review = workflow.get("review").result
        self.assertIn("preview", review["evidence_type"])
        self.assertTrue(Path(review["preview"]).is_file())
        self.assertGreaterEqual(review["reviewed_view_count"], 2)
        self.assertEqual(len(review["evidence_views"]), review["reviewed_view_count"])
        self.assertTrue(all(Path(p).is_file() for p in review["previews"]))
        self.assertEqual(len(list(Path(review["preview"]).parent.glob("preview*.png"))), 3)

    def test_resume_checkpoint_preserves_successful_steps(self):
        workflow = Workflow.from_plan(
            "REJECT_REVIEW",
            {
                "tasks": [
                    {"id": "mesh", "expert": "modeler", "prompt": "cube"},
                    {
                        "id": "review",
                        "expert": "reviewer",
                        "prompt": "review",
                        "depends_on": ["mesh"],
                    },
                ]
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertFalse(workflow.complete)
        checkpoint = run.folder / "run.json"
        runtime.shutdown()
        data = json.loads(checkpoint.read_text())
        data["goal"] = "Accept this fixture"
        checkpoint.write_text(json.dumps(data), encoding="utf-8")
        resumed = runtime.resume_checkpoint(self.scene, str(checkpoint))
        pump(resumed)
        self.assertTrue(resumed.workflow.complete)
        self.assertEqual(len(resumed.objects()), 1)
        self.assertEqual(resumed.workflow.get("mesh").attempts, 1)

    def test_semantic_compression_uses_model_and_retains_original_turns(self):
        from ai_modeling_assistant.blender import conversation

        props = self.scene.ama_props
        props.project_id = props.thread_id = ""
        props.context_budget = 2000
        props.memory_enabled = False
        with conversation.store() as db:
            _, thread = conversation.identity(self.scene, db)
            for i in range(12):
                db.append(
                    thread,
                    "user" if i % 2 == 0 else "assistant",
                    f"Detail {i}: " + "blue material " * 80,
                )
        dialogue = conversation.send(self.scene, "Keep all agreed dimensions")
        self.assertEqual(dialogue.stage, "compress")
        deadline = time.monotonic() + 15
        while dialogue.tick() and time.monotonic() < deadline:
            time.sleep(0.02)
        conversation._jobs.pop(self.scene.as_pointer(), None)
        with conversation.store() as db:
            self.assertEqual(len(db.turns(thread)), 14)
            self.assertEqual(db.summary(thread)["mode"], "semantic")

    def test_scene_process_deadline_terminates_without_live_changes(self):
        from ai_modeling_assistant.blender.staging import SceneJob

        job = SceneJob("while True:\n    x=1", [], self.directory.name, render=False, timeout=-1)
        self.assertIn("deadline", job.poll()["error"])
        self.assertIsNotNone(job.process.poll())
        self.assertEqual(len(bpy.data.objects), 0)

    def test_scene_commit_waits_for_interactive_edit_mode_to_end(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        run = runtime.start_reviewed_code(
            self.scene, "import bpy\nbpy.context.object.scale.x=2", [obj]
        )
        bpy.ops.object.mode_set(mode="EDIT")
        pump(run, until=lambda: run.staged_result is not None)
        self.assertEqual(obj.scale.x, 1)
        bpy.ops.object.mode_set(mode="OBJECT")
        pump(run)
        self.assertTrue(run.workflow.complete)
        self.assertEqual(run.objects()[0].scale.x, 2)

    def test_nested_node_changes_invalidate_content_fingerprint(self):
        from ai_modeling_assistant.blender.revision import fingerprint, ensure_ids

        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        ensure_ids([obj])
        material = bpy.data.materials.new("NodeFingerprint")
        material.use_nodes = True
        obj.data.materials.append(material)
        group = bpy.data.node_groups.new("NestedMaterial", "ShaderNodeTree")
        nested = material.node_tree.nodes.new("ShaderNodeGroup")
        nested.node_tree = group
        node = group.nodes.new("ShaderNodeValue")
        before = fingerprint([obj])
        node.outputs[0].default_value = 0.37
        # Output socket defaults must be included, not only input socket values.
        self.assertNotEqual(before, fingerprint([obj]))
        before = fingerprint([obj])
        material.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (
            0.17,
            0.23,
            0.91,
            1,
        )
        self.assertNotEqual(before, fingerprint([obj]))

    def profile(self, protocol):
        item = state.preferences().providers.add()
        item.name, item.protocol = protocol, protocol
        item.base_url, item.model, item.api_key = self.base, "fixture", "fixture-secret"
        item.options_json = (
            '{"poll_interval": 0.1, "response_format": "wav"}'
            if protocol == "speech"
            else '{"poll_interval":0.1}'
        )
        return item

    def test_all_original_quick_builds(self):
        for name, preset in QUICK_BUILDS.items():
            with self.subTest(preset=name):
                for obj in list(bpy.data.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                success, message = CodeExecutor.execute(preset["code"])
                self.assertTrue(success, message)
                self.assertGreater(len(bpy.data.objects), 0)

    def test_all_panel_draw_functions(self):
        bpy.ops.mesh.primitive_cube_add()
        for cls in ALL_CLASSES:
            if issubclass(cls, bpy.types.Panel):
                with self.subTest(panel=cls.__name__):
                    cls.draw(SimpleNamespace(layout=LayoutProbe()), bpy.context)
        from ai_modeling_assistant.blender.ui_studio import draw_providers

        self.profile("chat")
        draw_providers(LayoutProbe(), state.preferences())

    def test_material_presets(self):
        bpy.ops.mesh.primitive_cube_add()
        for name in MATERIAL_PRESETS:
            with self.subTest(material=name):
                self.assertIn("FINISHED", bpy.ops.ama.apply_material(material_name=name))

    def test_normals_are_not_classified_by_downward_direction(self):
        bpy.ops.mesh.primitive_cube_add()
        self.assertEqual(MeshAnalyzer.analyze(bpy.context.object)["possibly_flipped_faces"], 0)
        self.assertIn("FINISHED", bpy.ops.ama.recalculate_normals())

    def test_generated_code_failure_cleans_new_objects_and_restores_mesh(self):
        bpy.ops.mesh.primitive_cube_add()
        original = bpy.context.object
        vertices = len(original.data.vertices)
        ok, _ = CodeExecutor.execute(
            "import bpy\nbpy.ops.mesh.primitive_uv_sphere_add()\nraise ValueError('stop')"
        )
        self.assertFalse(ok)
        self.assertEqual(len(bpy.data.objects), 1)
        self.assertEqual(len(original.data.vertices), vertices)

    def test_python_loop_has_an_execution_budget(self):
        ok, error = CodeExecutor.execute("while True:\n    x=1", timeout=0.05)
        self.assertFalse(ok)
        self.assertIn("execution budget", error)

    def test_actual_export_preserves_source_and_selection(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        obj.scale = (2, 3, 4)
        modifier = obj.modifiers.new("Bevel", "BEVEL")
        for fmt in ("glb", "obj", "stl", "fbx"):
            with self.subTest(format=fmt):
                path = Path(self.directory.name) / ("asset." + fmt)
                export_objects(path, [obj], fmt, "unreal")
                self.assertTrue(path.is_file())
                self.assertEqual(tuple(obj.scale), (2, 3, 4))
                self.assertIn(modifier, list(obj.modifiers))
                self.assertEqual(bpy.context.selected_objects, [obj])

    def test_scene_key_is_not_an_id_property(self):
        self.scene.ama_props.api_key = "not-to-be-saved"
        self.assertEqual(self.scene.ama_props.api_key, "not-to-be-saved")
        self.assertNotIn("api_key", self.scene.ama_props.keys())
        item = self.profile("chat")
        self.assertNotIn("api_key", item.keys())

    def test_expert_specific_provider_overrides_general_provider(self):
        general = self.profile("chat")
        general.name = "General model"
        specialist = self.profile("chat")
        specialist.name = "Modeling specialist"
        specialist.experts = {"modeler"}
        self.assertEqual(state.provider_for("chat", "modeler").name, "Modeling specialist")
        self.assertEqual(state.provider_for("chat", "material").name, "General model")
        general.enabled = False
        with self.assertRaises(ValueError):
            state.provider_for("chat", "material")

    def test_legacy_key_migration(self):
        self.scene.ama_props["api_key"] = "legacy-saved-key"
        state.migrate_legacy_secrets()
        self.assertNotIn("api_key", self.scene.ama_props.keys())
        self.assertEqual(self.scene.ama_props.api_key, "legacy-saved-key")

    def test_video_and_world_bridge_import(self):
        profile = self.profile("bridge")
        profile.capabilities = {"world", "video"}
        workflow = Workflow.from_plan(
            "world and video",
            {
                "tasks": [
                    {"id": "world", "expert": "world", "prompt": "scene"},
                    {"id": "video", "expert": "video", "prompt": "clip", "depends_on": ["world"]},
                ]
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertTrue(workflow.complete, self.scene.ama_props.workflow_status)
        editor = self.scene.sequence_editor
        strips = editor.strips if hasattr(editor, "strips") else editor.sequences
        self.assertTrue(any(s.type == "MOVIE" for s in strips))

    def test_planning_through_export(self):
        self.scene.ama_props.workflow_goal = "Build a blue cube and export it"
        planning = runtime.start_plan(self.scene)
        pump(planning)
        self.assertEqual(len(planning.workflow.tasks), 5)
        run = runtime.run_plan(self.scene)
        pump(run)
        self.assertTrue(run.workflow.complete, self.scene.ama_props.workflow_status)
        self.assertEqual(len(run.objects()), 1)
        self.assertTrue((run.folder / "asset.glb").is_file())
        self.assertTrue(json.loads((run.folder / "run.json").read_text())["complete"])

    def test_repair_applies_corrected_code_exactly_once(self):
        workflow = Workflow.from_plan(
            "FAIL_ONCE", {"tasks": [{"id": "mesh", "expert": "modeler", "prompt": "FAIL_ONCE"}]}
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertTrue(workflow.complete, self.scene.ama_props.workflow_status)
        self.assertEqual(len(run.objects()), 1)
        self.assertNotIn("Partial", bpy.data.objects)
        self.assertEqual(run.repairs["mesh"], 1)

    def test_code_review_pauses_before_any_scene_change(self):
        run = runtime.start_single(self.scene, "Create a cube")
        pump(run, until=lambda: run.pending_code is not None)
        self.assertEqual(len(run.objects()), 0)
        self.scene.ama_props.last_code += "\nbpy.context.object.name='ReviewedCube'"
        run.accept_code()
        pump(run)
        self.assertTrue(run.workflow.complete)
        self.assertIn("ReviewedCube", bpy.data.objects)

    def test_media_models_import_into_blender(self):
        for protocol in ("meshy", "images", "speech"):
            self.profile(protocol)
        workflow = Workflow.from_plan(
            "Generate media",
            {
                "tasks": [
                    {"id": "model", "expert": "model3d", "prompt": "triangle"},
                    {
                        "id": "image",
                        "expert": "image",
                        "prompt": "reference",
                        "depends_on": ["model"],
                    },
                    {"id": "voice", "expert": "speech", "prompt": "hello", "depends_on": ["image"]},
                ]
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertTrue(workflow.complete, self.scene.ama_props.workflow_status)
        self.assertTrue(any(o.type == "MESH" for o in run.objects()))
        self.assertTrue(any(o.type == "EMPTY" for o in run.objects()))
        self.assertIsNotNone(self.scene.sequence_editor)

    def test_failed_review_blocks_export_and_retry_keeps_geometry(self):
        workflow = Workflow.from_plan(
            "REJECT_REVIEW",
            {
                "tasks": [
                    {"id": "mesh", "expert": "modeler", "prompt": "cube"},
                    {
                        "id": "review",
                        "expert": "reviewer",
                        "prompt": "review",
                        "depends_on": ["mesh"],
                    },
                    {
                        "id": "export",
                        "expert": "exporter",
                        "prompt": "export",
                        "depends_on": ["review"],
                    },
                ]
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertFalse(workflow.complete)
        self.assertEqual(workflow.get("export").status, "blocked")
        self.assertFalse((run.folder / "asset.glb").exists())
        workflow.goal = "Accept this fixture"
        self.assertIn("FINISHED", bpy.ops.ama.retry_workflow())
        pump(run)
        self.assertTrue(workflow.complete)
        self.assertEqual(len(run.objects()), 1)
        self.assertEqual(workflow.get("mesh").attempts, 1)

    def test_scene_change_cancels_pending_request(self):
        self.scene.ama_props.model = "slow"
        run = runtime.start_single(self.scene, "cube")
        run.tick()
        other = bpy.data.scenes.new("OtherScene")
        bpy.context.window.scene = other
        self.assertFalse(run.tick())
        self.assertFalse(run.running)
        bpy.context.window.scene = self.scene
        bpy.data.scenes.remove(other)

    def test_offline_example_has_material_rig_animation_and_export(self):
        from ai_modeling_assistant.blender.demo import build_demo

        collection, folder = build_demo(self.scene, Path(self.directory.name) / "demo")
        self.assertTrue((folder / "HELIO.glb").is_file())
        self.assertTrue(any(o.type == "ARMATURE" and o.animation_data for o in collection.objects))
        self.assertTrue(all(o.data.materials for o in collection.objects if o.type == "MESH"))

    def test_register_unregister_repeatably(self):
        count = len(ALL_CLASSES)
        self.assertEqual(sum(c.is_registered for c in ALL_CLASSES), count)
        addon.unregister()
        self.assertFalse(hasattr(bpy.types.Scene, "ama_props"))
        addon.register()
        self.assertEqual(sum(c.is_registered for c in ALL_CLASSES), count)

    def wait_scene_job(self, job):
        deadline = time.monotonic() + 40
        result = None
        while result is None and time.monotonic() < deadline:
            result = job.poll()
            time.sleep(0.02)
        self.assertIsNotNone(result)
        return result

    def test_compatibility_exception_fallback_executes_in_restricted_python(self):
        ok, output = CodeExecutor.execute(
            "try:\n    missing = {}['legacy']\nexcept KeyError:\n    print('fallback works')"
        )
        self.assertTrue(ok, output)
        self.assertIn("fallback works", output)

    def test_commit_revalidates_evaluated_modifiers_and_named_contract(self):
        from ai_modeling_assistant.blender.staging import SceneJob

        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        collection = bpy.data.collections.new("ContractValidation")
        self.scene.collection.children.link(collection)
        code = "import bpy\nm=bpy.context.object.modifiers.new('detail','SUBSURF')\nm.levels=1"
        job = SceneJob(code, [obj], self.directory.name, render=False)
        result = self.wait_scene_job(job)
        self.assertFalse(result.get("error"), result)
        # Candidate claims PASS, but the host must independently enforce the
        # currently required contract on evaluated (not raw eight-vertex) meshes.
        job.contract = {"max_vertices": 8}
        with self.assertRaisesRegex(ValueError, "Vertex count"):
            job.commit(result, collection)
        self.assertEqual(len(obj.modifiers), 0)
        job.contract = {"required_objects": ["MissingRequiredObject"]}
        with self.assertRaisesRegex(ValueError, "Missing required object"):
            job.commit(result, collection)
        self.assertEqual(len(self.scene.objects), 1)

    def test_unit_change_during_generation_is_a_conflict(self):
        from ai_modeling_assistant.blender.staging import SceneJob

        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        job = SceneJob("pass", [obj], self.directory.name, render=False)
        result = self.wait_scene_job(job)
        before = self.scene.unit_settings.scale_length
        try:
            self.scene.unit_settings.scale_length = before * 2
            with self.assertRaisesRegex(ValueError, "units changed"):
                job.commit(result, self.scene.collection)
        finally:
            self.scene.unit_settings.scale_length = before

    def test_weights_and_attributes_invalidate_stale_fingerprint(self):
        from ai_modeling_assistant.blender.revision import ensure_ids, fingerprint

        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        ensure_ids([obj])
        group = obj.vertex_groups.new(name="bone")
        baseline = fingerprint([obj])
        group.add([0], 0.75, "REPLACE")
        self.assertNotEqual(baseline, fingerprint([obj]))
        attribute = obj.data.attributes.new("production_mask", "FLOAT", "POINT")
        baseline = fingerprint([obj])
        attribute.data[1].value = 0.75
        self.assertNotEqual(baseline, fingerprint([obj]))

    def test_precise_edit_rejects_uv_change_outside_selected_faces(self):
        from ai_modeling_assistant.blender.revision import ensure_ids, fingerprint
        from ai_modeling_assistant.blender.staging import SceneJob

        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        ensure_ids([obj])
        before = [tuple(v.uv) for v in obj.data.uv_layers[0].data]
        # Use the real isolated process. In 3.6 Mesh.copy can share UV storage;
        # an in-process fake candidate would also mutate its alleged original.
        job = SceneJob(
            f"import bpy\nbpy.data.objects[{obj.name!r}].data.uv_layers[0].data[-1].uv.x += 0.4",
            [obj],
            self.directory.name,
            render=False,
            regions=[
                {
                    "asset_id": obj["ama_asset_id"],
                    "vertices": [0],
                    "faces": [0],
                    "fingerprint": fingerprint([obj]),
                }
            ],
        )
        result = self.wait_scene_job(job)
        self.assertEqual(before, [tuple(v.uv) for v in obj.data.uv_layers[0].data])
        with self.assertRaisesRegex(ValueError, "UVs outside"):
            job.commit(result, self.scene.collection)
        self.assertEqual(before, [tuple(v.uv) for v in obj.data.uv_layers[0].data])

    def test_failed_code_restores_original_uv_values(self):
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        before = [tuple(v.uv) for v in obj.data.uv_layers[0].data]
        passed, _ = CodeExecutor.execute(
            "import bpy\nbpy.context.object.data.uv_layers[0].data[-1].uv.x += 0.4\n"
            "raise ValueError('stop before committing')",
            targets=[obj],
        )
        self.assertFalse(passed)
        self.assertEqual(before, [tuple(v.uv) for v in obj.data.uv_layers[0].data])

    def test_scope_requires_external_parent_to_be_explicit(self):
        from ai_modeling_assistant.blender.staging import SceneJob

        bpy.ops.mesh.primitive_cube_add()
        parent = bpy.context.object
        bpy.ops.mesh.primitive_cube_add()
        child = bpy.context.object
        child.parent = parent
        with self.assertRaisesRegex(ValueError, "referenced objects"):
            SceneJob("pass", [child], self.directory.name, render=False)

    def test_failed_branch_does_not_cancel_independent_media_task(self):
        self.profile("chat")
        self.profile("images")
        self.scene.ama_props.auto_fix = False
        workflow = Workflow.from_plan(
            "independent outcomes",
            {
                "tasks": [
                    {"id": "bad", "expert": "modeler", "prompt": "FAIL_ONCE"},
                    {"id": "image", "expert": "image", "prompt": "reference"},
                    {
                        "id": "export",
                        "expert": "exporter",
                        "prompt": "export",
                        "depends_on": ["bad"],
                    },
                ]
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertEqual(workflow.get("bad").status, "failed")
        self.assertEqual(workflow.get("image").status, "succeeded")
        self.assertEqual(workflow.get("export").status, "blocked")
        self.assertFalse((run.folder / "asset.glb").exists())

    def test_export_rechecks_upstream_contract_after_human_edit(self):
        workflow = Workflow.from_plan(
            "bounded cube",
            {
                "tasks": [
                    {
                        "id": "mesh",
                        "expert": "modeler",
                        "prompt": "cube",
                        "contract": {"max_extent": 2},
                    },
                    {
                        "id": "export",
                        "expert": "exporter",
                        "prompt": "export",
                        "depends_on": ["mesh"],
                    },
                ]
            },
        )
        self.scene.ama_props.require_visual_review = True
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run, until=lambda: run.pending_quality is not None)
        run.objects()[0].scale = (5, 5, 5)
        with self.assertRaisesRegex(ValueError, "dimension limit"):
            run.approve_quality()
        self.assertFalse((run.folder / "asset.glb").exists())

    def test_failed_media_import_removes_new_strips_and_preserves_existing(self):
        from ai_modeling_assistant.blender.compat import import_transaction, import_artifact

        fixture = ROOT / "tests/fixtures/video.mp4"
        artifact = {"path": str(fixture), "kind": "video"}
        import_artifact(artifact)
        editor = self.scene.sequence_editor
        strips = editor.strips if hasattr(editor, "strips") else editor.sequences
        original = list(strips)
        with self.assertRaisesRegex(ValueError, "quality rejected"):
            with import_transaction(self.scene):
                import_artifact(artifact)
                raise ValueError("quality rejected")
        self.assertEqual(list(strips), original)

    def test_checkpoint_rejects_tampered_export_even_with_valid_scene(self):
        workflow = Workflow.from_plan(
            "exported cube",
            {
                "tasks": [
                    {"id": "mesh", "expert": "modeler", "prompt": "cube"},
                    {
                        "id": "export",
                        "expert": "exporter",
                        "prompt": "export",
                        "depends_on": ["mesh"],
                    },
                ]
            },
        )
        run = runtime.StudioRun(self.scene, workflow)
        run.start()
        pump(run)
        self.assertTrue(workflow.complete)
        (run.folder / "asset.glb").write_bytes(b"tampered content")
        with self.assertRaisesRegex(ValueError, "content changed"):
            runtime.resume_checkpoint(self.scene, str(run.folder / "run.json"))

    def test_parallel_remote_receipt_survives_cancel_and_cold_recovery(self):
        from urllib.request import urlopen
        from ai_modeling_assistant.core.process import ProcessJob

        profile = self.profile("bridge")
        profile.capabilities = {"image"}
        profile.options_json = '{"poll_interval":2}'
        workflow = Workflow.from_plan(
            "recover independently generated reference",
            {
                "tasks": [
                    {
                        "id": "reference",
                        "expert": "image",
                        "prompt": "reference",
                        "contract": {"part_id": "reference"},
                    }
                ]
            },
        )

        def checked_process(payload):
            # This runs at the actual process launch boundary, before any POST.
            checkpoint = json.loads((run.folder / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(
                checkpoint["tasks"][0]["result"]["submission"]["directory"], payload["output_dir"]
            )
            self.assertEqual(checkpoint["repairs"]["reference"], 1)
            return ProcessJob(payload)

        run = runtime.StudioRun(self.scene, workflow, job_factory=checked_process)
        run.repairs["reference"] = 1
        run.start()

        def accepted():
            submission = workflow.tasks[0].result.get("submission")
            if not submission:
                return False
            path = Path(submission["directory"]) / "remote-job.json"
            return path.is_file() and json.loads(path.read_text())["state"] == "pending"

        pump(run, until=accepted)
        self.assertTrue(accepted(), json.dumps(workflow.snapshot(), ensure_ascii=False))
        with urlopen(self.base + "/stats") as response:
            posts = json.load(response)["job_posts"]
        run.cancel()
        resumed = runtime.resume_checkpoint(self.scene, str(run.folder / "run.json"))
        self.assertEqual(resumed.calls, 1)
        self.assertEqual(resumed.repairs["reference"], 1)
        resumed.tick()
        child = resumed.lanes["reference"]
        # Simulate no further parent timer ticks while a child finishes.
        pump(child)
        checkpoint = json.loads((resumed.folder / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["tasks"][0]["status"], "succeeded")
        pump(resumed)
        self.assertTrue(resumed.workflow.complete)
        self.assertEqual(resumed.dispatches[-1]["action"], "recover")
        self.assertEqual(resumed.workflow.tasks[0].attempts, 2)
        with urlopen(self.base + "/stats") as response:
            self.assertEqual(json.load(response)["job_posts"], posts)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(BlenderTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
destination = ROOT / "artifacts/validation"
destination.mkdir(parents=True, exist_ok=True)
(destination / f"blender-{bpy.app.version_string}.json").write_text(
    json.dumps(
        {
            "blender": bpy.app.version_string,
            "tests": result.testsRun,
            "failures": [(str(t), msg) for t, msg in result.failures],
            "errors": [(str(t), msg) for t, msg in result.errors],
            "success": result.wasSuccessful(),
        },
        indent=2,
    ),
    encoding="utf-8",
)
if not result.wasSuccessful():
    raise RuntimeError("Blender integration tests failed")
