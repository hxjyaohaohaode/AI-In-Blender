"""Session state. Keys are never stored in Blender scene or preference properties."""
import os
import bpy
from ..core.history import ConversationHistory
from ..core.telemetry import CostTracker
from ..core.config import ProviderConfig, PROTOCOL_CAPABILITIES, is_loopback
from ..core.providers import APIEngine
from urllib.parse import urlsplit

_cost_tracker = CostTracker()
_conversation_histories = {}
_version_snapshots = {}
_asset_registry = []
_session_keys = {}


def secret_get(self):
    return _session_keys.get(self.as_pointer(), "")


def secret_set(self, value):
    _session_keys[self.as_pointer()] = value


def get_conversation(scene_name=None):
    scene = bpy.context.scene
    key = scene_name if scene_name is not None else scene.as_pointer()
    history = _conversation_histories.setdefault(key, ConversationHistory())
    history.max_tokens = scene.ama_props.max_history_tokens
    return history


def preferences():
    addon = bpy.context.preferences.addons.get(__package__.rsplit(".", 1)[0])
    return addon.preferences if addon else None


def profiles():
    prefs = preferences()
    return prefs.providers if prefs else []


def profile_supports(profile, capability):
    return (profile.enabled and capability in profile.capabilities
            and capability in PROTOCOL_CAPABILITIES.get(profile.protocol, set()))


def provider_for(capability="chat", expert="", scene=None):
    import json
    scene = scene or bpy.context.scene
    candidates = [p for p in profiles() if profile_supports(p, capability)]
    candidates.sort(key=lambda p: (0 if expert and expert in p.experts else 1))
    candidates = [p for p in candidates if not p.experts or expert in p.experts]
    if candidates:
        p = candidates[0]
        config = ProviderConfig(name=p.name, protocol=p.protocol, base_url=p.base_url,
            model=p.model, api_key=p.api_key or os.environ.get(p.key_env, ""),
            timeout=p.timeout, max_tokens=p.max_tokens, temperature=p.temperature,
            options=json.loads(p.options_json or "{}"))
        config.options["vision"] = "vision" in p.capabilities
    elif capability == "chat" and not any(p.enabled for p in profiles()):
        p = scene.ama_props
        config = ProviderConfig(base_url=p.api_url, model=p.model,
            api_key=p.api_key or os.environ.get(p.key_env, ""), timeout=p.request_timeout,
            max_tokens=p.max_tokens, temperature=p.temperature)
        config.options["vision"] = p.basic_vision
    else:
        raise ValueError(f"No enabled provider is assigned to {expert or capability} ({capability})")
    config.validate()
    if not getattr(bpy.app, "online_access", True) and not is_loopback(urlsplit(config.base_url).hostname):
        raise ValueError("Enable Blender Online Access to use a remote AI provider")
    return config


def available_capabilities():
    result = set()
    for profile in profiles():
        for capability in profile.capabilities:
            if profile_supports(profile, capability):
                result.add(capability)
    if not any(p.enabled for p in profiles()):
        result.add("chat")
    return result


def get_api_engine():
    config = provider_for()
    return APIEngine(config.base_url, config.api_key, config.model,
                     config.temperature, config.max_tokens)


def clear_session():
    _conversation_histories.clear()
    _version_snapshots.clear()
    _asset_registry.clear()


def migrate_legacy_secrets():
    """Remove the v2 stored key property; retain it only in this session's memory."""
    for scene in bpy.data.scenes:
        props = scene.ama_props
        old_key = props.get("api_key")
        if isinstance(old_key, str):
            if old_key:
                secret_set(props, old_key)
            del props["api_key"]
