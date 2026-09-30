from app.pii import scrub_text, summarize_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD của tôi là 001099012345")
    assert "001099012345" not in out
    assert out == "CCCD của tôi là [REDACTED_CCCD]"


def test_scrub_credit_card_formats() -> None:
    card_numbers = (
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "4111111111111111",
    )

    for card_number in card_numbers:
        out = scrub_text(f"Card: {card_number}")
        assert card_number not in out
        assert out == "Card: [REDACTED_CREDIT_CARD]"


def test_scrub_passport() -> None:
    out = scrub_text("Passport C1234567 hết hạn")
    assert "C1234567" not in out
    assert "REDACTED_PASSPORT" in out


def test_scrub_does_not_touch_normal_numbers() -> None:
    text = "Latency P95 is 2500 ms for 10 requests in 2026"
    assert scrub_text(text) == text


def test_scrub_mixed_pii_in_one_message() -> None:
    # Cùng input dùng cho evidence 05-pii-redaction. CCCD đứng ngay trước số thẻ
    # nên test này còn bảo vệ thứ tự pattern (CCCD phải được che trước thẻ).
    out = summarize_text("a@b.vn 0901234567 001099012345 4111 1111 1111 1111")
    assert out == (
        "[REDACTED_EMAIL] [REDACTED_PHONE_VN] [REDACTED_CCCD] [REDACTED_CREDIT_CARD]"
    )
