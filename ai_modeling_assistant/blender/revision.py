"""Content fingerprints protect human edits from stale agent commits."""

from array import array
import hashlib
import json
import uuid
import bpy


def ensure_ids(objects):
    seen = set()
    for obj in objects:
        ident = obj.get("ama_asset_id")
        if not isinstance(ident, str) or ident in seen:
            ident = uuid.uuid4().hex
            obj["ama_asset_id"] = ident
        seen.add(ident)


def custom_values(value):
    try:
        return dict(value.items())
    except TypeError:
        # Only some RNA structures (notably Geometry Nodes modifiers) support
        # IDProperties. Subsurf/Bevel expose their state through RNA instead.
        return {}


def rna_values(value):
    result = {}
    for prop in value.bl_rna.properties:
        name = prop.identifier
        if (
            name
            in {"rna_type", "name", "name_full", "execution_time", "is_active", "is_override_data"}
            or prop.type == "COLLECTION"
        ):
            continue
        try:
            item = getattr(value, name)
            if prop.type == "POINTER":
                if isinstance(item, bpy.types.ID):
                    result[name] = item.get("ama_asset_id", item.name)
            elif getattr(prop, "is_array", False):
                result[name] = list(item)
            elif isinstance(item, (str, int, float, bool)):
                result[name] = item
            elif isinstance(item, set):
                result[name] = sorted(item)
        except (AttributeError, TypeError, RuntimeError):
            continue
    return result


def animation_values(obj):
    data = getattr(obj, "animation_data", None)
    if not data or (not data.action and not data.nla_tracks and not data.drivers):
        return None
    return {
        "action": action_values(data.action),
        "nla": [
            (t.name, t.mute, [(rna_values(s), action_values(s.action)) for s in t.strips])
            for t in data.nla_tracks
        ],
        "drivers": [
            (
                f.data_path,
                f.array_index,
                f.driver.expression,
                [(v.name, v.type, [rna_values(t) for t in v.targets]) for v in f.driver.variables],
            )
            for f in data.drivers
        ],
    }


def action_values(action):
    if action is None:
        return None
    curves = list(getattr(action, "fcurves", ()))
    for layer in getattr(action, "layers", ()):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", ()):
                curves.extend(bag.fcurves)
    return [
        (
            f.data_path,
            f.array_index,
            f.extrapolation,
            f.mute,
            [rna_values(m) for m in f.modifiers],
            [
                (
                    list(k.co),
                    list(k.handle_left),
                    list(k.handle_right),
                    k.interpolation,
                    k.handle_left_type,
                    k.handle_right_type,
                )
                for k in f.keyframe_points
            ],
        )
        for f in curves
    ]


def socket_value(value):
    if isinstance(value, bpy.types.ID):
        result = {"id": value.get("ama_asset_id", value.name)}
        if isinstance(value, bpy.types.Object):
            result["transform"] = [list(row) for row in value.matrix_world]
        return result
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return list(value)
    except TypeError:
        return str(value)


def node_values(tree, seen=None):
    if tree is None:
        return None
    seen = set() if seen is None else seen
    if tree.as_pointer() in seen:
        return {"reference": tree.name}
    seen.add(tree.as_pointer())
    return {
        "nodes": [
            (
                n.name,
                n.bl_idname,
                rna_values(n),
                custom_values(n),
                [(s.identifier, socket_value(getattr(s, "default_value", ""))) for s in n.inputs],
                [(s.identifier, socket_value(getattr(s, "default_value", ""))) for s in n.outputs],
                node_values(getattr(n, "node_tree", None), seen),
            )
            for n in tree.nodes
        ],
        "links": [
            (l.from_node.name, l.from_socket.identifier, l.to_node.name, l.to_socket.identifier)
            for l in tree.links
        ],
    }


