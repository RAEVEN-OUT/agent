import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineMetrics:
    """Per-message latency + decision trace.

    Logged once per inbound message so you can see which cascade step answered
    and what it cost. This is what makes cost regressions visible.
    """

    steps: dict[str, float] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def record(self, name: str, t0: float) -> None:
        self.steps[name] = round((time.perf_counter() - t0) * 1000, 2)

    def mark(self, key: str, value: Any) -> None:
        self.trace[key] = value

    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.llm_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def as_dict(self) -> dict[str, Any]:
        return {
            "steps_ms": self.steps,
            "trace": self.trace,
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
