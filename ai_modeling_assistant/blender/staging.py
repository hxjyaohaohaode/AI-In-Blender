"""Isolated scene work and optimistic, serialized main-thread commits."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import bpy
from .revision import ensure_ids, fingerprint, check_region, region_preserved
from .quality import evaluate
from ..core.security import SecurityValidator


class SceneJob:
    def __init__(self, code, objects, folder, *, contract=None, regions=None, render=True, timeout=120):
        valid, reason = SecurityValidator.validate(code)
        if not valid:
            raise ValueError(reason)
        self.objects = list(objects)
        ensure_ids(self.objects)
        self.regions = regions or []
        check_region(self.objects, self.regions)
        self.before = fingerprint(self.objects)
        self.ids = [o['ama_asset_id'] for o in self.objects]
        self.folder = Path(folder) / ('branch-' + uuid.uuid4().hex[:12])
        self.folder.mkdir(parents=True)
        self.contract = contract or {}
        if self.objects:
            bpy.data.libraries.write(str(self.folder/'input.blend'), set(self.objects), fake_user=True)
        scene = bpy.context.scene
        self.frames = [scene.frame_start, scene.frame_end]
        payload = {'code':code, 'objects':[o.name for o in self.objects], 'contract':self.contract,
            'frames':self.frames, 'current_frame':scene.frame_current, 'unit_scale':scene.unit_settings.scale_length, 'render':render}
        (self.folder/'request.json').write_text(json.dumps(payload), encoding='utf-8')
        worker = Path(__file__).resolve().parents[1] / 'scene_worker.py'
        self.log = open(self.folder/'blender.log', 'wb')
        # No provider secrets are serialized into the request or command line.
        allowed_env = {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA',
            'HOMEDRIVE','HOMEPATH','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMDATA','ALLUSERSPROFILE',
            'COMSPEC','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE','HOME','LANG','LC_ALL',
            'DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','LD_LIBRARY_PATH','DYLD_LIBRARY_PATH',
            'CUDA_PATH','CUDA_VISIBLE_DEVICES'}
        env = {k:v for k,v in os.environ.items() if k.upper() in allowed_env}
        self.process = subprocess.Popen([bpy.app.binary_path, '--background', '--factory-startup', '--disable-autoexec',
            '--python-exit-code','1','--python',str(worker),'--',str(self.folder)],
            stdout=self.log, stderr=subprocess.STDOUT, env=env,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.started, self.timeout = time.monotonic(), timeout
        self.closed = False

    def poll(self):
        if self.closed:
            return {'error':'Scene process was cancelled'}
        if self.process.poll() is None:
            if time.monotonic()-self.started <= self.timeout:
                return None
            self.cancel()
            return {'error':'Isolated Blender execution exceeded its deadline; current scene is unchanged'}
        self.log.close()
        self.closed = True
        path = self.folder/'result.json'
        if self.process.returncode or not path.is_file():
            return {'error':'Isolated Blender process failed; inspect ' + str(self.folder/'blender.log')}
        return json.loads(path.read_text(encoding='utf-8'))

    def commit(self, result, collection):
        if result.get('error'):
            raise ValueError(result['error'])
        if any(o.name not in bpy.context.scene.objects for o in self.objects) or fingerprint(self.objects) != self.before:
            raise ValueError('Human edit conflict: source objects changed during generation. Candidate retained at ' + str(self.folder))
        if [bpy.context.scene.frame_start,bpy.context.scene.frame_end] != self.frames:
            raise ValueError('Timeline changed during generation; candidate retained for review')
        if self.contract.get('part_id') and result['frames'] != self.frames:
            raise ValueError('Independent part tasks cannot change the shared timeline')
        path = Path(result['blend']).resolve()
        if path.parent != self.folder.resolve() or not path.is_file():
            raise ValueError('Invalid isolated output path')
        loaded = []
        try:
            with bpy.data.libraries.load(str(path), link=False) as (src, dest):
                dest.objects = result['objects']
            loaded = list(dest.objects)
            if any(o is None for o in loaded):
                raise ValueError('Candidate object is missing')
            by_id = {o.get('ama_asset_id'):o for o in loaded}
            if len(by_id) != len(loaded) or any(i not in by_id for i in self.ids):
                raise ValueError('Candidate violated stable asset identity contract')
            region_preserved(self.objects, loaded, self.regions)
            report = evaluate(loaded, {k:v for k,v in self.contract.items() if k not in {'required_objects','anchor_object','anchor_position'}})
            if not report['passed']:
                raise ValueError('Candidate failed native validation before commit')
        except Exception:
            for obj in loaded:
                if obj:
                    bpy.data.objects.remove(obj, do_unlink=True)
            raise
        # Nothing mutates source objects until every candidate and revision check passes.
        for obj in loaded:
            collection.objects.link(obj)
        for old in self.objects:
            new = by_id[old['ama_asset_id']]
            name = old.name
            for owner in list(old.users_collection):
                if new.name not in owner.objects:
                    owner.objects.link(new)
            old.user_remap(new)
            bpy.data.objects.remove(old, do_unlink=True)
            new.name = name
        bpy.context.scene.frame_start, bpy.context.scene.frame_end = result['frames']
        bpy.context.view_layer.update()
        return loaded

    def cancel(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=5)
        if not self.closed:
            self.log.close()
        self.closed = True