def fingerprint(objects):
    bpy.context.view_layer.update()
    digest = hashlib.sha256()

    def add(data):
        digest.update(
            json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        )

    for obj in sorted(objects, key=lambda o: (o.get("ama_asset_id", ""), o.name)):
        if obj.mode == "EDIT":
            obj.update_from_editmode()
        add(
            (
                obj.name,
                obj.get("ama_asset_id", ""),
                obj.type,
                [list(row) for row in obj.matrix_world],
                list(obj.location),
                list(obj.scale),
                list(obj.rotation_euler),
                list(obj.rotation_quaternion),
                list(obj.delta_location),
                list(obj.delta_scale),
                list(obj.delta_rotation_euler),
                obj.parent.get("ama_asset_id", obj.parent.name) if obj.parent else None,
                [(rna_values(m), custom_values(m)) for m in obj.modifiers],
                [rna_values(c) for c in obj.constraints],
                animation_values(obj),
            )
        )
        add(
            (
                dict(obj.items()),
                obj.hide_render,
                obj.hide_viewport,
                obj.parent_type,
                obj.parent_bone,
                [list(row) for row in obj.matrix_parent_inverse],
                list(obj.color),
            )
        )
        if obj.data:
            add(dict(obj.data.items()))
            add(animation_values(obj.data))
        add([node_values(m.node_group) for m in obj.modifiers if m.type == "NODES"])
        if obj.type == "MESH":
            mesh = obj.data
            for values, prop, size, code in (
                (mesh.vertices, "co", 3, "f"),
                (mesh.edges, "vertices", 2, "i"),
                (mesh.loops, "vertex_index", 1, "i"),
                (mesh.polygons, "loop_total", 1, "i"),
                (mesh.polygons, "material_index", 1, "i"),
            ):
                buf = array(code, [0]) * (len(values) * size)
                values.foreach_get(prop, buf)
                digest.update(buf.tobytes())
            for layer in mesh.uv_layers:
                add((layer.name, layer.active_render))
                buf = array("f", [0]) * (len(layer.data) * 2)
                layer.data.foreach_get("uv", buf)
                digest.update(buf.tobytes())
            add([(g.name, g.lock_weight) for g in obj.vertex_groups])
            add([[(g.group, g.weight) for g in v.groups] for v in mesh.vertices])
            add([(p.use_smooth, getattr(p, "use_freestyle_mark", False)) for p in mesh.polygons])
            for attribute in mesh.attributes:
                if attribute.name in {"position", ".edge_verts", ".corner_vert", ".corner_edge"}:
                    continue
                add((attribute.name, attribute.domain, attribute.data_type))
                specs = {
                    "FLOAT": ("value", 1, "f"),
                    "INT": ("value", 1, "i"),
                    "INT8": ("value", 1, "i"),
                    "BOOLEAN": ("value", 1, "i"),
                    "FLOAT_VECTOR": ("vector", 3, "f"),
                    "FLOAT2": ("vector", 2, "f"),
                    "FLOAT_COLOR": ("color", 4, "f"),
                    "BYTE_COLOR": ("color", 4, "f"),
                }
                if attribute.data_type in specs:
                    prop, size, code = specs[attribute.data_type]
                    buf = array(code, [0]) * (len(attribute.data) * size)
                    attribute.data.foreach_get(prop, buf)
                    digest.update(buf.tobytes())
            if mesh.shape_keys:
                for key in mesh.shape_keys.key_blocks:
                    add(
                        (
                            key.name,
                            key.value,
                            key.mute,
                            key.relative_key.name,
                            [list(p.co) for p in key.data],
                        )
                    )
                add(animation_values(mesh.shape_keys))
        elif obj.type == "ARMATURE":
            add(
                [
                    (
                        b.name,
                        list(b.head_local),
                        list(b.tail_local),
                        b.parent.name if b.parent else "",
                    )
                    for b in obj.data.bones
                ]
            )
            add(
                [
                    (b.name, rna_values(b), [rna_values(c) for c in b.constraints])
                    for b in obj.pose.bones
                ]
            )
        elif obj.type in {"CURVE", "SURFACE", "FONT"}:
            add(rna_values(obj.data))
            add(
                [
                    (
                        [list(p.co) for p in s.points],
                        [
                            (list(p.co), list(p.handle_left), list(p.handle_right))
                            for p in s.bezier_points
                        ],
                    )
                    for s in obj.data.splines
                ]
            )
        elif obj.type in {"LIGHT", "CAMERA"}:
            add(rna_values(obj.data))
            add(animation_values(obj.data))
        for slot in obj.material_slots:
            mat = slot.material
            if mat:
                add((mat.name, list(mat.diffuse_color), mat.metallic, mat.roughness))
                add(animation_values(mat))
                if mat.node_tree:
                    add(node_values(mat.node_tree))
    return digest.hexdigest()


def object_dependencies(objects):
    """Objects referenced outside the write scope cannot be remapped safely on commit."""
    refs = set()

    def inspect(value):
        for prop in value.bl_rna.properties:
            if prop.type == "POINTER":
                target = getattr(value, prop.identifier, None)
                if isinstance(target, bpy.types.Object):
                    refs.add(target)

    def tree_refs(tree, seen):
        if tree is None or tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        for node in tree.nodes:
            inspect(node)
            for socket in node.inputs:
                value = getattr(socket, "default_value", None)
                if isinstance(value, bpy.types.Object):
                    refs.add(value)
            tree_refs(getattr(node, "node_tree", None), seen)

    for obj in objects:
        if obj.parent:
            refs.add(obj.parent)
        for value in list(obj.modifiers) + list(obj.constraints):
            inspect(value)
            tree_refs(getattr(value, "node_group", None), set())
        if obj.pose:
            for bone in obj.pose.bones:
                for constraint in bone.constraints:
                    inspect(constraint)
        for mat in obj.data.materials if obj.data and hasattr(obj.data, "materials") else []:
            if mat:
                tree_refs(mat.node_tree, set())
        if obj.animation_data:
            for curve in obj.animation_data.drivers:
                for variable in curve.driver.variables:
                    for target in variable.targets:
                        if isinstance(target.id, bpy.types.Object):
                            refs.add(target.id)
    return refs - set(objects)


