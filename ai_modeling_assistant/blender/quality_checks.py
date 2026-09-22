"""Material dependency and bound-action checks used by native delivery gates."""

import math
from pathlib import Path
import bpy


def material_issues(material):
    if not material.use_nodes or material.node_tree is None:
        return []
    errors, visited = [], set()

    def inspect(tree):
        if tree.as_pointer() in visited:
            return
        visited.add(tree.as_pointer())
        for node in tree.nodes:
            if node.type == "TEX_IMAGE" and any(s.is_linked for s in node.outputs):
                image = node.image
                if image is None:
                    errors.append("connected image texture has no image")
                elif image.source != "GENERATED" and not image.packed_file:
                    path = bpy.path.abspath(image.filepath, library=image.library)
                    if image.source == "TILED":
                        paths = [path.replace("<UDIM>", str(t.number)) for t in image.tiles]
                    else:
                        paths = [path]
                    if not paths or any(not Path(p).is_file() for p in paths):
                        errors.append("missing external texture: " + image.name)
                if image is not None and not all(image.size):
                    errors.append("undecodable texture: " + image.name)
            if node.type == "GROUP" and node.node_tree:
                inspect(node.node_tree)

    outputs = [
        n for n in material.node_tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output
    ]
    if not any(
        any(n.inputs.get(k) and n.inputs[k].is_linked for k in ("Surface", "Volume"))
        for n in outputs
    ):
        errors.append("material has no connected active output")
    inspect(material.node_tree)
    return errors


def bound_curves(action, slot=None):
    if action is None:
        return []
    if getattr(action, "is_action_layered", False):
        if slot is None:
            return []
        return [
            curve
            for layer in action.layers
            for strip in layer.strips
            for bag in getattr(strip, "channelbags", ())
            if bag.slot_handle == slot.handle
            for curve in bag.fcurves
        ]
    return list(getattr(action, "fcurves", ()))


def animation_evidence(objects):
    owners, seen_trees = set(), set()

    def tree_owners(tree):
        if tree is None or tree.as_pointer() in seen_trees:
            return
        seen_trees.add(tree.as_pointer())
        owners.add(tree)
        for node in tree.nodes:
            tree_owners(getattr(node, "node_tree", None))

    for obj in objects:
        owners.add(obj)
        if obj.data:
            owners.add(obj.data)
            keys = getattr(obj.data, "shape_keys", None)
            if keys:
                owners.add(keys)
        for slot in obj.material_slots:
            if slot.material:
                owners.add(slot.material)
                tree_owners(slot.material.node_tree)
    frames, errors, channels = set(), [], 0
    for owner in sorted(owners, key=lambda o: o.name):
        data = getattr(owner, "animation_data", None)
        if not data:
            continue
        actions = []
        if data.action:
            actions.append((data.action, getattr(data, "action_slot", None), None))
        if data.use_nla:
            solo = any(t.is_solo and not t.mute for t in data.nla_tracks)
            for track in data.nla_tracks:
                if track.mute or (solo and not track.is_solo):
                    continue
                for strip in track.strips:
                    if strip.action and not strip.mute and strip.influence > 0:
                        actions.append((strip.action, getattr(strip, "action_slot", None), strip))
        for action, slot, strip in actions:
            for curve in bound_curves(action, slot):
                if curve.mute or not curve.is_valid:
                    continue
                points = list(curve.keyframe_points) or list(curve.sampled_points)
                if not points:
                    continue
                channels += 1
                for point in points:
                    if not all(math.isfinite(v) for v in point.co):
                        errors.append(owner.name + ": non-finite animation keyframe")
                        continue
                    frame = point.co.x
                    if strip:
                        if not strip.action_frame_start <= frame <= strip.action_frame_end:
                            continue
                        frame = strip.frame_start + (frame - strip.action_frame_start) * strip.scale
                        if not strip.frame_start <= frame <= strip.frame_end:
                            continue
                    frames.add(round(frame, 5))
                if strip and points:
                    frames.update((float(strip.frame_start), float(strip.frame_end)))
    return {"channels": channels, "keyframe_times": sorted(frames), "errors": sorted(set(errors))}


def sample_frames(scene, contract, animation):
    explicit = contract.get("sample_frames")
    if explicit:
        return explicit
    if not contract.get("require_animation"):
        return [scene.frame_current]
    start, end = contract.get("animation_range", [scene.frame_start, scene.frame_end])
    frames = {int(start), int(end), round((start + end) / 2)}
    # Include keyframe discontinuities as well as uniform interior samples.
    frames.update(round(start + (end - start) * fraction) for fraction in (0.25, 0.75))
    candidates = [round(f) for f in animation["keyframe_times"] if start <= f <= end]
    if candidates:
        frames.update(candidates[:: max(1, len(candidates) // 6)][:6])
    return sorted(frames)
