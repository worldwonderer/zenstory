"""
Tests for redemption code format and checksum compatibility.
"""

import pytest

from services.subscription.redemption_service import redemption_service
from utils.code_generator import generate_code


@pytest.mark.unit
def test_generated_monthly_code_passes_format_and_checksum(monkeypatch):
    """Generated 30-day code should be accepted by validator and checksum verifier."""
    monkeypatch.setenv("REDEMPTION_CODE_HMAC_SECRET", "a" * 32)

    code = generate_code("pro", 30)

    assert redemption_service.validate_code_format(code) is True
    assert redemption_service.verify_checksum(code) is True


@pytest.mark.unit
def test_generated_two_digit_duration_code_passes_format_and_checksum(monkeypatch):
    """Generated code with longer tier-duration segment (e.g. PR10M) should still be valid."""
    monkeypatch.setenv("REDEMPTION_CODE_HMAC_SECRET", "b" * 32)

    code = generate_code("pro", 300)

    assert redemption_service.validate_code_format(code) is True
    assert redemption_service.verify_checksum(code) is True
