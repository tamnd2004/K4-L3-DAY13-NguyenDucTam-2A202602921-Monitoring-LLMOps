from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app
from app.pii import hash_user_id

REQUEST_ID_RE = re.compile(r"req-[0-9a-f]{8}")
ENRICHMENT_FIELDS = ("correlation_id", "user_id_hash", "session_id", "feature", "model", "env")


def _post_chats(requests: list[tuple[dict, dict]]) -> list[httpx.Response]:
    async def send_all() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return [
                await client.post("/chat", json=body, headers=headers)
                for body, headers in requests
            ]

    return asyncio.run(send_all())


def _read_logs(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]


def _body(message: str = "Explain traces") -> dict:
    return {"user_id": "student-01", "session_id": "session-01", "feature": "qa", "message": message}


def test_request_id_header_is_propagated_to_response_and_logs(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    [response] = _post_chats([(_body(), {"x-request-id": "req-1a2b3c4d"})])

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-1a2b3c4d"
    assert float(response.headers["x-response-time-ms"]) >= 0
    assert response.json()["correlation_id"] == "req-1a2b3c4d"

    records = [r for r in _read_logs(log_path) if r.get("service") == "api"]
    assert [r["event"] for r in records] == ["request_received", "response_sent"]
    for record in records:
        for field in ENRICHMENT_FIELDS:
            assert record.get(field), f"{record['event']} thiếu {field}"
        assert record["correlation_id"] == "req-1a2b3c4d"
        assert record["user_id_hash"] == hash_user_id("student-01")
        assert "student-01" not in json.dumps(record)


def test_missing_or_invalid_request_id_gets_new_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    responses = _post_chats(
        [
            (_body(), {}),
            (_body(), {"x-request-id": "a@b.vn"}),
            (_body(), {"x-request-id": "req-XYZ"}),
        ]
    )

    ids = [r.headers["x-request-id"] for r in responses]
    assert all(REQUEST_ID_RE.fullmatch(i) for i in ids)
    assert len(set(ids)) == len(ids), "mỗi request phải có correlation ID riêng"


def test_pii_is_scrubbed_before_log_is_written(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    message = "a@b.vn 0901234567 001099012345 4111 1111 1111 1111"

    _post_chats([(_body(message), {"x-request-id": "req-0badc0de"})])

    raw = log_path.read_text(encoding="utf-8")
    for pii in ("a@b.vn", "0901234567", "001099012345", "4111 1111 1111 1111"):
        assert pii not in raw
    received = next(r for r in _read_logs(log_path) if r["event"] == "request_received")
    assert received["payload"]["message_preview"] == (
        "[REDACTED_EMAIL] [REDACTED_PHONE_VN] [REDACTED_CCCD] [REDACTED_CREDIT_CARD]"
    )


def test_scrub_event_covers_nested_payload_and_exception_text() -> None:
    event = {
        "ts": "2026-09-30T00:00:00Z",
        "correlation_id": "req-1a2b3c4d",
        "user_id_hash": "123456789012",
        "event": "request_failed",
        "payload": {"detail": {"contacts": ["a@b.vn", "0901234567"]}},
        "exception": "ValueError: bad card 4111111111111111",
    }

    out = logging_config.scrub_event(None, "error", event)

    assert out["payload"]["detail"]["contacts"] == ["[REDACTED_EMAIL]", "[REDACTED_PHONE_VN]"]
    assert out["exception"] == "ValueError: bad card [REDACTED_CREDIT_CARD]"
    # Field hệ thống giữ nguyên dù trông giống số CCCD.
    assert out["user_id_hash"] == "123456789012"
    assert out["correlation_id"] == "req-1a2b3c4d"
