"""Rough latency and cost tracking for LLM usage.

Token counts are estimated (chars / 4) — good enough for a run ledger and
budget awareness, not for billing. Prices are USD per 1M tokens.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field

PRICES_PER_MTOK = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gemini-flash-latest": {"input": 0.10, "output": 0.40},
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class CallRecord:
    label: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0


@dataclass
class UsageTracker:
    calls: list[CallRecord] = field(default_factory=list)

    @contextmanager
    def track(self, label: str, model: str, prompt_text: str = ""):
        record = CallRecord(label=label, model=model, input_tokens=estimate_tokens(prompt_text))
        start = time.perf_counter()
        try:
            yield record
        finally:
            record.seconds = time.perf_counter() - start
            self.calls.append(record)

    def record_output(self, label: str, output_text: str) -> None:
        for call in reversed(self.calls):
            if call.label == label and call.output_tokens == 0:
                call.output_tokens = estimate_tokens(output_text)
                return

    def summary(self) -> dict:
        total_cost = 0.0
        total_seconds = 0.0
        for call in self.calls:
            price = PRICES_PER_MTOK.get(call.model, {"input": 0.0, "output": 0.0})
            total_cost += (
                call.input_tokens * price["input"] + call.output_tokens * price["output"]
            ) / 1_000_000
            total_seconds += call.seconds
        return {
            "calls": [vars(c) for c in self.calls],
            "total_input_tokens": sum(c.input_tokens for c in self.calls),
            "total_output_tokens": sum(c.output_tokens for c in self.calls),
            "total_seconds_llm": round(total_seconds, 2),
            "estimated_cost_usd": round(total_cost, 6),
        }
