"""blender / context_helpers — extracted from the original add-on."""

from ..blender.scene import SceneContextGenerator
import bpy


class PlanningEngine:
    """
    Decomposes complex requests into structured multi-part plans.
    This is the 'brain' that gives the AI holistic understanding.
    """

    @staticmethod
    def create_plan(request: str, scene_context: str) -> str:
        """Create a structured plan for complex modeling requests."""
        plan = f"""
===== SCENE PLANNING REQUEST =====
The user wants to create: {request}

Current scene state:
{scene_context}

You MUST plan before coding. Follow this structure:

STEP 1 — PART DECOMPOSITION
List every distinct geometric part needed. For each part specify:
- Part name (English, descriptive)
- Geometric approach (primitive/extrude/boolean/subdivision/curve)
- Approximate dimensions (meters)
- Material type

STEP 2 — SPATIAL LAYOUT
Plan where each part goes in 3D space. Ensure parts connect properly.
- Use a consistent coordinate system (Z-up, Y-forward)
- Parts should not overlap unless intentionally
- Leave appropriate gaps for joints, hinges, etc.

STEP 3 — DEPENDENCY ORDER
Which parts must be created first? Boolean operations need both objects.
Modifiers reference other objects. Plan the creation order.

STEP 4 — CODE STRUCTURE
Plan your code as:
1. Create all base geometry first
2. Apply transforms and modifiers
3. Create and assign materials
4. Final cleanup (normals, remove doubles, smooth shading)

Now write the code following your plan. Each part in its own try/except block.
"""
        return plan


class RefinementEngine:
    """
    Enables iterative refinement — improve existing models, not just create new ones.
    """

    @staticmethod
    def build_refinement_prompt(user_request: str) -> str:
        """
        Build a prompt that tells the AI to refine existing objects
        rather than creating from scratch.
        """
        selected = bpy.context.selected_objects
        if not selected:
            return user_request

        parts = []
        parts.append(f"REFINEMENT REQUEST: {user_request}")
        parts.append("")
        parts.append("The following objects already exist and need to be improved:")
        parts.append("You MUST modify these existing objects, NOT create new ones.")
        parts.append("Use bmesh to edit their geometry in place.")
        parts.append("")

        for obj in selected:
            if obj.type != 'MESH':
                continue
            desc = SceneContextGenerator._describe_object(obj, "")
            parts.append(f"OBJECT: {desc}")

            # Describe current geometry
            mesh = obj.data
            parts.append(f"  Current shape: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces")

            # Bounding box
            if mesh.vertices:
                import bmesh
                bm = bmesh.new()
                bm.from_mesh(mesh)
                bbox_min = tuple(min(v.co[i] for v in bm.verts) for i in range(3))
                bbox_max = tuple(max(v.co[i] for v in bm.verts) for i in range(3))
                bm.free()
                parts.append(f"  BBox: ({bbox_min[0]:.2f},{bbox_min[1]:.2f},{bbox_min[2]:.2f}) to ({bbox_max[0]:.2f},{bbox_max[1]:.2f},{bbox_max[2]:.2f})")

        parts.append("")
        parts.append("Use bmesh operations to modify the existing mesh:")
        parts.append("- bmesh.ops.extrude_face_region() for adding detail")
        parts.append("- bmesh.ops.bevel() for edge refinement")
        parts.append("- bmesh.ops.subdivide_edges() for more geometry")
        parts.append("- bmesh.ops.translate() / scale() / rotate() for shape changes")
        parts.append("- bmesh.ops.delete() for removing unwanted parts")
        parts.append("Always call bm.to_mesh(obj.data) and bm.free() when done.")

        return "\n".join(parts)
