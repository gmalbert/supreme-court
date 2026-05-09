"""Tests for utils/oyez_api.py — local-data paths, no live network calls."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import pandas as pd


# ── get_cases_by_term ─────────────────────────────────────────────────────────

def test_get_cases_by_term_returns_list():
    from utils.oyez_api import get_cases_by_term
    result = get_cases_by_term(2020)
    assert isinstance(result, list)


def test_get_cases_by_term_nonempty_known_term():
    from utils.oyez_api import get_cases_by_term
    cases = get_cases_by_term(2020)
    # parquet has cases for 2020 term
    assert len(cases) > 0


def test_get_cases_by_term_fields():
    from utils.oyez_api import get_cases_by_term
    cases = get_cases_by_term(2020)
    assert cases, "Expected at least one case for term 2020"
    c = cases[0]
    assert "name" in c
    assert "href" in c


def test_get_cases_by_term_unknown_term_returns_empty_or_list():
    from utils.oyez_api import get_cases_by_term
    # Very old term not in parquet — should return list (possibly empty)
    result = get_cases_by_term(1850)
    assert isinstance(result, list)


# ── get_recent_terms ──────────────────────────────────────────────────────────

def test_get_recent_terms_length():
    from utils.oyez_api import get_recent_terms
    terms = get_recent_terms(n=5)
    assert len(terms) == 5


def test_get_recent_terms_all_ints():
    from utils.oyez_api import get_recent_terms
    terms = get_recent_terms(n=10)
    assert all(isinstance(t, int) for t in terms)


def test_get_recent_terms_descending():
    from utils.oyez_api import get_recent_terms
    terms = get_recent_terms(n=5)
    assert terms == sorted(terms, reverse=True)


# ── get_case_detail ───────────────────────────────────────────────────────────

def _first_href_for_term(term: int) -> str | None:
    """Helper: grab the first href from the parquet for a known term."""
    from utils.oyez_api import get_cases_by_term
    cases = get_cases_by_term(term)
    for c in cases:
        if c.get("href"):
            return c["href"]
    return None


def test_get_case_detail_returns_dict_or_none():
    from utils.oyez_api import get_case_detail
    href = _first_href_for_term(2020)
    if href is None:
        pytest.skip("No href found for term 2020")
    result = get_case_detail(href)
    assert result is None or isinstance(result, dict)


def test_get_case_detail_known_case_has_name():
    from utils.oyez_api import get_case_detail
    href = _first_href_for_term(2020)
    if href is None:
        pytest.skip("No href found for term 2020")
    detail = get_case_detail(href)
    if detail is None:
        pytest.skip("Case detail not available in local data")
    assert "name" in detail
    assert isinstance(detail["name"], str)


def test_get_case_detail_invalid_href_returns_none():
    from utils.oyez_api import get_case_detail
    result = get_case_detail("https://api.oyez.org/cases/9999/99-9999")
    assert result is None


# ── search_cases ──────────────────────────────────────────────────────────────

def test_search_cases_returns_list():
    from utils.oyez_api import search_cases
    results = search_cases("Arizona")
    assert isinstance(results, list)


def test_search_cases_results_have_name():
    from utils.oyez_api import search_cases
    results = search_cases("Arizona")
    for c in results:
        assert "name" in c


def test_search_cases_max_twenty():
    from utils.oyez_api import search_cases
    results = search_cases("v.")  # very broad query
    assert len(results) <= 20


def test_search_cases_empty_query_returns_list():
    from utils.oyez_api import search_cases
    results = search_cases("")
    assert isinstance(results, list)


# ── extract_court_journey ─────────────────────────────────────────────────────

def test_extract_court_journey_empty_detail():
    from utils.oyez_api import extract_court_journey
    steps = extract_court_journey({})
    assert isinstance(steps, list)


def test_extract_court_journey_with_lower_court():
    from utils.oyez_api import extract_court_journey
    detail = {
        "lower_court": {"name": "Ninth Circuit Court of Appeals"},
        "decided_by": {"name": "Roberts Court (2021-2022)"},
        "decisions": [],
    }
    steps = extract_court_journey(detail)
    assert len(steps) >= 1
    assert any("Ninth Circuit" in s["court"] for s in steps)
