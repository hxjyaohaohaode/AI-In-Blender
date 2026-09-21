"""One conservative request accounting policy for chat, planning and maintenance.

This is a UTF-8 estimate, not a vendor tokenizer. Vision reserves are configurable
because providers use different image accounting. Input overflow fails explicitly.
"""

from .memory import tokens


def estimate_messages(messages, system="", *, image_tokens=4096):
    if type(image_tokens) is not int or not 256 <= image_tokens <= 65536:
        raise ValueError("vision_tokens_per_image must be between 256 and 65536")
    used = tokens(system) + 16
    for message in messages:
        content = message.get("content")
        used += 12
        if isinstance(content, str):
            used += tokens(content)
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    used += tokens(part["text"]) + 4
                elif part.get("type") == "image_url":
                    used += image_tokens
                else:
                    raise ValueError("Unknown request content cannot be budgeted")
        else:
            raise ValueError("Invalid request content")
    return used


def ensure_budget(config, messages, system="", *, requested=12000):
    limit = config.input_budget(requested)
    used = estimate_messages(
        messages, system, image_tokens=config.options.get("vision_tokens_per_image", 4096)
    )
    if used > limit:
        raise ValueError(
            f"Request needs approximately {used} input tokens, budget is {limit}. "
            "Reduce attachments or context, or configure a larger model context window. "
            "The current instruction has not been truncated."
        )
    return {
        "estimated_input_tokens": used,
        "input_budget": limit,
        "reserved_output_tokens": config.max_tokens,
    }
