"""Defense in depth for generated Python, NOT an operating-system sandbox.

Blender's Python API is powerful. Only execute code from a provider you trust.
This guard blocks common destructive/file/process APIs and introspection tricks;
it cannot make arbitrary Python or Blender data intrinsically safe.
"""
import ast
from .responses import extract_code

ALLOWED_MODULES = frozenset({"bpy", "bmesh", "mathutils", "math", "random",
                             "collections", "itertools", "functools", "copy"})
SAFE_BUILTINS = frozenset({"abs", "all", "any", "bool", "dict", "enumerate", "filter",
    "float", "frozenset", "int", "isinstance", "iter", "len", "list", "map", "max", "min",
    "next", "pow", "print", "range", "repr", "reversed", "round", "set", "slice", "sorted",
    "str", "sum", "tuple", "zip", "Exception", "ValueError", "RuntimeError", "TypeError"})
FORBIDDEN_NAMES = frozenset({"eval", "exec", "compile", "open", "getattr", "setattr",
    "delattr", "globals", "locals", "vars", "dir", "type", "breakpoint", "input", "help"})
FORBIDDEN_ATTRS = frozenset({"driver_namespace", "handlers", "timers", "preferences",
    "user_resource", "script_paths", "as_pointer", "bl_rna", "rna_type", "path_resolve",
    "save", "save_render", "filepath", "filepath_raw", "write", "read", "load", "pack",
    "unpack", "to_driver", "driver_add", "driver_remove"})


def attribute_path(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return attribute_path(node.value) + "." + node.attr
    return ""


class SecurityValidator:
    @staticmethod
    def clean_response(raw):
        return extract_code(raw)

    @staticmethod
    def validate(code):
        if len(code) > 200_000:
            return False, "Code exceeds the 200 KB limit"
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError) as exc:
            return False, f"Invalid Python: {exc}"
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in ALLOWED_MODULES:
                        return False, f"Import not allowed: {alias.name}"
                    aliases[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.level or node.module not in ALLOWED_MODULES:
                    return False, f"Import not allowed: {node.module}"
                for alias in node.names:
                    if alias.name.startswith("_") or alias.name == "*":
                        return False, "Private or wildcard imports are not allowed"
                    aliases[alias.asname or alias.name] = node.module + "." + alias.name
            elif isinstance(node, ast.Name):
                if node.id.startswith("__") or node.id in FORBIDDEN_NAMES:
                    return False, f"Name not allowed: {node.id}"
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("_") or node.attr in FORBIDDEN_ATTRS:
                    return False, f"Attribute not allowed: {node.attr}"
            elif isinstance(node, (ast.Global, ast.Nonlocal, ast.ClassDef, ast.AsyncFunctionDef)):
                return False, f"Construct not allowed: {type(node).__name__}"
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Attribute, ast.Name)):
                continue
            path = attribute_path(node)
            first, _, rest = path.partition(".")
            path = aliases.get(first, first) + ("." + rest if rest else "")
            if any(path == p or path.startswith(p + ".") for p in (
                    "bpy.ops.wm", "bpy.ops.script", "bpy.ops.console", "bpy.ops.text",
                    "bpy.ops.preferences", "bpy.ops.import_scene", "bpy.ops.export_scene",
                    "bpy.ops.object.delete", "bpy.data.libraries", "bpy.utils", "bpy.path")):
                return False, f"Blender API not allowed: {path}"
            if path.startswith("bpy.data.") and path.endswith((".remove", ".batch_remove")):
                return False, "Generated code may not delete existing scene data"
        return True, ""


def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name not in ALLOWED_MODULES or any(n.startswith("_") for n in (fromlist or ())):
        raise ImportError(f"Import not allowed: {name}")
    return __import__(name, globals, locals, fromlist, level)
