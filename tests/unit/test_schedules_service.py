"""Unit tests for schedule service."""

import pytest

from backend.services.schedule_service import validate_cron_expression


def test_valid_cron_expressions():
    valid = [
        "0 9 * * *",
        "*/5 * * * *",
        "0 0 1 * *",
        "30 18 * * 1-5",
        "0 0 * * 0",
    ]
    for expr in valid:
        assert validate_cron_expression(expr), f"Should be valid: {expr}"


def test_invalid_cron_expressions():
    invalid = [
        "not-a-cron",
        "* * * *",       # Only 4 fields
        "60 * * * *",    # Invalid minute
        "",
    ]
    for expr in invalid:
        assert not validate_cron_expression(expr), f"Should be invalid: {expr}"
