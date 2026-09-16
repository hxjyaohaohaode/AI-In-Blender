"""blender / localization — extracted from the original add-on."""

from ..data.translations import I18N
import bpy


def t(key: str) -> str:
    """Get localized string based on addon preferences."""
    lang = "zh" if getattr(get_prefs(), "language", "en") == "zh" else "en"
    return I18N.get(lang, I18N["en"]).get(key, key)


def get_prefs():
    """Safely get addon preferences."""
    try:
        addon = bpy.context.preferences.addons.get(__package__.rsplit(".", 1)[0])
        if addon:
            return addon.preferences
    except Exception:
        pass
    return None


def _current_lang():
    return getattr(get_prefs(), "language", "en")
