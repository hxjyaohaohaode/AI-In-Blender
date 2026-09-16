"""Content fingerprints protect human edits from stale agent commits."""
from array import array
import hashlib
import json
import uuid
import bpy


def ensure_ids(objects):
    seen = set()
    for obj in objects:
        ident = obj.get('ama_asset_id')
        if not isinstance(ident, str) or ident in seen:
            ident = uuid.uuid4().hex
            obj['ama_asset_id'] = ident
        seen.add(ident)


def rna_values(value):
    result = {}
    for prop in value.bl_rna.properties:
        name = prop.identifier
        if name in {'rna_type', 'name', 'name_full', 'execution_time', 'is_active', 'is_override_data'} or prop.type == 'COLLECTION':
            continue
        try:
            item = getattr(value, name)
            if prop.type == 'POINTER':
                if isinstance(item, bpy.types.ID):
                    result[name] = item.get('ama_asset_id', item.name)
            elif getattr(prop, 'is_array', False):
                result[name] = list(item)
            elif isinstance(item, (str, int, float, bool)):
                result[name] = item
            elif isinstance(item, set):
                result[name] = sorted(item)
        except (AttributeError, TypeError, RuntimeError):
            continue
    return result


def animation_values(obj):
    data = obj.animation_data
    if not data or not data.action:
        return None
    action = data.action
    curves = list(getattr(action, 'fcurves', ()))
    for layer in getattr(action, 'layers', ()):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', ()):
                curves.extend(bag.fcurves)
    return [(f.data_path, f.array_index, [(list(k.co), list(k.handle_left), list(k.handle_right), k.interpolation)
            for k in f.keyframe_points]) for f in curves]


def socket_value(value):
    if isinstance(value,bpy.types.ID):
        result = {'id':value.get('ama_asset_id',value.name)}
        if isinstance(value,bpy.types.Object):
            result['transform'] = [list(row) for row in value.matrix_world]
        return result
    if value is None or isinstance(value,(str,int,float,bool)):
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
        return {'reference':tree.name}
    seen.add(tree.as_pointer())
    return {'nodes':[(n.name,n.bl_idname,rna_values(n),dict(n.items()),
        [(s.identifier,socket_value(getattr(s,'default_value',''))) for s in n.inputs],
        [(s.identifier,socket_value(getattr(s,'default_value',''))) for s in n.outputs],
        node_values(getattr(n,'node_tree',None),seen)) for n in tree.nodes],
        'links':[(l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in tree.links]}


def fingerprint(objects):
    bpy.context.view_layer.update()
    digest = hashlib.sha256()
    def add(data):
        digest.update(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8'))
    for obj in sorted(objects, key=lambda o: (o.get('ama_asset_id', ''), o.name)):
        if obj.mode == 'EDIT':
            obj.update_from_editmode()
        add((obj.name, obj.get('ama_asset_id', ''), obj.type, [list(row) for row in obj.matrix_world],
             list(obj.location), list(obj.scale), list(obj.rotation_euler), list(obj.rotation_quaternion),
             list(obj.delta_location), list(obj.delta_scale), list(obj.delta_rotation_euler),
             obj.parent.get('ama_asset_id', obj.parent.name) if obj.parent else None,
             [(rna_values(m),dict(m.items())) for m in obj.modifiers], [rna_values(c) for c in obj.constraints], animation_values(obj)))
        add([node_values(m.node_group) for m in obj.modifiers if m.type=='NODES'])
        if obj.type == 'MESH':
            mesh = obj.data
            for values, prop, size, code in ((mesh.vertices,'co',3,'f'), (mesh.edges,'vertices',2,'i'),
                (mesh.loops,'vertex_index',1,'i'), (mesh.polygons,'loop_total',1,'i'), (mesh.polygons,'material_index',1,'i')):
                buf = array(code, [0]) * (len(values)*size)
                values.foreach_get(prop, buf)
                digest.update(buf.tobytes())
            for layer in mesh.uv_layers:
                buf = array('f', [0]) * (len(layer.data)*2)
                layer.data.foreach_get('uv', buf)
                digest.update(buf.tobytes())
            if mesh.shape_keys:
                for key in mesh.shape_keys.key_blocks:
                    add((key.name, key.value, [list(p.co) for p in key.data]))
        elif obj.type == 'ARMATURE':
            add([(b.name, list(b.head_local), list(b.tail_local), b.parent.name if b.parent else '') for b in obj.data.bones])
        elif obj.type in {'CURVE', 'SURFACE', 'FONT'}:
            add(rna_values(obj.data))
            add([([list(p.co) for p in s.points], [(list(p.co),list(p.handle_left),list(p.handle_right)) for p in s.bezier_points]) for s in obj.data.splines])
        elif obj.type in {'LIGHT','CAMERA'}:
            add(rna_values(obj.data))
            add(animation_values(obj.data))
        for slot in obj.material_slots:
            mat = slot.material
            if mat:
                add((mat.name, list(mat.diffuse_color), mat.metallic, mat.roughness))
                if mat.node_tree:
                    add(node_values(mat.node_tree))
    return digest.hexdigest()


def check_region(objects, regions):
    """Validate captured anchors against the exact revision the user selected."""
    by_id = {o.get('ama_asset_id'):o for o in objects}
    if regions and set(by_id) != {r['asset_id'] for r in regions}:
        raise ValueError('Precise edit targets must exactly match the captured object region')
    for region in regions:
        obj = by_id.get(region['asset_id'])
        if obj is None or fingerprint([obj]) != region['fingerprint']:
            raise ValueError("Captured edit region is stale; reselect and capture after your last edit")


def region_preserved(before, after, regions):
    originals = {o.get('ama_asset_id'):o for o in before}
    candidates = {o.get('ama_asset_id'):o for o in after}
    for region in regions:
        if 'vertices' not in region:
            continue
        old, new = originals[region['asset_id']], candidates.get(region['asset_id'])
        if new is None or old.type != 'MESH' or new.type != 'MESH':
            raise ValueError("Region edit must retain the original mesh object")
        if len(old.data.vertices) != len(new.data.vertices) or len(old.data.polygons) != len(new.data.polygons):
            raise ValueError("Precise region edits cannot change topology; use a separate remeshing task")
        if [tuple(p.vertices) for p in old.data.polygons] != [tuple(p.vertices) for p in new.data.polygons]:
            raise ValueError("Precise region edit changed topology")
        selected = set(region['vertices'])
        for index, vertex in enumerate(old.data.vertices):
            if index not in selected and (vertex.co-new.data.vertices[index].co).length > 1e-6:
                raise ValueError("Generated code modified vertices outside the selected region")
        if old.matrix_world != new.matrix_world:
            raise ValueError("A region edit cannot transform the entire object")
        if [rna_values(m) for m in old.modifiers] != [rna_values(m) for m in new.modifiers]:
            raise ValueError('A vertex region edit cannot change global modifiers')
        def materials(obj):
            return [(list(m.diffuse_color), m.metallic, m.roughness,
                     node_values(m.node_tree)) if m else None for m in obj.data.materials]
        if materials(old) != materials(new):
            raise ValueError('A vertex region edit cannot change shared materials')
        selected_faces = set(region.get('faces',[]))
        if any(p.material_index != new.data.polygons[i].material_index for i,p in enumerate(old.data.polygons) if i not in selected_faces):
            raise ValueError('Region edit changed material assignment outside selected faces')
