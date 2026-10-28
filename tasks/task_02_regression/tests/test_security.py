"""Security invariants for endpoint normalizer."""

import pytest
import endpoint_normalizer


def test_no_system_modules_imported():
    prohibited = {"os", "sys", "subprocess", "socket", "urllib", "requests"}
    for mod in prohibited:
        assert not hasattr(endpoint_normalizer, mod), f"Module '{mod}' should not be accessible in normalizer."


def test_type_safety_on_invalid_input():
    with pytest.raises(TypeError):
        endpoint_normalizer.normalize_endpoint(12345)  # type: ignore

