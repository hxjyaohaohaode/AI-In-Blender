"""Usage counters. Price estimates require explicit user supplied rates."""


class CostTracker:
    def __init__(self):
        self.reset()

    def record(self, prompt_tokens=0, completion_tokens=0, cost=None):
        self.prompt += max(0, int(prompt_tokens or 0))
        self.completion += max(0, int(completion_tokens or 0))
        self.requests += 1
        if cost is not None:
            self.cost += max(0.0, float(cost))
            self.priced += 1

    def get_totals(self):
        return {"prompt_tokens": self.prompt, "completion_tokens": self.completion,
                "total_tokens": self.prompt + self.completion, "requests": self.requests,
                "cost": self.cost, "cost_known": self.requests > 0 and self.priced == self.requests}

    def reset(self):
        self.prompt = self.completion = self.requests = self.priced = 0
        self.cost = 0.0
