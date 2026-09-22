"""Isolated scene work and optimistic, serialized main-thread commits."""

import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import bpy
from .revision import (
    ensure_ids,
    fingerprint,
    check_region,
    region_preserved,
    object_dependencies,
    scene_revision,
)
from .quality import evaluate
from ..core.security import SecurityValidator


class SceneJob:
    def __init__(
        self,
        code,
        objects,
        folder,
        *,
        contract=None,
        regions=None,
        render=True,
        timeout=120,
        contract_checks=None,
    ):
        valid, reason = SecurityValidator.validate(code)
        if not valid:
            raise ValueError(reason)
        self.objects = list(objects)
        external = object_dependencies(self.objects)
        if external:
            raise ValueError(
                "Include referenced objects in the workflow scope before editing: "
                + ", ".join(sorted(o.name for o in external))
            )
        ensure_ids(self.objects)
        self.regions = regions or []
        check_region(self.objects, self.regions)
        self.before = fingerprint(self.objects)
        self.ids = [o["ama_asset_id"] for o in self.objects]
        self.folder = Path(folder) / ("branch-" + uuid.uuid4().hex[:12])
        self.folder.mkdir(parents=True)
        self.contract = contract or {}
        self.contract_checks = contract_checks or []
        scene = bpy.context.scene
        if self.regions and self.contract.get("allow_scene_settings"):
            raise ValueError("Precise region edits cannot change shared scene settings")
        from .scene_state import capture

        resources = set(self.objects)
        if scene.world:
            resources.add(scene.world)
        if resources:
            bpy.data.libraries.write(
                str(self.folder / "input.blend"), resources, path_remap="ABSOLUTE"
            )
        self.frames = [scene.frame_start, scene.frame_end]
        self.scene_before = scene_revision(scene)
        self.settings_before = capture(scene, self.objects)
        payload = {
            "code": code,
            "objects": [o.name for o in self.objects],
            "contract": self.contract,
            "frames": self.frames,
            "current_frame": scene.frame_current,
            "current_subframe": scene.frame_subframe,
            "unit_scale": scene.unit_settings.scale_length,
            "render": render,
            "contract_checks": self.contract_checks,
            "fps": scene.render.fps,
            "fps_base": scene.render.fps_base,
            "settings": self.settings_before,
            "world": scene.world.name if scene.world else None,
        }
        (self.folder / "request.json").write_text(json.dumps(payload), encoding="utf-8")
        worker = Path(__file__).resolve().parents[1] / "scene_worker.py"
        self.log = open(self.folder / "blender.log", "wb")
        # No provider secrets are serialized into the request or command line.
        allowed_env = {
            "SYSTEMROOT",
            "WINDIR",
            "PATH",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "HOMEDRIVE",
            "HOMEPATH",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "PROGRAMDATA",
            "ALLUSERSPROFILE",
            "COMSPEC",
            "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE",
            "HOME",
            "LANG",
            "LC_ALL",
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "XDG_RUNTIME_DIR",
            "LD_LIBRARY_PATH",
            "DYLD_LIBRARY_PATH",
            "CUDA_PATH",
            "CUDA_VISIBLE_DEVICES",
        }
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed_env}
        self.process = subprocess.Popen(
            [
                bpy.app.binary_path,
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--python-exit-code",
                "1",
                "--python",
                str(worker),
                "--",
                str(self.folder),
            ],
            stdout=self.log,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.started, self.timeout = time.monotonic(), timeout
        self.closed = False

    def poll(self):
        if self.closed:
            return {"error": "Scene process was cancelled"}
        if self.process.poll() is None:
            if time.monotonic() - self.started <= self.timeout:
                return None
            self.cancel()
            return {
                "error": "Isolated Blender execution exceeded its deadline; current scene is unchanged"
            }
        self.log.close()
        self.closed = True
        path = self.folder / "result.json"
        if self.process.returncode or not path.is_file():
            return {
                "error": "Isolated Blender process failed; inspect "
                + str(self.folder / "blender.log")
            }
        if path.stat().st_size > 16_000_000:
            return {"error": "Isolated Blender result exceeds the manifest size limit"}
        return json.loads(path.read_text(encoding="utf-8"))

    def commit(self, result, collection):
        if result.get("error"):
            raise ValueError(result["error"])
        frames = result.get("frames")
        if (
            not isinstance(frames, list)
            or len(frames) != 2
            or any(type(v) is not int for v in frames)
            or frames[0] > frames[1]
        ):
            raise ValueError("Candidate returned an invalid timeline")
        if (
            any(o.name not in bpy.context.scene.objects for o in self.objects)
            or fingerprint(self.objects) != self.before
        ):
            raise ValueError(
                "Human edit conflict: source objects changed during generation. Candidate retained at "
                + str(self.folder)
            )
        if scene_revision(bpy.context.scene) != self.scene_before:
            raise ValueError(
                "Timeline, frame or units changed during generation; candidate retained for review"
            )
        if self.contract.get("part_id") and result["frames"] != self.frames:
            raise ValueError("Independent part tasks cannot change the shared timeline")
        if result.get("settings", {}).get("frames") != result["frames"]:
            raise ValueError("Candidate scene settings disagree with its timeline")
        if not self.contract.get("allow_scene_settings") and any(
            result["settings"].get(key) != value
            for key, value in self.settings_before.items()
            if key not in {"frames", "world_revision"}
        ):
            raise ValueError("Candidate changed protected shared scene settings")
        path = Path(result["blend"]).resolve()
        if path.parent != self.folder.resolve() or not path.is_file():
            raise ValueError("Invalid isolated output path")
        loaded = []
        validation_scene = None
        registries = (
            "meshes",
            "materials",
            "node_groups",
            "actions",
            "armatures",
            "cameras",
            "lights",
            "images",
            "curves",
            "worlds",
        )
        resources_before = {name: set(getattr(bpy.data, name)) for name in registries}
        try:
            with bpy.data.libraries.load(str(path), link=False) as (src, dest):
                dest.objects = list(result["objects"])
                dest.worlds = [result["world"]] if result.get("world") else []
            loaded = list(dest.objects)
            candidate_world = dest.worlds[0] if dest.worlds else None
            if any(o is None for o in loaded):
                raise ValueError("Candidate object is missing")
            by_id = {o.get("ama_asset_id"): o for o in loaded}
            if len(by_id) != len(loaded) or any(i not in by_id for i in self.ids):
                raise ValueError("Candidate violated stable asset identity contract")
            region_preserved(self.objects, loaded, self.regions)
            if object_dependencies(loaded):
                raise ValueError("Candidate contains out-of-scope object references")
            # An unlinked object has no evaluated dependency graph. Validate in a
            # temporary scene so modifiers and required names cannot evade gates.
            validation_scene = bpy.data.scenes.new("AI Candidate Validation")
            from .scene_state import apply

            apply(validation_scene, result["settings"], loaded, world=candidate_world)
            for obj in loaded:
                validation_scene.collection.objects.link(obj)
            name_map = {obj.name: name for obj, name in zip(loaded, result["objects"])}
            with bpy.context.temp_override(
                scene=validation_scene, view_layer=validation_scene.view_layers[0]
            ):
                validation_scene.frame_set(
                    self.scene_before["current_frame"], subframe=self.scene_before["subframe"]
                )
                report = evaluate(loaded, self.contract, name_map=name_map)
                for check in self.contract_checks:
                    subset = [o for o in loaded if o.get("ama_asset_id") in check["asset_ids"]]
                    if len(subset) != len(check["asset_ids"]):
                        report["errors"].append("Missing dependency assets: " + check["task"])
                    inherited = evaluate(subset, check["contract"], name_map=name_map)
                    report["errors"].extend(check["task"] + ": " + e for e in inherited["errors"])
                report["passed"] = not report["errors"]
            if not report["passed"]:
                raise ValueError(
                    "Candidate failed native validation before commit: "
                    + "; ".join(report["errors"])
                )
        except Exception:
            if validation_scene:
                bpy.data.scenes.remove(validation_scene)
                validation_scene = None
            for obj in loaded:
                if obj:
                    bpy.data.objects.remove(obj, do_unlink=True)
            for name in registries:
                registry = getattr(bpy.data, name)
                for item in set(registry) - resources_before[name]:
                    if item.users == 0:
                        registry.remove(item)
            raise
        finally:
            if validation_scene:
                bpy.data.scenes.remove(validation_scene)
        # Nothing mutates source objects until every candidate and revision check passes.
        remapped = []
        try:
            for old in self.objects:
                new = by_id[old["ama_asset_id"]]
                # user_remap transfers collection membership too. Linking first
                # creates duplicate references and leaks user counts in Blender 3.6.
                old.user_remap(new)
                remapped.append((old, new))
            for obj in loaded:
                if obj.name not in collection.objects:
                    collection.objects.link(obj)
        except Exception:
            # Originals still exist until every reference update has succeeded.
            for old, new in reversed(remapped):
                new.user_remap(old)
            for obj in loaded:
                bpy.data.objects.remove(obj, do_unlink=True)
            raise
        for old in self.objects:
            new = by_id[old["ama_asset_id"]]
            name = old.name
            new.use_fake_user = old.use_fake_user
            old.use_fake_user = False
            bpy.data.objects.remove(old, do_unlink=True)
            new.name = name
        bpy.context.scene.frame_start, bpy.context.scene.frame_end = result["frames"]
        if self.contract.get("allow_scene_settings"):
            apply(bpy.context.scene, result["settings"], loaded, world=candidate_world)
        elif candidate_world and candidate_world.users == 0:
            bpy.data.worlds.remove(candidate_world)
        bpy.context.view_layer.update()
        self.quality = dict(report, fingerprint=fingerprint(loaded))
        return loaded

    def cancel(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=5)
        if not self.closed:
            self.log.close()
        self.closed = True
