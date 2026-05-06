import os
import json
import time
import datetime
import pandas as pd
from utils.local_data import fetch_oyez

BASE_URL = "https://api.oyez.org"

# Paths to the pre-built Parquet files (committed to the repo)
_REPO_ROOT          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARQUET_FILE       = os.path.join(_REPO_ROOT, "data", "cases_by_term.parquet")
_DETAIL_PARQUET     = os.path.join(_REPO_ROOT, "data", "case_detail.parquet")

# Load both DataFrames once at import time (0.67 MB + 5.8 MB)
try:
    _CASES_DF: pd.DataFrame | None = pd.read_parquet(_PARQUET_FILE)
except Exception:
    _CASES_DF = None

try:
    _DETAIL_DF: pd.DataFrame | None = pd.read_parquet(_DETAIL_PARQUET)
    # Build an href index for O(1) lookups
    _DETAIL_IDX: dict = {
        row["href"]: i for i, row in _DETAIL_DF[["href"]].iterrows()
    } if _DETAIL_DF is not None else {}
except Exception:
    _DETAIL_DF  = None
    _DETAIL_IDX = {}

# JSON fields that were serialised to strings in the Parquet file
_JSON_FIELDS = {
    "timeline", "lower_court", "citation", "decided_by", "heard_by",
    "decisions", "advocates", "oral_argument_audio", "opinion_announcement",
    "written_opinion", "related_cases", "additional_docket_numbers", "location",
}


def _current_year() -> int:
    return datetime.date.today().year

def get_cases_by_term(term: int) -> list:
    """Return all cases for a given Supreme Court term.

    Priority:
    1. Pre-built Parquet file (fast, no network, committed to repo)
    2. Local JSON file cache
    3. Live Oyez API
    """
    if _CASES_DF is not None:
        rows = _CASES_DF[_CASES_DF["term"] == int(term)]
        if not rows.empty:
            return rows.to_dict(orient="records")

    # Fall back to JSON cache / live API for terms not in the Parquet
    url = f"{BASE_URL}/cases?filter=term:{term}&per_page=100&page=0"
    data = fetch_oyez(url)
    return data if isinstance(data, list) else []

def get_case_detail(href: str) -> dict | None:
    """Return full detail for a case by its Oyez href.

    Priority:
    1. Pre-built Parquet file (fast, no network, committed to repo)
    2. Local JSON file cache
    3. Live Oyez API
    """
    if _DETAIL_DF is not None and href in _DETAIL_IDX:
        row = _DETAIL_DF.iloc[_DETAIL_IDX[href]]
        record = row.to_dict()
        # Deserialise JSON string fields back to their original types
        for field in _JSON_FIELDS:
            val = record.get(field)
            if isinstance(val, str):
                record[field] = json.loads(val)
            elif pd.isna(val) if not isinstance(val, (list, dict)) else False:
                record[field] = None
        return record

    data = fetch_oyez(href)
    return data if isinstance(data, dict) else None

def search_cases(query: str) -> list:
    """Search cases by name across recent terms (local cache first)."""
    results = []
    query_lower = query.lower()
    for term in range(_current_year(), _current_year() - 27, -1):
        cases = get_cases_by_term(term)
        for c in cases:
            name = c.get("name", "")
            if query_lower in name.lower():
                results.append(c)
        if len(results) >= 20:
            break
    return results[:20]

def get_recent_terms(n: int = 10) -> list[int]:
    """Return the n most recent SCOTUS terms (terms are named by their October start year)."""
    cy = _current_year()
    return list(range(cy - 1, cy - 1 - n, -1))

def extract_court_journey(detail: dict) -> list[dict]:
    """
    Extract the journey of a case through the courts.
    Returns a list of steps from originating court to SCOTUS.
    """
    steps = []

    lower_court = detail.get("lower_court")
    if lower_court:
        court_name = lower_court.get("name", "Lower Court")
        # Infer the correct level from the court name
        name_lower = court_name.lower()
        if any(kw in name_lower for kw in ("court of appeals", "circuit", "appellate")):
            level = "Appellate Court"
        elif any(kw in name_lower for kw in ("supreme court of", "state supreme", "court of last resort")):
            level = "Appellate Court"  # state supreme courts are intermediate relative to SCOTUS
        else:
            level = "Lower Court"
        steps.append({
            "court": court_name,
            "level": level,
            "decision": lower_court.get("decision", ""),
        })

    decided_by = detail.get("decided_by")
    if decided_by:
        steps.append({
            "court": "U.S. Supreme Court",
            "level": "Supreme Court",
            "decision": _summarize_decision(detail),
            "justices": _extract_justices(detail),
        })

    return steps

def _summarize_decision(detail: dict) -> str:
    disposition = detail.get("disposition", {})
    if isinstance(disposition, dict):
        return disposition.get("label", "")
    return str(disposition) if disposition else ""

def _pick_primary_decision(decisions: list) -> dict | None:
    """Return the most meaningful decision from a case's decision list.

    Preference order:
    1. Most dissent/minority votes  (the contested merits decision).
    2. Tie-break: most total votes.
    3. Final tie-break: last in list (Oyez stores decisions chronologically;
       for re-argued cases the final ruling comes last).
    """
    if not decisions:
        return None

    def _dissent_count(d: dict) -> int:
        return sum(
            1 for v in (d.get("votes") or [])
            if (v.get("vote") or "").lower() in ("dissent", "minority")
        )

    _, decision = max(
        enumerate(decisions),
        key=lambda x: (_dissent_count(x[1]), len(x[1].get("votes") or []), x[0]),
    )
    return decision


def _extract_justices(detail: dict) -> list[dict]:
    """Extract justice votes from the primary merits decision."""
    decisions = detail.get("decisions") or []
    primary = _pick_primary_decision(decisions)
    if not primary:
        return []
    winning_party = primary.get("winning_party", "")
    return [
        {
            "name": (vote.get("member", {}) or {}).get("name", "Unknown"),
            "vote": vote.get("vote", ""),
            "winning_party": winning_party,
        }
        for vote in (primary.get("votes") or [])
    ]
