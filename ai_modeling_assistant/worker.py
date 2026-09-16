"""Private worker entrypoint. Requests arrive through stdin, never process arguments."""
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_modeling_assistant.core.config import ProviderConfig
from ai_modeling_assistant.core.providers import chat
from ai_modeling_assistant.core.media import generate


def main():
    config = None
    try:
        raw = sys.stdin.buffer.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Request exceeds 2 MB")
        data = json.loads(raw.decode("utf-8"))
        config = ProviderConfig.from_dict(data["config"])
        if data["action"] == "chat" and config.protocol == "chat":
            result = chat(config, data["messages"], data.get("system_prompt", ""))
        else:
            result = generate(config, data["capability"], data["prompt"], data["output_dir"],
                              data.get("input_path", ""), data.get("inputs", []))
    except Exception as exc:
        message = str(exc)
        if config is not None and config.api_key:
            message = message.replace(config.api_key, "[redacted]")
        result = {"error": message[:1000] or type(exc).__name__}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
