"""Regression tests for existing volume discount behavior."""

import pytest
from fee_calculator import calculate_tiered_discount


def test_zero_volume():
    res = calculate_tiered_discount(0)
    assert type(res) is float
    assert res == 0.0


def test_sub_thousand_volume():
    res_500 = calculate_tiered_discount(500)
    res_1000 = calculate_tiered_discount(1000)
    assert type(res_500) is float and type(res_1000) is float
    assert res_500 == 0.0
    assert res_1000 == 0.0


def test_mid_tier_volume():
    # 5000 volume: (5000 - 1000) * 0.05 = 200.0
    res = calculate_tiered_discount(5000)
    assert type(res) is float
    assert res == 200.0


def test_tier_one_cap():
    # 10000 volume: (10000 - 1000) * 0.05 = 450.0
    res = calculate_tiered_discount(10000)
    assert type(res) is float
    assert res == 450.0

