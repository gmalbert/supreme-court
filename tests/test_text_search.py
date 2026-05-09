"""Tests for utils/text_search.py — TF-IDF semantic search."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from utils.text_search import search, is_available


def test_is_available():
    """Parquet + sklearn must both be present."""
    assert is_available() is True


def test_search_returns_results():
    results = search("police cell phone warrant")
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_top_result_riley_or_carpenter():
    """The canonical Fourth Amendment phone-search cases should rank high."""
    results = search("police cell phone warrant", top_k=5)
    names = [r.get("name", "").lower() for r in results]
    assert any("riley" in n or "carpenter" in n for n in names), (
        f"Expected riley or carpenter in top-5, got: {names}"
    )


def test_search_empty_query():
    assert search("") == []


def test_search_respects_top_k():
    results = search("first amendment speech", top_k=3)
    assert len(results) <= 3


def test_search_result_has_expected_keys():
    results = search("equal protection")
    assert len(results) > 0
    required = {"name", "term", "href"}
    for r in results:
        assert required.issubset(r.keys()), f"Missing keys in: {r.keys()}"
