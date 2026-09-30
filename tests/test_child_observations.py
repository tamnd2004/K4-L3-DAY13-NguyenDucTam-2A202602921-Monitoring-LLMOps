from __future__ import annotations

from app import mock_llm, mock_rag
from app.agent import LabAgent


class RecordingGenerationClient:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    def update_current_generation(self, **kwargs) -> None:
        self.updates.append(kwargs)


def test_retrieve_and_generate_are_child_observations() -> None:
    # @observe bọc hàm gốc; __wrapped__ chứng minh hai bước có observation riêng.
    assert hasattr(mock_rag.retrieve, "__wrapped__")
    assert hasattr(mock_llm.FakeLLM.generate, "__wrapped__")


def test_generation_records_model_usage_and_cost_without_raw_prompt(monkeypatch) -> None:
    client = RecordingGenerationClient()
    monkeypatch.setattr(mock_llm, "get_langfuse_client", lambda: client)
    llm = mock_llm.FakeLLM(model="claude-sonnet-4-5")
    prompt = "Question=my email is a@b.vn " + "x" * 370

    response = mock_llm.FakeLLM.generate.__wrapped__(llm, prompt)

    [update] = client.updates
    assert update["model"] == "claude-sonnet-4-5"
    assert update["usage_details"] == {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }
    assert update["cost_details"]["total"] == LabAgent()._estimate_cost(
        response.usage.input_tokens, response.usage.output_tokens
    )
    assert update["completion_start_time"] is not None
    # Không gửi prompt đã điền câu hỏi hay câu trả lời lên trace.
    assert "input" not in update and "output" not in update
    assert "a@b.vn" not in repr(update)


def test_cost_matches_reference_price() -> None:
    assert mock_llm.usage_cost_usd(1_000_000, 1_000_000) == {
        "input": 3.0,
        "output": 15.0,
        "total": 18.0,
    }
    assert LabAgent()._estimate_cost(36, 110) == 0.001758
