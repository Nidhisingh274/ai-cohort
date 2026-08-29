"""
Day 29: tests for the Day 25 PII redaction. Deterministic - regex only,
no LLM calls.
"""

from redact_pii import redact_pii


def test_redacts_member_id():
    result = redact_pii("Member M1001 filed a claim.")
    assert "M1001" not in result
    assert "[MEMBER_ID]" in result


def test_redacts_claim_id():
    result = redact_pii("Claim C1001 is pending.")
    assert "C1001" not in result
    assert "[CLAIM_ID]" in result


def test_redacts_email_and_phone():
    result = redact_pii("Contact me at john.doe@example.com or 555-123-4567.")
    assert "john.doe@example.com" not in result
    assert "555-123-4567" not in result
    assert "[EMAIL]" in result
    assert "[PHONE]" in result


def test_non_string_input_returned_unchanged():
    assert redact_pii(None) is None
    assert redact_pii(123) == 123


def test_clean_text_unaffected():
    """Text with no PII should pass through unchanged."""
    text = "The Gold PPO plan has a $2,000 deductible."
    assert redact_pii(text) == text