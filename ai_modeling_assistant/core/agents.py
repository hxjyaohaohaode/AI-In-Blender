"""Expert contracts, dependency graph validation and deterministic task state."""
from dataclasses import dataclass, field, asdict
import re
import math
import time
from .responses import extract_json

EXPERTS = {
    "modeler": ("chat", "Modeling", "Build accurate, named, well-proportioned mesh geometry."),
    "material": ("chat", "Materials", "Create PBR materials, procedural textures and UVs."),
    "rigger": ("chat", "Rigging", "Build an appropriate armature, constraints and weights."),
    "animator": ("chat", "Animation", "Create usable keyframes, actions and a sensible timeline."),
    "reviewer": ("chat", "Creative review", "Review the supplied scene facts against the goal. Return JSON with passed (boolean), summary (string), issues (array of strings). Do not claim visual inspection unless images were supplied."),
    "model3d": ("model3d", "3D generation", "Generate a 3D asset from the prompt."),
    "image": ("image", "Image / texture", "Generate an image or texture reference."),
    "video": ("video", "Video", "Generate a video clip."),
    "speech": ("speech", "Speech", "Synthesize spoken audio."),
    "transcriber": ("transcription", "Transcription", "Transcribe the supplied audio file."),
    "world": ("world", "World generation", "Generate a world or scene asset."),
    "inspector": ("builtin", "Geometry inspection", "Inspect mesh topology and report issues."),
    "exporter": ("builtin", "Export", "Export the workflow objects as GLB."),
}
CODE_EXPERTS = {"modeler", "material", "rigger", "animator"}
TERMINAL = {"succeeded", "failed", "cancelled", "blocked"}


@dataclass
class Task:
    id: str
    expert: str
    prompt: str
    depends_on: list = field(default_factory=list)
    status: str = "queued"
    attempts: int = 0
    error: str = ""
    result: dict = field(default_factory=dict)
    contract: dict = field(default_factory=dict)

    @property
    def capability(self):
        return EXPERTS[self.expert][0]


