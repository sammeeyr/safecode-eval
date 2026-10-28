"""Functional correctness tests for tiered fee calculator repair."""

import pytest
from fee_calculator import calculate_tiered_discount


def test_reject_negative_volume():
    with pytest.raises(ValueError, match="Volume cannot be negative"):
        calculate_tiered_discount(-1)


def test_tier_two_calculation():
    # 20,000 units:
    # 0..1000: 0
    # 1001..10000: 9000 * 0.05 = 450.0
    # 10001..20000: 10000 * 0.10 = 1000.0
    # Total = 1450.0
    assert calculate_tiered_discount(20000) == 1450.0


def test_tier_two_boundary():
    # 50,000 units:
    # 0..1000: 0
    # 1001..10000: 9000 * 0.05 = 450.0
    # 10001..50000: 40000 * 0.10 = 4000.0
    # Total = 4450.0
    assert calculate_tiered_discount(50000) == 4450.0


def test_tier_three_progressive_calculation():
    # 60,000 units:
    # 450.0 + 4000.0 + (10000 * 0.15 = 1500.0) = 5950.0
    assert calculate_tiered_discount(60000) == 5950.0


def test_high_volume_progressive_calculation():
    # 100,000 units:
    # 450.0 + 4000.0 + (50000 * 0.15 = 7500.0) = 11950.0
    assert calculate_tiered_discount(100000) == 11950.0

