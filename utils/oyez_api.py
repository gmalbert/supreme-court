import time
import datetime
from utils.local_data import fetch_oyez

BASE_URL = "https://api.oyez.org"

def _current_year() -> int:
    return datetime.date.today().year

def get_cases_by_term(term: int) -> list:
    """Fetch all cases for a given Supreme Court term (local cache first)."""
    url = f"{BASE_URL}/cases?filter=term:{term}&per_page=100&page=0"
    data = fetch_oyez(url)
    return data if isinstance(data, list) else []

def get_case_detail(href: str) -> dict | None:
    """Fetch full detail for a case by its href (local cache first)."""
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

def _extract_justices(detail: dict) -> list[dict]:
    """Extract justice votes from case detail."""
    votes = []
    decisions = detail.get("decisions", [])
    if not decisions:
        return votes
    for decision in decisions:
        winning_party = decision.get("winning_party", "")
        for vote in decision.get("votes", []):
            member = vote.get("member", {}) or {}
            votes.append({
                "name": member.get("name", "Unknown"),
                "vote": vote.get("vote", ""),
                "winning_party": winning_party,
            })
    return votes
