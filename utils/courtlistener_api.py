"""
CourtListener API wrapper.

CourtListener (Free Law Project) provides:
  - /dockets/          → case metadata, amicus counts, cert petition data
  - /opinions/         → full opinion text (majority, concurrence, dissent)
  - /citations/        → inter-case citation graph
  - /opinion-clusters/ → opinion clusters keyed to docket

Authentication: API token required (free, register at https://www.courtlistener.com/register/)
Set environment variable COURTLISTENER_TOKEN=<your_token> before using.

All responses are cached locally to data_files/courtlistener/ as JSON files.
"""
import os
import json
import time
import hashlib
import requests

_REPO      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_DIR = os.path.join(_REPO, "data_files", "courtlistener")
_BASE_URL  = "https://www.courtlistener.com/api/rest/v4"
_TOKEN     = os.environ.get("COURTLISTENER_TOKEN", "")

os.makedirs(_CACHE_DIR, exist_ok=True)


def _cache_path(key: str) -> str:
    safe = hashlib.sha1(key.encode()).hexdigest()[:16]
    return os.path.join(_CACHE_DIR, f"{safe}.json")


def _from_cache(key: str) -> dict | list | None:
    path = _cache_path(key)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return None


def _to_cache(key: str, data: dict | list) -> None:
    try:
        with open(_cache_path(key), "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except Exception:
        pass


def _get(endpoint: str, params: dict | None = None, *, force_refresh: bool = False) -> dict | list | None:
    """
    Make a GET request to the CourtListener API, with local file cache.

    Returns parsed JSON or None on error / missing token.
    """
    if not _TOKEN:
        return None

    cache_key = endpoint + json.dumps(params or {}, sort_keys=True)
    if not force_refresh:
        cached = _from_cache(cache_key)
        if cached is not None:
            return cached

    headers = {
        "Authorization": f"Token {_TOKEN}",
        "Accept": "application/json",
    }
    url = f"{_BASE_URL}/{endpoint.lstrip('/')}"
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=15)
        r.raise_for_status()
        data = r.json()
        _to_cache(cache_key, data)
        time.sleep(0.1)  # gentle rate limiting
        return data
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Return True if a CourtListener API token is available."""
    return bool(_TOKEN)


def search_docket(docket_number: str, court: str = "scotus") -> list[dict]:
    """
    Search for a SCOTUS docket by docket number.

    Args:
        docket_number: e.g. "22-1064"
        court: Defaults to "scotus"

    Returns:
        List of matching docket dicts (usually 0-1 for exact docket numbers)
    """
    data = _get("/dockets/", params={"docket_number": docket_number, "court": court})
    if not isinstance(data, dict):
        return []
    return data.get("results", [])


def get_opinion_cluster(docket_id: int) -> dict | None:
    """
    Fetch the opinion cluster for a docket (majority + concurrences + dissents).

    Returns the first matching cluster dict or None.
    """
    data = _get("/opinion-clusters/", params={"docket": docket_id})
    if not isinstance(data, dict):
        return None
    results = data.get("results", [])
    return results[0] if results else None


def get_opinions(cluster_id: int) -> list[dict]:
    """
    Fetch all opinion texts for a given cluster (majority, concurrences, dissents).

    Each item has keys: 'type', 'plain_text', 'html', 'author_str', etc.
    """
    data = _get("/opinions/", params={"cluster": cluster_id})
    if not isinstance(data, dict):
        return []
    return data.get("results", [])


def get_amicus_count(docket_id: int) -> int:
    """
    Return the number of amicus curiae filings for a given docket.
    Counts entries/documents with 'amicus' in description.
    """
    data = _get("/docket-entries/", params={"docket": docket_id, "page_size": 100})
    if not isinstance(data, dict):
        return 0
    entries = data.get("results", [])
    return sum(
        1 for e in entries
        if "amicus" in (e.get("description") or "").lower()
    )


def get_citations_for_case(cluster_id: int) -> list[dict]:
    """
    Return a list of cases that cite the given cluster (incoming citations).

    Each result has: 'citing_cluster_id', 'cited_cluster_id', etc.
    """
    data = _get("/citations/", params={"cited_cluster": cluster_id})
    if not isinstance(data, dict):
        return []
    return data.get("results", [])


def fetch_case_data(docket_number: str) -> dict:
    """
    High-level helper: given a SCOTUS docket number, return a consolidated
    dict with docket metadata, amicus count, and opinion texts.

    Example:
        data = fetch_case_data("19-1392")   # Fulton v. Philadelphia
        data.keys() → ['docket', 'amicus_count', 'opinions']
    """
    if not is_configured():
        return {"error": "COURTLISTENER_TOKEN not set. See utils/courtlistener_api.py."}

    dockets = search_docket(docket_number)
    if not dockets:
        return {"error": f"No docket found for {docket_number}"}

    docket = dockets[0]
    docket_id = docket.get("id")
    amicus = get_amicus_count(docket_id) if docket_id else 0

    cluster = get_opinion_cluster(docket_id) if docket_id else None
    opinions = []
    if cluster:
        opinions = get_opinions(cluster["id"])

    return {
        "docket": docket,
        "amicus_count": amicus,
        "opinions": opinions,
        "cluster": cluster,
    }
