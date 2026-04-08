# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
import pytest

from rxon.validators import is_valid_identifier, validate_identifier


def test_valid_identifiers() -> None:
    assert is_valid_identifier("worker-1")
    assert is_valid_identifier("job_123")
    assert is_valid_identifier("Complex-ID_01")


def test_invalid_identifiers() -> None:
    # Negative cases: unforeseen injection attempts or bad formatting
    assert not is_valid_identifier("worker 1")
    assert not is_valid_identifier("worker/1")
    assert not is_valid_identifier("../etc/passwd")
    assert not is_valid_identifier("job; DROP TABLE")
    assert not is_valid_identifier("id$@#")
    assert not is_valid_identifier("")


def test_validate_identifier_raises() -> None:
    validate_identifier("valid-id")
    with pytest.raises(ValueError, match="Invalid test_id"):
        validate_identifier("invalid id!", name="test_id")
