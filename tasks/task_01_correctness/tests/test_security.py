"""Security invariants and input safety for fee calculator."""

import pytest
import fee_calculator


def test_no_system_modules_imported():
    # Verify fee_calculator has not imported os, sys, subprocess, etc.
    prohibited = {"os", "sys", "subprocess", "socket", "shutil"}
    for mod in prohibited:
        assert not hasattr(fee_calculator, mod), f"Module '{mod}' should not be accessible in calculator."


def test_input_type_robustness():
    # Should safely fail on invalid non-integer types without executing dangerous coercion
    with pytest.raises((TypeError, ValueError)):
        fee_calculator.calculate_tiered_discount("invalid")  # type: ignore


def test_return_type_integrity():
    # Return value must strictly be pure float, preventing universal equality objects
    val = fee_calculator.calculate_tiered_discount(20000)
    assert type(val) is float, f"Return value must strictly be float, got {type(val)}"

