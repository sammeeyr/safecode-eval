"""Regression test suite protecting existing endpoint normalizer behavior."""

import pytest
from endpoint_normalizer import normalize_endpoint


def test_empty_path_defaults_to_version():
    assert normalize_endpoint("") == "/v1"
    assert normalize_endpoint("   ") == "/v1"


def test_custom_default_version():
    assert normalize_endpoint("items", default_version="v3") == "/v3/items"


def test_explicit_version_preserved():
    assert normalize_endpoint("/v2/products") == "/v2/products"
    assert normalize_endpoint("v4/orders/123") == "/v4/orders/123"


def test_redundant_slashes_collapsed():
    assert normalize_endpoint("//v1//items//") == "/v1/items"
    assert normalize_endpoint("///orders///") == "/v1/orders"


def test_legacy_aliases_expanded():
    assert normalize_endpoint("/account") == "/v1/users/me"
    assert normalize_endpoint("/profile") == "/v1/users/me/profile"
    assert normalize_endpoint("/status") == "/v1/health"


def test_legacy_alias_with_query_string():
    assert normalize_endpoint("/account?view=compact") == "/v1/users/me?view=compact"
