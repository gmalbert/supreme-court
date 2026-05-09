"""Tests for data files — parquet schema validation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import pandas as pd

_REPO = os.path.dirname(os.path.dirname(__file__))


def test_circuit_stats_parquet_exists():
    path = os.path.join(_REPO, "data_files", "circuit_stats.parquet")
    assert os.path.exists(path), f"Missing: {path}"


def test_circuit_stats_parquet_schema():
    path = os.path.join(_REPO, "data_files", "circuit_stats.parquet")
    df = pd.read_parquet(path)
    required_cols = {"term", "name", "circuit", "lower_court", "outcome", "issue_area"}
    assert required_cols.issubset(set(df.columns)), (
        f"Missing columns: {required_cols - set(df.columns)}"
    )


def test_circuit_stats_parquet_nonempty():
    path = os.path.join(_REPO, "data_files", "circuit_stats.parquet")
    df = pd.read_parquet(path)
    assert len(df) > 1000, f"Expected >1000 rows, got {len(df)}"


def test_circuit_stats_outcome_values():
    path = os.path.join(_REPO, "data_files", "circuit_stats.parquet")
    df = pd.read_parquet(path)
    valid_outcomes = {"Reversed/Vacated", "Affirmed", "Remanded", "Unknown"}
    found = set(df["outcome"].unique())
    assert found.issubset(valid_outcomes), f"Unexpected outcome values: {found - valid_outcomes}"


def test_advocate_stats_parquet_exists():
    path = os.path.join(_REPO, "data_files", "advocate_stats.parquet")
    assert os.path.exists(path), f"Missing: {path}"


def test_advocate_stats_parquet_schema():
    path = os.path.join(_REPO, "data_files", "advocate_stats.parquet")
    df = pd.read_parquet(path)
    required_cols = {"advocate", "appearances", "wins", "known_outcomes", "win_rate"}
    assert required_cols.issubset(set(df.columns))


def test_cases_by_term_parquet_exists():
    path = os.path.join(_REPO, "data", "cases_by_term.parquet")
    assert os.path.exists(path), f"Missing: {path}"


def test_case_detail_parquet_exists():
    path = os.path.join(_REPO, "data", "case_detail.parquet")
    assert os.path.exists(path), f"Missing: {path}"


def test_case_detail_parquet_min_rows():
    path = os.path.join(_REPO, "data", "case_detail.parquet")
    df = pd.read_parquet(path, columns=["name"])
    assert len(df) > 5000, f"Expected >5000 rows, got {len(df)}"
