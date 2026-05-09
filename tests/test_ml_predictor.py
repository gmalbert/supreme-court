"""Tests for utils/ml_predictor.py — pure-logic functions, no I/O needed."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from utils.ml_predictor import (
    extract_circuit,
    parse_split,
    normalise_split,
    _infer_outcome,
    is_trained,
    load_meta,
    CURRENT_JUSTICES,
)


# ── extract_circuit ───────────────────────────────────────────────────────────

def test_extract_circuit_ninth():
    assert extract_circuit("United States Court of Appeals for the Ninth Circuit") == "9th Circuit"


def test_extract_circuit_dc():
    assert extract_circuit("D.C. Circuit Court of Appeals") == "D.C. Circuit"


def test_extract_circuit_state():
    result = extract_circuit("Supreme Court of California")
    assert result == "State Supreme Court"


def test_extract_circuit_empty():
    assert extract_circuit("") == "Other"


def test_extract_circuit_unknown():
    assert extract_circuit("Some random tribunal") == "Other"


# ── parse_split ───────────────────────────────────────────────────────────────

def _vote(v: str) -> dict:
    return {"vote": v}


def test_parse_split_five_four():
    votes = [_vote("majority")] * 5 + [_vote("dissent")] * 4
    assert parse_split(votes) == "5-4"


def test_parse_split_nine_zero():
    votes = [_vote("majority")] * 9
    assert parse_split(votes) == "9-0"


def test_parse_split_unanimous_with_concurrence():
    votes = [_vote("majority")] * 7 + [_vote("concurrence")] * 2
    assert parse_split(votes) == "9-0"


def test_parse_split_too_few_votes():
    # Fewer than 5 total → return None
    votes = [_vote("majority")] * 3
    assert parse_split(votes) is None


def test_parse_split_empty():
    assert parse_split([]) is None


# ── normalise_split ───────────────────────────────────────────────────────────

def test_normalise_split_six_three():
    assert normalise_split("6-3") == "6-3"


def test_normalise_split_nine_zero():
    assert normalise_split("9-0") == "9-0"


def test_normalise_split_fallback():
    # malformed → falls back to "5-4"
    assert normalise_split("invalid") == "5-4"


def test_normalise_split_empty():
    assert normalise_split("") == "5-4"


# ── _infer_outcome ────────────────────────────────────────────────────────────

def test_infer_outcome_petitioner_wins():
    detail = {
        "name": "Smith v. Jones",
        "decisions": [{"winning_party": "Smith"}],
    }
    assert _infer_outcome(detail) == 1  # petitioner won → reverse


def test_infer_outcome_respondent_wins():
    detail = {
        "name": "Smith v. Jones",
        "decisions": [{"winning_party": "Jones"}],
    }
    assert _infer_outcome(detail) == 0  # respondent won → affirm


def test_infer_outcome_no_winner():
    detail = {"name": "Smith v. Jones", "decisions": [{}]}
    assert _infer_outcome(detail) is None


def test_infer_outcome_no_decisions():
    assert _infer_outcome({}) is None


# ── model loading (non-crashing even when untrained) ─────────────────────────

def test_is_trained_returns_bool():
    result = is_trained()
    assert isinstance(result, bool)


def test_load_meta_returns_dict():
    meta = load_meta()
    assert isinstance(meta, dict)


# ── CURRENT_JUSTICES sanity ───────────────────────────────────────────────────

def test_current_justices_count():
    assert len(CURRENT_JUSTICES) == 9


def test_current_justices_roberts_present():
    assert "Roberts" in CURRENT_JUSTICES
