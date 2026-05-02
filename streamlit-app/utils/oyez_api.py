import requests
import time

BASE_URL = "https://api.oyez.org"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "SCOTUS-Visualizer/1.0"
}

def get_cases_by_term(term: int) -> list:
    """Fetch all cases for a given Supreme Court term."""
    url = f"{BASE_URL}/cases?filter=term:{term}&per_page=100&page=0"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

def get_case_detail(href: str) -> dict | None:
    """Fetch full detail for a case by its href."""
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def search_cases(query: str) -> list:
    """Search cases by name across recent terms."""
    results = []
    query_lower = query.lower()
    for term in range(2023, 1999, -1):
        cases = get_cases_by_term(term)
        for c in cases:
            name = c.get("name", "")
            if query_lower in name.lower():
                results.append(c)
        if len(results) >= 20:
            break
        time.sleep(0.05)
    return results[:20]

def get_recent_terms(n: int = 10) -> list[int]:
    """Return the n most recent SCOTUS terms."""
    return list(range(2023, 2023 - n, -1))

def extract_court_journey(detail: dict) -> list[dict]:
    """
    Extract the journey of a case through the courts.
    Returns a list of steps from originating court to SCOTUS.
    """
    steps = []

    lower_court = detail.get("lower_court")
    if lower_court:
        court_name = lower_court.get("name", "Lower Court")
        steps.append({
            "court": court_name,
            "level": "Lower Court",
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
