"""core / presets — extracted from the original add-on."""




def apply_preset(preset_name: str, props) -> None:
    """Apply an API preset to properties."""
    presets = {
        "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
        "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
        "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
        "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        "moonshot": ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
        "siliconflow": ("https://api.siliconflow.cn/v1", "Qwen/Qwen2.5-7B-Instruct"),
        "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
        "together": ("https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
        "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct"),
        "ollama": ("http://localhost:11434/v1", "llama3.1"),
        "lmstudio": ("http://localhost:1234/v1", "local-model"),
        # Chinese model presets
        "deepseek_v3": ("https://api.deepseek.com/v1", "deepseek-chat"),
        "deepseek_coder": ("https://api.deepseek.com/v1", "deepseek-coder"),
        "qwen_plus": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
        "qwen_turbo": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
        "qwen3_coder": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3-coder-next"),
        "glm4": ("https://open.bigmodel.cn/api/paas/v4", "glm-4"),
        "glm4_flash": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
        "kimi": ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
        "siliconflow_ds": ("https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3"),
        "siliconflow_qw": ("https://api.siliconflow.cn/v1", "Qwen/Qwen3-8B"),
    }
    if preset_name in presets:
        url, model = presets[preset_name]
        props.api_url = url
        props.model = model
