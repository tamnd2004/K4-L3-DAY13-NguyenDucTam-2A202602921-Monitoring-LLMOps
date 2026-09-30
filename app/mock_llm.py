from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from .incidents import STATE
from .tracing import get_langfuse_client, observe

# Bảng giá tham khảo (USD / 1M token) của model giả lập; log và trace dùng chung
# để cost trên dashboard khớp với cost trên Langfuse.
INPUT_PRICE_PER_MTOK = 3.0
OUTPUT_PRICE_PER_MTOK = 15.0


def usage_cost_usd(input_tokens: int, output_tokens: int) -> dict[str, float]:
    input_cost = (input_tokens / 1_000_000) * INPUT_PRICE_PER_MTOK
    output_cost = (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_MTOK
    return {
        "input": round(input_cost, 6),
        "output": round(output_cost, 6),
        "total": round(input_cost + output_cost, 6),
    }


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeResponse:
    text: str
    usage: FakeUsage
    model: str
    ttft_ms: int


class FakeLLM:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model

    # Không capture input/output: prompt đã điền câu hỏi của người dùng có thể chứa PII.
    @observe(name="generation", as_type="generation", capture_input=False, capture_output=False)
    def generate(self, prompt: str) -> FakeResponse:
        started = time.perf_counter()
        time.sleep(0.05)  # mô phỏng thời điểm token đầu tiên sẵn sàng
        first_token_at = datetime.now(timezone.utc)
        ttft_ms = int((time.perf_counter() - started) * 1000)
        time.sleep(0.10)
        input_tokens = max(20, len(prompt) // 4)
        output_tokens = random.randint(80, 180)
        if STATE["cost_spike"]:
            output_tokens *= 4
        answer = (
            "Starter answer. You should improve this output logic and add better quality checks. "
            "Use retrieved context and keep responses concise."
        )
        # Prompt version được gắn qua propagate_attributes(prompt=...) ở agent.
        get_langfuse_client().update_current_generation(
            model=self.model,
            usage_details={"input": input_tokens, "output": output_tokens},
            cost_details=usage_cost_usd(input_tokens, output_tokens),
            completion_start_time=first_token_at,
        )
        return FakeResponse(
            text=answer,
            usage=FakeUsage(input_tokens, output_tokens),
            model=self.model,
            ttft_ms=ttft_ms,
        )
