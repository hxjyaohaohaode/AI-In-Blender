"""Strict, reversible registration and file-load lifecycle cleanup."""
import bpy
from bpy.props import PointerProperty
from bpy.app.handlers import persistent
from .properties import AMA_Provider, AMA_Properties, AMA_AddonPreferences
from . import ai_operators, ui_studio, ui_tools, ui_platform, conversation, proactive
from . import tools_build, tools_materials, tools_mesh, tools_rigging
from . import tools_animation, tools_procedural, tools_assets, tools_export
from . import runtime, state


def own_classes(module, base):
    return [value for value in vars(module).values()
            if isinstance(value, type) and value.__module__ == module.__name__
            and issubclass(value, base)]


ALL_CLASSES = [AMA_Provider, AMA_Properties, AMA_AddonPreferences] + ai_operators.CLASSES
for module in (tools_build, tools_materials, tools_mesh, tools_rigging,
               tools_animation, tools_procedural, tools_assets, tools_export):
    ALL_CLASSES.extend(own_classes(module, bpy.types.Operator))
ALL_CLASSES += ui_studio.CLASSES + own_classes(ui_tools, bpy.types.Panel)
ALL_CLASSES += ui_platform.CLASSES
_registered = []


@persistent
def on_load_pre(_):
    proactive.stop()
    conversation.shutdown()
    runtime.shutdown()
    state.clear_session()
    state._session_keys.clear()


@persistent
def on_load_post(_):
    proactive.start()
    state.migrate_legacy_secrets()
    for scene in bpy.data.scenes:
        if scene.ama_props.project_id:
            try:
                conversation.refresh(scene)
            except (OSError, ValueError):
                scene.ama_props.chat_status = 'Could not reopen local conversation database'


def migrate_after_registration():
    if _registered:
        state.migrate_legacy_secrets()
        proactive.start()
    return None


def register():
    if _registered:
        return
    try:
        for cls in ALL_CLASSES:
            bpy.utils.register_class(cls)
            _registered.append(cls)
        bpy.types.Scene.ama_props = PointerProperty(type=AMA_Properties)
        bpy.app.handlers.load_pre.append(on_load_pre)
        bpy.app.handlers.load_post.append(on_load_post)
        # Blender restricts scene access while addon_utils is registering an add-on.
        bpy.app.timers.register(migrate_after_registration, first_interval=0.0)
    except Exception:
        unregister()
        raise


def unregister():
    proactive.stop()
    conversation.shutdown()
    runtime.shutdown()
    if bpy.app.timers.is_registered(migrate_after_registration):
        bpy.app.timers.unregister(migrate_after_registration)
    if on_load_pre in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(on_load_pre)
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
    if hasattr(bpy.types.Scene, "ama_props"):
        del bpy.types.Scene.ama_props
    errors = []
    for cls in reversed(_registered):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as exc:
            errors.append(str(exc))
    _registered.clear()
    state.clear_session()
    state._session_keys.clear()
    if errors:
        raise RuntimeError("Could not fully unregister add-on: " + "; ".join(errors))
