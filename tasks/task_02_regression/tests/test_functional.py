"""Functional correctness tests for query string and fragment extension."""

import pytest
from endpoint_normalizer import normalize_endpoint


def test_query_string_preserved():
    result = normalize_endpoint("/users?sort=asc&page=2")
    assert result == "/v1/users?sort=asc&page=2"


def test_fragment_preserved():
    result = normalize_endpoint("/docs#section-intro")
    assert result == "/v1/docs#section-intro"


def test_query_and_fragment_combined():
    result = normalize_endpoint("/search?q=security#results")
    assert result == "/v1/search?q=security#results"


def test_multiple_query_params():
    result = normalize_endpoint("/products?cat=books&in_stock=true&limit=25")
    assert result == "/v1/products?cat=books&in_stock=true&limit=25"


def test_query_string_with_explicit_version():
    result = normalize_endpoint("/v3/reports?format=pdf")
    assert result == "/v3/reports?format=pdf"
