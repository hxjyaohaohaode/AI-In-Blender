"""Provider configuration and transport policy."""
from dataclasses import dataclass, field, asdict
from urllib.parse import urlsplit, urlunsplit
import ipaddress

CAPABILITIES = ("chat", "model3d", "image", "video", "speech", "transcription", "world", "vision")
PROTOCOL_CAPABILITIES = {
    "chat": {"chat", "vision"}, "meshy": {"model3d"}, "images": {"image"},
    "speech": {"speech"}, "transcription": {"transcription"}, "bridge": set(CAPABILITIES),
}


def is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def validate_url(url):
    parts = urlsplit(url.strip())
    if parts.scheme not in {"https", "http"} or not parts.hostname:
        raise ValueError("Provider URL must be an absolute HTTPS URL")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Use a base URL without embedded credentials, query or fragment")
    if parts.scheme == "http" and not is_loopback(parts.hostname):
        raise ValueError("HTTP is supported only for loopback services; use HTTPS remotely")
    # Trigger validation of malformed port numbers here, before any request starts.
    _ = parts.port
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


@dataclass
class ProviderConfig:
    name: str = "Default"
    protocol: str = "chat"
    base_url: str = "https://api.openai.com/v1"
    model: str = ""
    api_key: str = field(default="", repr=False)
    timeout: int = 120
    max_tokens: int = 8192
    temperature: float = 0.4
    options: dict = field(default_factory=dict)

    def validate(self):
        self.base_url = validate_url(self.base_url)
        if self.protocol not in PROTOCOL_CAPABILITIES:
            raise ValueError(f"Unsupported provider protocol: {self.protocol}")
        if not self.model.strip() and self.protocol != "meshy":
            raise ValueError("Set the provider model identifier")
        if not 5 <= self.timeout <= 3600 or not 128 <= self.max_tokens <= 131072:
            raise ValueError("Provider timeout or output token limit is out of range")
        if not 0 <= self.temperature <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        if not isinstance(self.options, dict):
            raise ValueError("Provider options must be a JSON object")
        if 'context_window' in self.options and (type(self.options['context_window']) is not int
                or not 1024 <= self.options['context_window'] <= 2_000_000):
            raise ValueError('context_window must be an integer from 1024 to 2000000 tokens')
        return self

    def input_budget(self, requested):
        budget = min(requested,self.options.get('context_window',requested+self.max_tokens+256)-self.max_tokens-256)
        if budget < 1000:
            raise ValueError('Output reservation leaves too little input context; adjust context_window or output tokens')
        return budget

    def payload(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        allowed = cls.__dataclass_fields__
        return cls(**{k: v for k, v in value.items() if k in allowed}).validate()

    def endpoint(self, suffix):
        base = self.base_url.rstrip("/")
        return base if base.endswith(suffix) else base + suffix
