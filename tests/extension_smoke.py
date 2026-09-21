"""Verify a real extension install, namespaced preferences and its packaged worker."""
import importlib
import os
from pathlib import Path
import subprocess
import time
import bpy

root = Path(__file__).resolve().parents[1]
expected = Path(os.environ['BLENDER_USER_EXTENSIONS']).resolve()
assert root / 'artifacts' in expected.parents
os.environ['AI_IN_BLENDER_MEMORY_DB'] = str(expected.parent/'memory.sqlite3')
name = 'bl_ext.studio_smoke.ai_modeling_assistant'
module = importlib.import_module(name)
assert expected in Path(module.__file__).resolve().parents
assert name in bpy.context.preferences.addons
state = importlib.import_module(name + '.blender.state')
assert state.preferences() is not None
assert 'FINISHED' in bpy.ops.ama.quick_build(preset_key='sword')
process = importlib.import_module(name + '.core.process')
config_module = importlib.import_module(name + '.core.config')
server = subprocess.Popen([process.python_executable(), str(root / 'tests/fixtures/provider_server.py')],
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
job = None
try:
    port = int(server.stdout.readline())
    config = config_module.ProviderConfig(base_url=f'http://127.0.0.1:{port}', model='fixture')
    job = process.ProcessJob({'action': 'chat', 'config': config.payload(),
                              'messages': [{'role': 'user', 'content': 'cube'}]})
    end = time.monotonic() + 10
    result = None
    while time.monotonic() < end:
        result = job.poll()
        if result is not None:
            break
        time.sleep(0.02)
    assert result is not None and not result.get('error'), result
    assert 'primitive_cube_add' in result['content']
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj,do_unlink=True)
    runtime = importlib.import_module(name+'.blender.runtime')
    bpy.context.scene.ama_props.artifact_dir = str(expected.parent/'runs')
    run = runtime.start_reviewed_code(bpy.context.scene,"import bpy\nbpy.ops.mesh.primitive_cube_add(size=1)",[])
    end = time.monotonic()+45
    while run.running and time.monotonic()<end:
        run.tick()
        time.sleep(.03)
    assert run.workflow.complete, bpy.context.scene.ama_props.workflow_status
    assert any(run.folder.rglob('candidate.blend'))
    assert any(run.folder.rglob('preview.png'))
    runtime.shutdown()
finally:
    if job:
        job.cancel()
    server.terminate()
    server.wait(timeout=5)
    server.stdout.close()
print('EXTENSION_SMOKE_OK', module.__file__)
