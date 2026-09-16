"""Strict model output extraction, independent of the Blender runtime."""
import ast
import json
import re


def extract_code(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("The model returned no text")
    blocks = re.findall(r"^\s*```([^\n]*)\n(.*?)^\s*```\s*$", raw, re.M | re.S)
    if blocks:
        code = "\n\n".join(body.strip() for lang, body in blocks
                           if lang.strip().lower() in {"python", "py", ""})
        if not code:
            raise ValueError("The reply has no Python code block")
    else:
        code = raw.strip()
        if "```" in code:
            raise ValueError("Incomplete code block; request a complete response")
    ast.parse(code)
    return code


def extract_json(raw):
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", raw, re.S | re.I)
    return json.loads(blocks[0] if blocks else raw.strip())


def parse_chat(body):
    try:
        choice = body["choices"][0]
        if choice.get("finish_reason") in {"length", "content_filter"}:
            raise ValueError("Model response was truncated or filtered; no code was executed")
        content = choice["message"]["content"]
        if isinstance(content, list):
            content = "\n".join(part.get("text", "") for part in content
                                if isinstance(part, dict) and part.get("type") == "text")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Model returned no text content")
        usage = body.get("usage") or {}
        prompt = max(0, int(usage.get("prompt_tokens") or 0))
        completion = max(0, int(usage.get("completion_tokens") or 0))
        return {"content": content, "prompt_tokens": prompt,
                "completion_tokens": completion, "cost": None, "error": ""}
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Invalid chat completion response") from exc
