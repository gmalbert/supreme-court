"""Tests for utils/local_data.py — data-loading helpers."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


def test_infer_issue_area_criminal_procedure():
    from utils.local_data import infer_issue_area
    result = infer_issue_area({
        "question": "Does a warrantless search of a vehicle violate the Fourth Amendment?",
        "description": "Police conducted a search without a warrant.",
    })
    assert result == "Criminal Procedure"


def test_infer_issue_area_first_amendment():
    from utils.local_data import infer_issue_area
    result = infer_issue_area({
        "question": "Does the government's restriction on free speech violate the First Amendment?",
        "description": "A speaker was arrested for political expression.",
    })
    assert result == "First Amendment"


def test_infer_issue_area_unknown():
    from utils.local_data import infer_issue_area
    result = infer_issue_area({})
    assert isinstance(result, str)  # Returns some string, even if "Unknown"


def test_strip_html():
    from utils.local_data import strip_html
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_empty():
    from utils.local_data import strip_html
    assert strip_html("") == ""
    assert strip_html(None) in ("", None)  # graceful with None


def test_fetch_oyez_local_only():
    """In LOCAL_ONLY mode, fetch_oyez should return None or a cached dict — never raise."""
    from utils.local_data import fetch_oyez
    result = fetch_oyez("https://api.oyez.org/cases/2020/19-783")
    assert result is None or isinstance(result, (dict, list))


def test_get_cases_by_term_returns_list():
    from utils.oyez_api import get_cases_by_term
    cases = get_cases_by_term(2020)
    assert isinstance(cases, list)


def test_get_recent_terms():
    from utils.oyez_api import get_recent_terms
    terms = get_recent_terms(n=5)
    assert isinstance(terms, list)
    assert len(terms) <= 5
    assert all(isinstance(t, int) for t in terms)
