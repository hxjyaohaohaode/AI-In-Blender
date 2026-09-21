"""blender / properties — extracted from the original add-on."""

from bpy.props import BoolProperty
from bpy.props import EnumProperty
from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.props import StringProperty
from bpy.props import CollectionProperty
from bpy.types import PropertyGroup
import bpy
from .state import secret_get, secret_set
from ..core.config import CAPABILITIES, PROTOCOL_CAPABILITIES
from ..core.agents import EXPERTS
from ..core.presets import apply_preset


def update_protocol(self, context):
    if self.protocol != "bridge":
        self.capabilities = PROTOCOL_CAPABILITIES[self.protocol] - {"vision"}


def update_preset(self, context):
    apply_preset(self.api_preset, self)


class AMA_Provider(PropertyGroup):
    name: StringProperty(name="Provider name", default="My model")
    enabled: BoolProperty(name="Enabled", default=True)
    protocol: EnumProperty(name="Protocol", items=[
        ("chat", "Chat Completions", "OpenAI-compatible text/code models"),
        ("meshy", "Meshy Text-to-3D", "Native preview and texture refinement API"),
        ("images", "Image Generations", "OpenAI-compatible image generation"),
        ("speech", "Speech Synthesis", "OpenAI-compatible audio synthesis"),
        ("transcription", "Audio Transcription", "OpenAI-compatible file transcription"),
        ("bridge", "Async Jobs Bridge", "Requires a server implementing docs/PROVIDERS.md")],
        default="chat", update=update_protocol)
    base_url: StringProperty(name="Base URL", default="https://api.openai.com/v1")
    model: StringProperty(name="Model", default="")
    api_key: StringProperty(name="API key (this session)", subtype="PASSWORD",
                            get=secret_get, set=secret_set, options={"SKIP_SAVE"})
    key_env: StringProperty(name="Key environment variable", default="AI_IN_BLENDER_API_KEY")
    capabilities: EnumProperty(name="Capabilities", options={"ENUM_FLAG"},
        items=[(c, c.upper(), c, 1 << i) for i, c in enumerate(CAPABILITIES)], default={"chat"})
    experts: EnumProperty(name="Assigned experts (empty = any)", options={"ENUM_FLAG"},
        items=[(key, value[1], value[2], 1 << i)
               for i, (key, value) in enumerate({"planner": ("chat", "Planner", "Plan workflows"), **EXPERTS,
                   "conversation": ("chat", "Conversation", "Persistent multi-turn dialogue")}.items())])
    timeout: IntProperty(name="Timeout (seconds)", default=300, min=5, max=3600)
    max_tokens: IntProperty(name="Output tokens", default=8192, min=128, max=131072)
    temperature: FloatProperty(name="Temperature", default=0.4, min=0, max=2)
    options_json: StringProperty(name="Protocol options (JSON)", default="{}")


