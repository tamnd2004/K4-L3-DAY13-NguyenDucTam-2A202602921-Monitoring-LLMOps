from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import dashboard
from scripts.validate_dashboard import load_dashboard_config

NOW = datetime(2026, 9, 30, 3, 30, 30, tzinfo=timezone.utc)
CONFIG = load_dashboard_config(Path(__file__).resolve().parents[1] / "config" / "dashboard.yaml")


def _rec(minutes_ago: float, event: str, **fields) -> dict:
    return {"_ts": NOW - timedelta(minutes=minutes_ago), "event": event, **fields}


def _ok(minutes_ago: float, latency_ms: int = 150, cost_usd: float = 0.002) -> list[dict]:
    return [
        _rec(minutes_ago, "request_received"),
        _rec(minutes_ago, "response_sent", latency_ms=latency_ms, ttft_ms=50, tokens_in=30,
             tokens_out=120, cost_usd=cost_usd, quality_score=0.9, tool_success=True),
    ]


def _failed(minutes_ago: float) -> list[dict]:
    return [
        _rec(minutes_ago, "request_received"),
        _rec(minutes_ago, "request_failed", error_type="RuntimeError", tool_success=False),
    ]


def test_retrieval_success_counts_response_sent_and_request_failed() -> None:
    records = [r for i in range(9) for r in _ok(i)] + _failed(1)

    errors = dashboard.build_dashboard(records, CONFIG, now=NOW)["panels"]["errors"]

    assert errors["summary"]["tool_success_rate_pct"] == 90.0
    assert errors["summary"]["error_rate_pct"] == 10.0
    assert errors["summary"]["count_by_value"] == {"RuntimeError": 1}
    assert errors["status"] == "breach"  # error rate 10% > threshold 2%


def test_window_is_last_60_minutes_bucketed_per_minute() -> None:
    records = _ok(0) + _ok(59) + _ok(61)  # bản ghi 61 phút trước nằm ngoài cửa sổ

    data = dashboard.build_dashboard(records, CONFIG, now=NOW)

    assert len(data["labels"]) == 60
    traffic = data["panels"]["traffic"]
    assert traffic["summary"]["count"] == 2
    assert traffic["series"]["rate_per_minute"][-1] == 1
    assert data["refresh_seconds"] == 30


def test_thresholds_come_from_contract() -> None:
    slow = [r for i in range(20) for r in _ok(i, latency_ms=3500, cost_usd=0.2)]

    panels = dashboard.build_dashboard(slow, CONFIG, now=NOW)["panels"]

    assert panels["latency"]["summary"]["p95"] == 3500
    assert panels["latency"]["status"] == "breach"  # p95 <= 3000 ms
    assert panels["cost"]["summary"]["total"] == 4.0
    assert panels["cost"]["status"] == "breach"  # total <= 2.5 USD
    assert panels["quality"]["status"] == "ok"  # mean 0.9 >= 0.75
    assert {p["unit"] for p in panels.values()} == {
        "ms", "requests_per_minute", "percent", "usd", "tokens", "score_0_to_1",
    }


def test_empty_window_reports_no_data() -> None:
    data = dashboard.build_dashboard([], CONFIG, now=NOW)

    assert data["panels"]["latency"]["status"] == "no_data"
    assert data["panels"]["quality"]["status"] == "no_data"
