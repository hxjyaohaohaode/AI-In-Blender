"""Chat protocol adapter. Other model protocols live in media.py."""
from .config import ProviderConfig
from .http import HTTPClient
from .responses import parse_chat


def chat(config, messages, system_prompt=""):
    config.validate()
    full = ([{"role": "system", "content": system_prompt}] if system_prompt else [])
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"user", "assistant", "system"}:
            raise ValueError("Chat messages require a valid role")
        content = message.get('content')
        if isinstance(content,list):
            if message['role'] != 'user' or not content or len(content)>20:
                raise ValueError('Only user messages may carry 1-20 multimodal parts')
            for part in content:
                if not isinstance(part,dict):
                    raise ValueError('Invalid multimodal part')
                if part.get('type')=='text' and isinstance(part.get('text'),str):
                    continue
                if part.get('type')=='image_url' and config.options.get('vision'):
                    url = part.get('image_url',{}).get('url','')
                    if isinstance(url,str) and url.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,','https://')):
                        continue
                raise ValueError('Unsupported multimodal part or vision capability is disabled')
        elif not isinstance(content,str):
            raise ValueError('Chat content must be text or validated multimodal parts')
        full.append({"role": message["role"], "content": message["content"]})
    payload = {"model": config.model, "messages": full}
    token_field = config.options.get("token_field", "max_tokens")
    if token_field not in {"max_tokens", "max_completion_tokens"}:
        raise ValueError("token_field must be max_tokens or max_completion_tokens")
    payload[token_field] = config.max_tokens
    if not config.options.get("omit_temperature", False):
        payload["temperature"] = config.temperature
    return parse_chat(HTTPClient(config).call(config.endpoint("/chat/completions"), payload))


class APIEngine:
    """Synchronous compatibility facade for scripts; Blender UI uses ProcessJob."""
    def __init__(self, api_url, api_key, model, temperature=0.4, max_tokens=8192):
        self.config = ProviderConfig(base_url=api_url, api_key=api_key, model=model,
                                     temperature=temperature, max_tokens=max_tokens)

    def chat(self, messages, system_prompt=""):
        try:
            return chat(self.config, messages, system_prompt)
        except Exception as exc:
            return {"content": "", "prompt_tokens": 0, "completion_tokens": 0,
                    "cost": None, "error": str(exc)}