class AMA_Properties(PropertyGroup):
    """Main addon properties stored per-scene."""

    project_id: StringProperty(name="Project identity", default="")
    thread_id: StringProperty(name="Conversation identity", default="")
    chat_input: StringProperty(name="Message / 对话", maxlen=32000)
    chat_status: StringProperty(name="Conversation status", default="Start a persistent conversation")
    chat_preview: StringProperty(name="Recent conversation", options={'SKIP_SAVE'})
    context_budget: IntProperty(name="Context budget (estimated tokens)", default=12000, min=2000, max=100000)
    semantic_compression: BoolProperty(name="Automatic semantic compression (model call)", default=True)
    memory_enabled: BoolProperty(name="Generate memory candidates (model call)", default=True)
    memory_retrieval: BoolProperty(name="Use verified memory in context", default=True)
    personal_memory: BoolProperty(name="Use confirmed personal memories", default=True)
    basic_vision: BoolProperty(name="Basic model supports vision", default=False)
    memory_status: StringProperty(name="Memory status", options={'SKIP_SAVE'})
    memory_page: IntProperty(name='Memory page',default=0,min=0,max=249)
    thread_page: IntProperty(name='Conversation page',default=0,min=0,max=10000)
    project_page: IntProperty(name='Local project page',default=0,min=0,max=10000)
    attachment_path: StringProperty(name="Input attachment", subtype='FILE_PATH')
    attachments_json: StringProperty(default="[]")
    region_json: StringProperty(default="")
    max_parallel: IntProperty(name="Concurrent model tasks", default=2, min=1, max=4)
    max_calls: IntProperty(name="Model calls per workflow", default=40, min=1, max=200)
    require_visual_review: BoolProperty(name="Require human visual approval for export", default=True)
    proactive_enabled: BoolProperty(name="Proactive local suggestions", default=True)
    proactive_status: StringProperty(options={'SKIP_SAVE'})

    # Prompt
    prompt: StringProperty(
        name="Prompt",
        description="Describe what to create",
        default="",
        maxlen=2048,
    )

    # API Settings
    api_url: StringProperty(
        name="API URL",
        description="OpenAI-compatible API endpoint",
        default="https://api.openai.com/v1",
    )
    api_key: StringProperty(
        name="API Key",
        description="API authentication key",
        subtype='PASSWORD',
        get=secret_get, set=secret_set, options={'SKIP_SAVE'},
    )
    key_env: StringProperty(name="Key environment variable", default="AI_IN_BLENDER_API_KEY")
    request_timeout: IntProperty(name="Request timeout", default=180, min=5, max=3600)
    workflow_goal: StringProperty(name="Creative brief / 创作目标", default="", maxlen=16000)
    workflow_status: StringProperty(name="Workflow status", default="Describe your goal, then create a plan")
    workflow_report: StringProperty(name="Run report", default="", subtype='FILE_PATH')
    plan_json: StringProperty(name="Plan JSON", default="")
    show_task_details: BoolProperty(name="Show task instructions", default=False)
    artifact_dir: StringProperty(name="Output directory", default="", subtype='DIR_PATH')
    input_audio: StringProperty(name="Audio input for transcription", default="", subtype='FILE_PATH')
    auto_run_plan: BoolProperty(name="Run after planning", default=False)
    review_code: BoolProperty(name="Review each generated script", default=True)
    max_repairs: IntProperty(name="Code repair attempts", default=2, min=0, max=3)
    model: StringProperty(
        name="Model",
        description="Model name",
        default="gpt-4o-mini",
    )
    temperature: FloatProperty(
        name="Temperature",
        description="Generation temperature (0.0-2.0)",
        default=0.7, min=0.0, max=2.0,
    )
    max_tokens: IntProperty(
        name="Max Tokens",
        description="Maximum tokens in response",
        default=4096, min=256, max=128000,
    )
    api_preset: EnumProperty(
        name="Preset",
        description="API preset (or Custom)",
        items=[
            ("custom", "Custom / 自定义", "Use custom API settings"),
            ("openai", "OpenAI", "OpenAI API"),
            ("deepseek", "DeepSeek", "DeepSeek API"),
            ("qwen", "Qwen (Alibaba)", "Alibaba Qwen API"),
            ("zhipu", "Zhipu (GLM)", "Zhipu GLM API"),
            ("moonshot", "Moonshot", "Moonshot API"),
            ("siliconflow", "SiliconFlow", "SiliconFlow API"),
            ("groq", "Groq", "Groq API"),
            ("together", "Together AI", "Together AI API"),
            ("openrouter", "OpenRouter", "OpenRouter API"),
            ("ollama", "Ollama (Local)", "Local Ollama API"),
            ("lmstudio", "LM Studio (Local)", "Local LM Studio API"),
            ("deepseek_v3", "DeepSeek V3", "DeepSeek V3 API"),
            ("deepseek_coder", "DeepSeek Coder", "DeepSeek Coder API"),
            ("qwen_plus", "Qwen-Plus", "Alibaba Qwen-Plus"),
            ("qwen_turbo", "Qwen-Turbo", "Alibaba Qwen-Turbo"),
            ("qwen3_coder", "Qwen3-Coder", "Alibaba Qwen3-Coder"),
            ("glm4", "GLM-4", "Zhipu GLM-4"),
            ("glm4_flash", "GLM-4-Flash", "Zhipu GLM-4-Flash (Free)"),
            ("kimi", "Kimi (Moonshot)", "Moonshot Kimi API"),
            ("siliconflow_ds", "SiliconFlow DeepSeek", "SiliconFlow DeepSeek-V3"),
            ("siliconflow_qw", "SiliconFlow Qwen3", "SiliconFlow Qwen3-8B (Free)"),
        ],
        default="custom",
        update=update_preset,
    )

    # UI state
    auto_fix: BoolProperty(
        name="Auto Fix",
        description="Automatically attempt to fix failed code",
        default=True,
    )
    show_scene_context: BoolProperty(
        name="Scene Context",
        description="Include scene context in AI request",
        default=True,
    )
    include_history: BoolProperty(
        name="Include History",
        description="Include conversation history in requests",
        default=True,
    )
    max_history_tokens: IntProperty(
        name="Max History Tokens",
        description="Maximum tokens for conversation history",
        default=16000, min=1000, max=200000,
    )

    # Last generated code (for display/execution)
    last_code: StringProperty(
        name="Last Code",
        description="Last AI-generated code",
        default="",
    )
    last_think: StringProperty(
        name="Last Think",
        description="AI's thinking process",
        default="",
    )
    status_message: StringProperty(
        name="Status",
        default="Ready",
    )

    # LOD settings
    lod_target: StringProperty(
        name="LOD Target",
        description="Object name for LOD generation",
        default="",
    )

    # Version snapshots
    version_name: StringProperty(
        name="Version Name",
        description="Name for version snapshot",
        default="",
    )

    # Asset management
    asset_name: StringProperty(
        name="Asset Name",
        description="Name for asset registration",
        default="",
    )
    asset_category: StringProperty(
        name="Asset Category",
        description="Category for asset",
        default="General",
    )

    # Batch operations
    batch_prefix: StringProperty(
        name="Prefix",
        description="Prefix for batch rename",
        default="",
    )
    batch_suffix: StringProperty(
        name="Suffix",
        description="Suffix for batch rename",
        default="",
    )
    batch_find: StringProperty(
        name="Find",
        description="Text to find in names",
        default="",
    )
    batch_replace: StringProperty(
        name="Replace",
        description="Replacement text",
        default="",
    )

    # Export
    export_engine: EnumProperty(
        name="Engine",
        items=[
            ("unity", "Unity", "Unity Engine"),
            ("unreal", "Unreal Engine", "Unreal Engine"),
            ("godot", "Godot", "Godot Engine"),
        ],
        default="unity",
    )
    export_path: StringProperty(
        name="Export Path",
        description="Export file path",
        default="//",
        subtype='DIR_PATH',
    )

    # Template params (stored as JSON string)
    template_params_json: StringProperty(
        name="Template Params",
        default="{}",
    )
    active_template: EnumProperty(
        name="Template",
        items=[
            ("chair", "Chair", "椅子"),
            ("table", "Table", "桌子"),
            ("sword", "Sword", "剑"),
            ("house", "Simple House", "简单房屋"),
            ("tree", "Tree", "树"),
            ("humanoid", "Humanoid Figure", "人形"),
            ("pillar", "Column / Pillar", "柱子"),
            ("gear", "Gear", "齿轮"),
        ],
        default="chair",
    )


class AMA_AddonPreferences(bpy.types.AddonPreferences):
    """Addon preferences for global settings."""
    bl_idname = __package__.rsplit(".", 1)[0]
    providers: CollectionProperty(type=AMA_Provider)
    provider_index: IntProperty(default=0, min=0)

    language: EnumProperty(
        name="Language / 语言",
        items=[
            ("en", "English", "English interface"),
            ("zh", "中文", "Chinese interface"),
        ],
        default="en",
    )

    # Persistent API presets (stored as JSON)
    custom_presets_json: StringProperty(
        name="Custom API Presets",
        description="JSON string of custom API presets",
        default="[]",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "language")
        from .ui_studio import draw_providers
        draw_providers(layout, self)