def scene_revision(scene):
    return {
        "frames": [scene.frame_start, scene.frame_end],
        "current_frame": scene.frame_current,
        "fps": scene.render.fps,
        "fps_base": scene.render.fps_base,
        "unit_scale": scene.unit_settings.scale_length,
        "unit_system": scene.unit_settings.system,
    }


def check_region(objects, regions):
    """Validate captured anchors against the exact revision the user selected."""
    by_id = {o.get("ama_asset_id"): o for o in objects}
    if regions and set(by_id) != {r["asset_id"] for r in regions}:
        raise ValueError("Precise edit targets must exactly match the captured object region")
    for region in regions:
        obj = by_id.get(region["asset_id"])
        if obj is None or fingerprint([obj]) != region["fingerprint"]:
            raise ValueError(
                "Captured edit region is stale; reselect and capture after your last edit"
            )


def region_preserved(before, after, regions):
    originals = {o.get("ama_asset_id"): o for o in before}
    candidates = {o.get("ama_asset_id"): o for o in after}
    if regions and set(originals) != set(candidates):
        raise ValueError("Precise region edits cannot create or remove objects")
    for region in regions:
        if "vertices" not in region:
            continue
        old, new = originals[region["asset_id"]], candidates.get(region["asset_id"])
        if new is None or old.type != "MESH" or new.type != "MESH":
            raise ValueError("Region edit must retain the original mesh object")
        if len(old.data.vertices) != len(new.data.vertices) or len(old.data.polygons) != len(
            new.data.polygons
        ):
            raise ValueError(
                "Precise region edits cannot change topology; use a separate remeshing task"
            )
        if [tuple(p.vertices) for p in old.data.polygons] != [
            tuple(p.vertices) for p in new.data.polygons
        ]:
            raise ValueError("Precise region edit changed topology")
        selected = set(region["vertices"])
        if any(type(i) is not int or not 0 <= i < len(old.data.vertices) for i in selected):
            raise ValueError("Captured region has invalid vertex indices")
        for index, vertex in enumerate(old.data.vertices):
            if index not in selected and (vertex.co - new.data.vertices[index].co).length > 1e-6:
                raise ValueError("Generated code modified vertices outside the selected region")
        if old.matrix_world != new.matrix_world:
            raise ValueError("A region edit cannot transform the entire object")
        if [rna_values(m) for m in old.modifiers] != [rna_values(m) for m in new.modifiers]:
            raise ValueError("A vertex region edit cannot change global modifiers")
        if animation_values(old) != animation_values(new) or [
            rna_values(c) for c in old.constraints
        ] != [rna_values(c) for c in new.constraints]:
            raise ValueError("A vertex region edit cannot change global animation or constraints")
        if [tuple(e.vertices) for e in old.data.edges] != [
            tuple(e.vertices) for e in new.data.edges
        ]:
            raise ValueError("A vertex region edit cannot change edge topology")
        if [g.name for g in old.vertex_groups] != [g.name for g in new.vertex_groups]:
            raise ValueError("Region edit changed vertex groups")
        for index, vertex in enumerate(old.data.vertices):
            if index not in selected and [(g.group, g.weight) for g in vertex.groups] != [
                (g.group, g.weight) for g in new.data.vertices[index].groups
            ]:
                raise ValueError("Region edit changed weights outside the selected region")
        if bool(old.data.shape_keys) != bool(new.data.shape_keys):
            raise ValueError("Region edit changed shape-key structure")
        if old.data.shape_keys:
            old_keys, new_keys = old.data.shape_keys.key_blocks, new.data.shape_keys.key_blocks
            if [k.name for k in old_keys] != [k.name for k in new_keys]:
                raise ValueError("Region edit changed shape-key structure")
            for a, b in zip(old_keys, new_keys):
                if a.value != b.value or any(
                    (p.co - b.data[i].co).length > 1e-6
                    for i, p in enumerate(a.data)
                    if i not in selected
                ):
                    raise ValueError("Region edit changed shape keys outside the selected region")

        def materials(obj):
            return [
                (list(m.diffuse_color), m.metallic, m.roughness, node_values(m.node_tree))
                if m
                else None
                for m in obj.data.materials
            ]

        if materials(old) != materials(new):
            raise ValueError("A vertex region edit cannot change shared materials")
        selected_faces = set(region.get("faces", []))
        if [uv.name for uv in old.data.uv_layers] != [uv.name for uv in new.data.uv_layers]:
            raise ValueError("Region edit changed UV layer structure")
        protected_loops = [
            i for p in old.data.polygons if p.index not in selected_faces for i in p.loop_indices
        ]
        for a, b in zip(old.data.uv_layers, new.data.uv_layers):
            if any((a.data[i].uv - b.data[i].uv).length > 1e-6 for i in protected_loops):
                raise ValueError("Region edit changed UVs outside the selected faces")
        if any(
            p.material_index != new.data.polygons[i].material_index
            for i, p in enumerate(old.data.polygons)
            if i not in selected_faces
        ):
            raise ValueError("Region edit changed material assignment outside selected faces")
