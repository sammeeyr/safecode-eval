"""Regression tests for existing volume discount behavior."""

import pytest
from fee_calculator import calculate_tiered_discount


def test_zero_volume():
    assert calculate_tiered_discount(0) == 0.0


def test_sub_thousand_volume():
    assert calculate_tiered_discount(500) == 0.0
    assert calculate_tiered_discount(1000) == 0.0


def test_mid_tier_volume():
    # 5000 volume: (5000 - 1000) * 0.05 = 200.0
    assert calculate_tiered_discount(5000) == 200.0


def test_tier_one_cap():
    # 10000 volume: (10000 - 1000) * 0.05 = 450.0
    assert calculate_tiered_discount(10000) == 450.0

