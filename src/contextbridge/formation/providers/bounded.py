"""Injectable sequential quota client for application factories and offline evaluation."""

import time

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.quota import TokenGate, reservation


class QuotaClient(ChatClient):
    def __init__(
        self,
        settings,
        calls=None,
        max_calls=32,
        *,
        case_id="unbound",
        stage="extraction",
        gate=None,
        transport=None,
    ):
        if type(max_calls) is not int or not 1 <= max_calls <= 40:
            raise ModuleError("INVALID_INPUT")
        if transport is None:
            super().__init__(settings)
        else:
            super().__init__(settings, transport=transport)
        self.calls = [] if calls is None else calls
        self.max_calls, self.case_id, self.stage = max_calls, case_id, stage
        self.gate = TokenGate(smooth=True) if gate is None else gate
        self.before_call = None

    def complete(self, model, prompt, payload, schema):
        with self.gate.lock:
            if len(self.calls) >= self.max_calls:
                raise ModuleError("CANCELLED")
            estimator = self.gate.estimator
            self.gate.pending_tokens = (
                estimator.estimate(self.settings, model, prompt, payload, schema)
                if estimator is not None
                else reservation(self.settings, prompt, payload, schema)
            )
            self.gate.wait()
            call = {
                "observation": None,
                "case_id": self.case_id,
                "stage": self.stage,
                "requested_model": model,
                "error_code": None,
                "retryable": False,
                "reserved_tokens": self.gate.pending_tokens,
            }
            self.calls.append(call)
            started = time.monotonic()
            self.last_observation = None
            try:
                if self.before_call is not None:
                    self.before_call()
                return super().complete(model, prompt, payload, schema)
            except ModuleError as exc:
                call.update(error_code=exc.code, retryable=exc.retryable)
                if exc.code == "PROVIDER_UNAVAILABLE":
                    self.gate.failure = exc.retryable
                raise
            finally:
                call.update(
                    observation=self.last_observation,
                    latency_ms=(time.monotonic() - started) * 1000,
                )
                self.gate.observe(self.last_observation)
                if estimator is not None:
                    estimator.observe(self.settings, model, prompt, schema, self.last_observation)
