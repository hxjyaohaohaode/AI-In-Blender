"""Bounded conversation storage; prior responses never become system instructions."""
from copy import deepcopy
import math


class ConversationHistory:
    def __init__(self, max_tokens=16000):
        self.max_tokens = max(1, int(max_tokens))
        self.messages = []

    @staticmethod
    def _estimate_tokens(text):
        return max(1, math.ceil(len(text.encode("utf-8")) / 3))

    def _total_tokens(self):
        return sum(self._estimate_tokens(m["content"]) + 4 for m in self.messages)

    def add(self, role, content):
        if role not in {"user", "assistant", "system"} or not isinstance(content, str):
            raise ValueError("Invalid conversation message")
        self.messages.append({"role": role, "content": content})
        self._compress_if_needed()

    def _compress_if_needed(self):
        # Each iteration removes a message: termination does not depend on text length.
        while len(self.messages) > 1 and self._total_tokens() > self.max_tokens:
            self.messages.pop(0)
        if self.messages and self._total_tokens() > self.max_tokens:
            message = self.messages[-1]
            budget = max(0, (self.max_tokens - 5) * 3)
            message["content"] = message["content"].encode("utf-8")[-budget:].decode(
                "utf-8", errors="ignore"
            ) if budget else ""
            if self._total_tokens() > self.max_tokens:
                self.messages.clear()
        while self.messages and self.messages[0]["role"] == "assistant":
            self.messages.pop(0)

    def get_messages(self):
        self._compress_if_needed()
        return deepcopy(self.messages)

    def clear(self):
        self.messages.clear()

    def get_stats(self):
        return {"count": len(self.messages), "estimated_tokens": self._total_tokens()}
