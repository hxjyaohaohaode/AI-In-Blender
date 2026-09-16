"""Debounced local observations: no paid calls, no automatic scene mutation."""
import time
import bpy
from bpy.app.handlers import persistent

_dirty = {}
_last = {}


@persistent
def changed(scene, depsgraph):
    _dirty[scene.as_pointer()] = True


def tick():
    scene = bpy.context.scene
    if not scene or not hasattr(scene,'ama_props'):
        return 5.0
    key = scene.as_pointer()
    if scene.ama_props.proactive_enabled and _dirty.get(key) and time.monotonic()-_last.get(key,0) >= 15:
        _dirty[key] = False
        _last[key] = time.monotonic()
        suggestions = []
        selected = list(bpy.context.selected_objects)[:24]
        missing_materials = sum(o.type=='MESH' and not any(o.data.materials) for o in selected)
        missing_uv = sum(o.type=='MESH' and not o.data.uv_layers for o in selected)
        if missing_materials:
            suggestions.append(f'{missing_materials} selected meshes have no materials')
        if missing_uv:
            suggestions.append(f'{missing_uv} selected meshes have no UV maps; check texture requirements')
        from .conversation import _ui_cache
        conflicts = sum(m['status']=='conflict' for m in _ui_cache.get(key,{}).get('memories',[]))
        if conflicts:
            suggestions.append(f'{conflicts} memory conflicts await your decision')
        from .runtime import current
        run = current(scene)
        if run and run.pending_quality:
            suggestions.append('Visual quality approval is pending and will be invalidated by content changes')
        scene.ama_props.proactive_status = ' · '.join(suggestions) or 'No immediate local issue detected; artistic quality still needs inspection'
    return 5.0


def start():
    if changed not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(changed)
    if not bpy.app.timers.is_registered(tick):
        bpy.app.timers.register(tick,first_interval=5)


def stop():
    if changed in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(changed)
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    _dirty.clear()
    _last.clear()
