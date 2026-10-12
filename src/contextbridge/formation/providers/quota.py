"""Local sequential quota guard. Provider/account limits remain authoritative."""

import json
import time
from collections import deque
from threading import Lock

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.chat import strict_schema


def reservation(settings, prompt, payload, schema):
    # Byte upper bound, not a tokenizer or a measured usage observation. Include schema
    # and 512 tokens of framing margin; refuse large requests rather than truncate evidence.
    raw = json.dumps([prompt, payload, strict_schema(schema)], ensure_ascii=False)
    return len(raw.encode("utf-8")) + settings.max_output_tokens + 512


class TokenGate:
    def __init__(
        self,
        *,
        tokens_per_minute=8000,
        max_total_tokens=50000,
        interval=3.1,
        clock=time.monotonic,
        sleeper=time.sleep,
    ):
        if not (
            type(tokens_per_minute) is int
            and 128 <= tokens_per_minute <= 8000
            and type(max_total_tokens) is int
            and 128 <= max_total_tokens <= 50000
            and type(interval) in (int, float)
            and 3.1 <= interval <= 60
        ):
            raise ValueError("Invalid local quota limits")
        self.limit, self.budget, self.interval = tokens_per_minute, max_total_tokens, interval
        self.clock, self.sleeper = clock, sleeper
        self.lock = Lock()
        self.window = deque()
        self.total = 0
        self.last_started = None
        self.failure = None
        self.budget_reason = "call_budget"
        self.pending_tokens = 0
        self.required_tokens = None
        self.token_stopped = False
        self.active = None

    def wait(self):
        if self.failure is not None:
            raise ModuleError("PROVIDER_UNAVAILABLE", retryable=self.failure)
        if self.token_stopped:
            raise ModuleError("CANCELLED")
        amount = self.pending_tokens
        if type(amount) is not int or amount < 1:
            raise ModuleError("INVALID_INPUT")
        if amount > self.limit or self.total + amount > self.budget:
            self.budget_reason = "token_budget"
            self.required_tokens = amount
            self.token_stopped = True
            raise ModuleError("CANCELLED")
        while True:
            now = self.clock()
            while self.window and now - self.window[0][0] >= 61:
                self.window.popleft()
            pacing = (
                max(0, self.interval - (now - self.last_started))
                if self.last_started is not None
                else 0
            )
            capacity = (
                0
                if sum(item[1] for item in self.window) + amount <= self.limit
                else self.window[0][0] + 61 - now
            )
            delay = max(pacing, capacity)
            if delay <= 0:
                break
            self.sleeper(delay)
        self.last_started = self.clock()
        self.active = [self.last_started, amount]
        self.window.append(self.active)
        self.total += amount

    def observe(self, observation):
        if self.active is None:
            return
        values = [getattr(observation, name, None) for name in ("input_tokens", "output_tokens")]
        if all(type(value) is int and value >= 0 for value in values):
            actual = sum(values)
            self.total += actual - self.active[1]
            self.active[1] = actual
            if actual > self.limit:
                self.required_tokens = actual
                self.budget_reason = "token_budget"
                self.token_stopped = True
        self.active = None
