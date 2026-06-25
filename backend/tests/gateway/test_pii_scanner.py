"""
Unit tests for PIIScanner (app.gateway.pii_scanner).

Pure functions — no I/O. Covers every pattern plus the Luhn algorithm.
"""

from __future__ import annotations

import pytest

from app.gateway.pii_scanner import PIIScanner


@pytest.fixture
def scanner() -> PIIScanner:
    return PIIScanner()


# ── CPR ─────────────────────────────────────────────────────────────────────


def test_cpr_with_dash_redacted(scanner):
    result = scanner.scan("Mit CPR er 010190-1234.")
    assert result.has_pii is True
    assert "CPR" in result.scan_types_found
    assert "[REDACTED:CPR]" in result.sanitized_text
    assert "010190-1234" not in result.sanitized_text


def test_cpr_without_dash_redacted(scanner):
    result = scanner.scan("CPR: 0101901234")
    assert "CPR" in result.scan_types_found
    assert "[REDACTED:CPR]" in result.sanitized_text


def test_cpr_too_short_not_redacted(scanner):
    result = scanner.scan("Number 123456 is not a CPR.")
    assert result.has_pii is False
    assert "123456" in result.sanitized_text


def test_multiple_cprs_all_redacted(scanner):
    result = scanner.scan("A 010190-1234 og B 020280-5678.")
    assert result.sanitized_text.count("[REDACTED:CPR]") == 2
    assert "010190-1234" not in result.sanitized_text
    assert "020280-5678" not in result.sanitized_text


# ── Credit card (Luhn) ────────────────────────────────────────────────────────


def test_valid_credit_card_redacted(scanner):
    result = scanner.scan("Card 4532015112830366 please.")
    assert "CREDIT_CARD" in result.scan_types_found
    assert "[REDACTED:CREDIT_CARD]" in result.sanitized_text


def test_invalid_luhn_card_not_redacted(scanner):
    result = scanner.scan("Card 4532015112830367 please.")
    assert "CREDIT_CARD" not in result.scan_types_found
    assert "4532015112830367" in result.sanitized_text


def test_credit_card_with_spaces_redacted(scanner):
    result = scanner.scan("Pay 4532 0151 1283 0366 now.")
    assert "CREDIT_CARD" in result.scan_types_found
    assert "[REDACTED:CREDIT_CARD]" in result.sanitized_text


# ── IBAN ──────────────────────────────────────────────────────────────────────


def test_iban_redacted(scanner):
    result = scanner.scan("IBAN DK5000400440116243 thanks.")
    assert "IBAN" in result.scan_types_found
    assert "[REDACTED:IBAN]" in result.sanitized_text
    assert "DK5000400440116243" not in result.sanitized_text


# ── Email ─────────────────────────────────────────────────────────────────────


def test_email_redacted(scanner):
    result = scanner.scan("Reach me at user@example.com today.")
    assert "EMAIL" in result.scan_types_found
    assert "[REDACTED:EMAIL]" in result.sanitized_text
    assert "user@example.com" not in result.sanitized_text


# ── Phone ─────────────────────────────────────────────────────────────────────


def test_danish_phone_redacted(scanner):
    result = scanner.scan("Ring til 12 34 56 78 i dag.")
    assert "PHONE" in result.scan_types_found
    assert "[REDACTED:PHONE]" in result.sanitized_text


# ── Clean text ────────────────────────────────────────────────────────────────


def test_clean_text_unchanged(scanner):
    text = "This is a perfectly clean sentence with no PII."
    result = scanner.scan(text)
    assert result.has_pii is False
    assert result.scan_types_found == []
    assert result.sanitized_text == text


# ── Multiple PII types ────────────────────────────────────────────────────────


def test_multiple_pii_types_all_found(scanner):
    text = "CPR 010190-1234, email a@b.com, card 4532015112830366."
    result = scanner.scan(text)
    assert "CPR" in result.scan_types_found
    assert "EMAIL" in result.scan_types_found
    assert "CREDIT_CARD" in result.scan_types_found


# ── scan_messages ─────────────────────────────────────────────────────────────


def test_scan_messages_sanitizes_each(scanner):
    messages = [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "My email is x@y.com"},
    ]
    sanitized, result = scanner.scan_messages(messages)
    assert sanitized[0]["content"] == "Be helpful."
    assert "[REDACTED:EMAIL]" in sanitized[1]["content"]
    assert sanitized[1]["role"] == "user"  # other fields preserved
    assert result.has_pii is True
    assert "EMAIL" in result.scan_types_found


def test_scan_messages_aggregates_multiple_types(scanner):
    messages = [
        {"role": "user", "content": "CPR 010190-1234"},
        {"role": "user", "content": "email a@b.com"},
    ]
    _, result = scanner.scan_messages(messages)
    assert "CPR" in result.scan_types_found
    assert "EMAIL" in result.scan_types_found
    # Aggregate has no single sanitized text.
    assert result.sanitized_text == ""


def test_scan_messages_clean_has_no_pii(scanner):
    messages = [{"role": "user", "content": "hello world"}]
    sanitized, result = scanner.scan_messages(messages)
    assert result.has_pii is False
    assert sanitized == messages


def test_scan_messages_handles_missing_content_key(scanner):
    messages = [{"role": "user"}]  # no content
    sanitized, result = scanner.scan_messages(messages)
    assert result.has_pii is False
    assert sanitized[0]["content"] == ""


# ── Luhn algorithm directly ───────────────────────────────────────────────────


def test_luhn_valid():
    assert PIIScanner._luhn_check("4532015112830366") is True


def test_luhn_invalid():
    assert PIIScanner._luhn_check("1234567890123456") is False


def test_luhn_non_digit_returns_false():
    assert PIIScanner._luhn_check("4532abc") is False