@dataclass
class Workflow:
    goal: str
    tasks: list
    created_at: float = field(default_factory=time.time)
    assembly: dict = field(default_factory=dict)

    @classmethod
    def from_plan(cls, goal, data):
        if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
            raise ValueError("Plan must contain a tasks array")
        if not 1 <= len(data["tasks"]) <= 24:
            raise ValueError("A workflow must contain between 1 and 24 tasks")
        tasks = []
        for item in data["tasks"]:
            if not isinstance(item, dict):
                raise ValueError("Each task must be an object")
            ident, expert, prompt = item.get("id"), item.get("expert"), item.get("prompt")
            deps = item.get("depends_on", [])
            if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,47}", ident):
                raise ValueError("Task IDs must be short alphanumeric identifiers")
            if expert not in EXPERTS:
                raise ValueError(f"Unknown expert: {expert}")
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000:
                raise ValueError(f"Task {ident} needs a prompt of at most 20000 characters")
            if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
                raise ValueError(f"Invalid dependencies for {ident}")
            contract = item.get('contract', {})
            if not isinstance(contract, dict):
                raise ValueError('Task contract must be an object')
            allowed = {'part_id', 'require_geometry', 'closed_mesh', 'require_materials', 'require_uv',
                       'min_vertices', 'max_vertices', 'max_extent', 'required_objects',
                       'bounds_min','bounds_max','anchor_object','anchor_position','anchor_tolerance'}
            if set(contract) - allowed:
                raise ValueError('Unknown task contract fields')
            for key in ('require_geometry','closed_mesh','require_materials','require_uv'):
                if key in contract and type(contract[key]) is not bool:
                    raise ValueError(key + ' must be a boolean')
            for key in ('min_vertices','max_vertices','max_extent','anchor_tolerance'):
                if key in contract and (type(contract[key]) not in {int,float} or not 0 <= contract[key] <= 1e9):
                    raise ValueError(key + ' is outside the contract limits')
            for key in ('bounds_min','bounds_max','anchor_position'):
                if key in contract and (not isinstance(contract[key],list) or len(contract[key]) != 3
                    or any(type(v) not in {int,float} or not math.isfinite(v) for v in contract[key])):
                    raise ValueError(key + ' must contain three finite coordinates')
            if contract.get('min_vertices',0) > contract.get('max_vertices',1e9):
                raise ValueError('Vertex limits are contradictory')
            if 'anchor_position' in contract and not isinstance(contract.get('anchor_object'),str):
                raise ValueError('Anchor position requires a named anchor object')
            if 'required_objects' in contract and (not isinstance(contract['required_objects'], list)
                    or len(contract['required_objects']) > 100 or not all(isinstance(n,str) for n in contract['required_objects'])):
                raise ValueError('required_objects must be a list of names')
            if 'part_id' in contract and (not isinstance(contract['part_id'], str)
                    or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,47}', contract['part_id'])):
                raise ValueError('Invalid assembly part ID')
            tasks.append(Task(ident, expert, prompt, list(dict.fromkeys(deps)), contract=contract))
        ids = [t.id for t in tasks]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate task IDs")
        if any(d not in ids or d == t.id for t in tasks for d in t.depends_on):
            raise ValueError("Task has a missing or self dependency")
        resolved = set()
        while len(resolved) < len(tasks):
            ready = {t.id for t in tasks if t.id not in resolved and set(t.depends_on) <= resolved}
            if not ready:
                raise ValueError("Plan contains a dependency cycle")
            resolved.update(ready)
        assembly = data.get('assembly', {})
        if not isinstance(assembly, dict) or len(str(assembly)) > 16000:
            raise ValueError('Assembly specification must be a bounded JSON object')
        return cls(goal, tasks, assembly=assembly)

    @classmethod
    def parse(cls, goal, raw):
        return cls.from_plan(goal, extract_json(raw))

    def get(self, ident):
        return next(t for t in self.tasks if t.id == ident)

    def ready(self):
        if any(t.status in {"running", "failed", "cancelled"} for t in self.tasks):
            return []
        done = {t.id for t in self.tasks if t.status == "succeeded"}
        return [t for t in self.tasks if t.status == "queued" and set(t.depends_on) <= done]

    def start(self, task):
        if task not in self.ready():
            raise ValueError("Task is not ready")
        task.status = "running"
        task.attempts += 1
        task.error = ""

    def succeed(self, task, result=None):
        if task.status != "running":
            raise ValueError("Only a running task can succeed")
        task.status = "succeeded"
        task.result = result or {}

    def fail(self, task, error):
        task.status, task.error = "failed", str(error)
        blocked = {task.id}
        changed = True
        while changed:
            changed = False
            for item in self.tasks:
                if item.status == "queued" and set(item.depends_on) & blocked:
                    item.status = "blocked"
                    blocked.add(item.id)
                    changed = True

    def cancel(self):
        for task in self.tasks:
            if task.status in {"queued", "running", "blocked"}:
                task.status = "cancelled"

    def retry(self):
        if any(t.status == "running" for t in self.tasks):
            raise ValueError("Cannot retry a running workflow")
        for task in self.tasks:
            if task.status in {"failed", "blocked", "cancelled"}:
                task.status, task.error = "queued", ""

    @property
    def complete(self):
        return all(t.status == "succeeded" for t in self.tasks)

    def snapshot(self):
        return {"schema_version": 1, "goal": self.goal, "created_at": self.created_at,
                "complete": self.complete, "assembly": self.assembly, "tasks": [asdict(t) for t in self.tasks]}


def planner_prompt(capabilities):
    available = {key: {"capability": value[0], "purpose": value[2]}
                 for key, value in EXPERTS.items()
                 if value[0] in set(capabilities) | {"builtin"}}
    return ("You are the production planner of a Blender expert team. Return ONLY JSON: "
            '{"tasks":[{"id":"model","expert":"modeler","prompt":"...","depends_on":[]}]}. '
            "Use 1-24 tasks, unique IDs, explicit dependencies. Include an assembly object describing "
            "units, axes, overall dimensions, named part interfaces/anchors and tolerances. "
            "Each task may include contract: {part_id: short unique part ID for independently built parts, "
            "require_geometry: true, closed_mesh: false, require_materials: false, require_uv: false, "
            "min_vertices: 0, max_vertices: 1000000, max_extent: 1000, required_objects: []}. "
            "Contracts can also specify bounds_min and bounds_max as [x,y,z] workspace limits, "
            "and anchor_object, anchor_position [x,y,z], anchor_tolerance for checked assembly interfaces. "
            "Independent root parts with different part_id can run concurrently; all other scene changes "
            "are ordered. Contract dimensions are in Blender scene units. For 3D workflows include an inspector after geometry and before an exporter. For "
            "media-only workflows the generated media file is the output; do not add a GLB exporter. Include "
            "reviewer after final creative changes. Only include rigging/animation/video/audio "
            "when the user requests them. Do not invent unavailable capabilities. Prompts "
            "must describe concrete outputs and build on earlier results. Available experts: "
            + str(available))
