"""AI in Blender. Core modules remain importable without Blender installed."""

bl_info = {
    "name": "AI in Blender — Agent Platform",
    "author": "AI-In-Blender contributors",
    "version": (3, 1, 0),
    "blender": (3, 6, 0),
    "location": "3D View > Sidebar > AI Model",
    "description": "Multi-model creative workflows, modeling and asset tools",
    "doc_url": "https://github.com/hxjyaohaohaode/AI-In-Blender",
    "category": "3D View",
}


def register():
    from .blender.registration import register as register_addon
    register_addon()


def unregister():
    from .blender.registration import unregister as unregister_addon
    unregister_addon()
