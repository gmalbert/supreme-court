"""
Incremental Parquet refresh — fetches only the current and previous SCOTUS
terms directly from the Oyez API and merges the results into the existing
Parquet files.

Run from the repo root:
    python scripts/refresh_parquet.py [--terms N]

Arguments:
    --terms N   Number of most-recent terms to refresh (default: 2)

On a fresh clone (no Parquet files yet) it falls back to a full rebuild
by reading any locally-cached JSON in data_files/oyez_data/, then filling
the rest from the live API.
"""

import argparse
import datetime
import json
import os
import sys
import time

import pandas as pd
import requests

REPO_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_PARQUET    = os.path.join(REPO_ROOT, "data", "cases_by_term.parquet")
DETAIL_PARQUET   = os.path.join(REPO_ROOT, "data", "case_detail.parquet")
CASES_JSON_DIR   = os.path.join(REPO_ROOT, "data_files", "oyez_data", "cases")
DETAIL_JSON_DIR  = os.path.join(REPO_ROOT, "data_files", "oyez_data", "case_detail")

BASE_URL  = "https://api.oyez.org"
HEADERS   = {"Accept": "application/json", "User-Agent": "SCOTUS-ParquetRefresh/1.0"}
RATE_WAIT = 0.2   # seconds between live API calls

SCALAR_FIELDS = [
    "ID", "name", "href", "docket_number", "term",
    "first_party", "second_party", "first_party_label", "second_party_label",
    "manner_of_jurisdiction", "facts_of_the_case", "question", "conclusion",
    "description", "justia_url", "argument2_url", "view_count",
]
JSON_FIELDS = [
    "timeline", "lower_court", "citation", "decided_by", "heard_by",
    "decisions", "advocates", "oral_argument_audio", "opinion_announcement",
    "written_opinion", "related_cases", "additional_docket_numbers", "location",
]
CASES_COLS = [
    "term", "ID", "name", "href", "docket_number", "question", "description",
    "justia_url", "view_count", "cite_volume", "cite_page", "cite_year",
]


# ── API helpers ────────────────────────────────────────────────────────────────

def _get(url: str) -> dict | list | None:
    """GET url with rate limiting; return parsed JSON or None on error."""
    time.sleep(RATE_WAIT)
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  WARN: {url} — {exc}", flush=True)
        return None


def _fetch_cases_for_term(term: int) -> list[dict]:
    """Fetch the case list for one term (tries local JSON cache first)."""
    local = os.path.join(CASES_JSON_DIR, str(term), "cases.json")
    if os.path.exists(local):
        with open(local, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data

    print(f"  API: cases for term {term}", flush=True)
    data = _get(f"{BASE_URL}/cases?filter=term:{term}&per_page=300&page=0")
    return data if isinstance(data, list) else []


def _fetch_case_detail(href: str) -> dict | None:
    """Fetch case detail (tries local JSON cache first)."""
    # Derive expected local path from the href
    path_part = href.replace(BASE_URL, "").strip("/")  # e.g. cases/2024/23-191
    parts = path_part.split("/")
    if len(parts) >= 3:  # cases / <term> / <docket>
        local = os.path.join(DETAIL_JSON_DIR, parts[1],
                             "_".join(parts) + ".json")
        if os.path.exists(local):
            with open(local, encoding="utf-8") as f:
                return json.load(f)

    data = _get(href)
    return data if isinstance(data, dict) else None


# ── Row builders ───────────────────────────────────────────────────────────────

def _case_row(c: dict, term: int) -> dict:
    citation = c.get("citation") or {}
    return {
        "term":          c.get("term") or int(term),
        "ID":            c.get("ID"),
        "name":          c.get("name"),
        "href":          c.get("href"),
        "docket_number": c.get("docket_number"),
        "question":      c.get("question"),
        "description":   c.get("description"),
        "justia_url":    c.get("justia_url"),
        "view_count":    c.get("view_count"),
        "cite_volume":   citation.get("volume")  if isinstance(citation, dict) else None,
        "cite_page":     citation.get("page")    if isinstance(citation, dict) else None,
        "cite_year":     citation.get("year")    if isinstance(citation, dict) else None,
    }


def _detail_row(d: dict) -> dict:
    row = {f: d.get(f) for f in SCALAR_FIELDS}
    for f in JSON_FIELDS:
        v = d.get(f)
        row[f] = json.dumps(v, ensure_ascii=False) if v is not None else None
    return row


# ── Main refresh logic ─────────────────────────────────────────────────────────

def current_term() -> int:
    today = datetime.date.today()
    return today.year if today.month >= 10 else today.year - 1


def refresh(n_terms: int = 2) -> None:
    os.makedirs(os.path.join(REPO_ROOT, "data"), exist_ok=True)

    # Load existing Parquet files (may not exist on first run)
    try:
        cases_df = pd.read_parquet(CASES_PARQUET)
        print(f"Loaded existing cases Parquet: {len(cases_df):,} rows")
    except Exception:
        cases_df = pd.DataFrame(columns=CASES_COLS)
        print("No existing cases Parquet — starting fresh")

    try:
        detail_df = pd.read_parquet(DETAIL_PARQUET)
        print(f"Loaded existing detail Parquet: {len(detail_df):,} rows")
    except Exception:
        detail_df = pd.DataFrame(columns=SCALAR_FIELDS + JSON_FIELDS)
        print("No existing detail Parquet — starting fresh")

    ct = current_term()
    terms_to_refresh = list(range(ct, ct - n_terms, -1))
    print(f"Refreshing terms: {terms_to_refresh}")

    new_case_rows   = []
    new_detail_rows = []

    for term in terms_to_refresh:
        cases = _fetch_cases_for_term(term)
        print(f"  term {term}: {len(cases)} cases", flush=True)

        for c in cases:
            new_case_rows.append(_case_row(c, term))

            href = c.get("href", "")
            if not href:
                continue
            detail = _fetch_case_detail(href)
            if detail:
                new_detail_rows.append(_detail_row(detail))

    if not new_case_rows:
        print("No data fetched — nothing to update.")
        return

    # Drop the refreshed terms from existing data, then append fresh rows
    new_terms_set = {r["term"] for r in new_case_rows}

    cases_df  = cases_df[~cases_df["term"].isin(new_terms_set)]
    detail_df = detail_df[~detail_df["href"].isin(
        {r["href"] for r in new_detail_rows}
    )]

    cases_df  = pd.concat([cases_df,  pd.DataFrame(new_case_rows)],   ignore_index=True)
    detail_df = pd.concat([detail_df, pd.DataFrame(new_detail_rows)], ignore_index=True)

    # Write back
    cases_df.to_parquet(CASES_PARQUET,  index=False, compression="zstd")
    detail_df.to_parquet(DETAIL_PARQUET, index=False, compression="zstd")

    print(f"\nDone.")
    print(f"  cases_by_term.parquet : {len(cases_df):,} rows  "
          f"({os.path.getsize(CASES_PARQUET)/1e6:.2f} MB)")
    print(f"  case_detail.parquet   : {len(detail_df):,} rows  "
          f"({os.path.getsize(DETAIL_PARQUET)/1e6:.2f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", type=int, default=2,
                        help="Number of most-recent terms to refresh (default: 2)")
    args = parser.parse_args()
    refresh(args.terms)
