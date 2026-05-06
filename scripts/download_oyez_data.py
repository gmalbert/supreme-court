"""
Download all Oyez data (excluding audio binaries) to oyez_data/.

Layout:
  oyez_data/
    justices/           — one JSON per justice (full detail)
    courts/             — one JSON per court (full detail)
    cases/<term>/       — case list summary JSONs
    case_detail/<term>/ — full case detail JSONs
    decisions/          — decision detail JSONs (votes, disposition, etc.)
    written_opinions/   — written opinion detail JSONs
    oral_arguments/     — oral argument detail JSONs (with transcript JSON)
    opinion_announcements/ — announcement detail JSONs (with transcript JSON)
    advocate_detail/    — individual advocate/justice profile JSONs
"""

import os
import sys
import time
import json
import requests
from urllib.parse import urlparse

BASE       = "https://api.oyez.org"
DATA_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_files", "oyez_data")
RATE_LIMIT = 0.15   # seconds between uncached requests
HEADERS    = {"Accept": "application/json", "User-Agent": "SCOTUS-Downloader/1.0"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cache_path(subdir: str, key: str) -> str:
    d = os.path.join(DATA_DIR, subdir)
    os.makedirs(d, exist_ok=True)
    safe = key.strip("/").replace("/", "_") + ".json"
    return os.path.join(d, safe)


def fetch_json(url: str, subdir: str = "raw") -> dict | list | None:
    """GET url, cache result under DATA_DIR/<subdir>/, return parsed JSON."""
    key = urlparse(url).path
    path = _cache_path(subdir, key)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"  GET {url}", flush=True)
    time.sleep(RATE_LIMIT)
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        print(f"    WARN: {exc}", flush=True)
        return None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def fetch_href(obj: dict | None, subdir: str) -> dict | None:
    """Fetch obj['href'] if present, caching to subdir."""
    if not isinstance(obj, dict):
        return None
    href = obj.get("href")
    if not href:
        return None
    return fetch_json(href, subdir)


# ── Justices & Courts ─────────────────────────────────────────────────────────

def download_justices():
    print("\n=== Justices ===")
    listing = fetch_json(f"{BASE}/justices", "justices")
    if not listing:
        return
    for j in listing:
        fetch_href(j, "justices")


def download_courts():
    print("\n=== Courts ===")
    listing = fetch_json(f"{BASE}/courts", "courts")
    if not listing:
        return
    for c in listing:
        fetch_href(c, "courts")


# ── Cases ─────────────────────────────────────────────────────────────────────

def fetch_terms() -> list[str]:
    """Return sorted list of all SCOTUS terms Oyez covers (1955 - current)."""
    import datetime
    current = datetime.date.today().year - 1   # most recent completed term
    return [str(t) for t in range(1955, current + 1)]


def fetch_cases_for_term(term: str) -> list[dict]:
    data = fetch_json(f"{BASE}/cases?filter=term:{term}&per_page=300",
                      f"cases/{term}")
    return data if isinstance(data, list) else []


def download_case(summary: dict, term: str):
    """Fetch full case detail and all linked sub-resources."""
    href = summary.get("href")
    if not href:
        return
    case = fetch_json(href, f"case_detail/{term}")
    if not case:
        return

    # ── Decisions ────────────────────────────────────────────────────────────
    for dec in (case.get("decisions") or []):
        detail = fetch_href(dec, "decisions")
        if detail:
            # decision votes may have advocate hrefs
            for vote in (detail.get("votes") or []):
                if isinstance(vote, dict) and vote.get("href"):
                    fetch_json(vote["href"], "decisions")

    # ── Written opinions ─────────────────────────────────────────────────────
    for op in (case.get("written_opinion") or []):
        fetch_href(op, "written_opinions")

    # ── Oral argument detail + transcript JSON (no audio binary) ─────────────
    for oral in (case.get("oral_argument_audio") or []):
        oral_detail = fetch_href(oral, "oral_arguments")
        if oral_detail:
            # transcript is a nested object with its own href
            transcript = oral_detail.get("transcript")
            if isinstance(transcript, dict) and transcript.get("href"):
                fetch_json(transcript["href"], "oral_arguments")

    # ── Opinion announcements + transcript JSON ───────────────────────────────
    for ann in (case.get("opinion_announcement") or []):
        ann_detail = fetch_href(ann, "opinion_announcements")
        if ann_detail:
            transcript = ann_detail.get("transcript")
            if isinstance(transcript, dict) and transcript.get("href"):
                fetch_json(transcript["href"], "opinion_announcements")

    # ── Advocate profiles ─────────────────────────────────────────────────────
    for adv_entry in (case.get("advocates") or []):
        if isinstance(adv_entry, dict):
            adv = adv_entry.get("advocate") or {}
            if isinstance(adv, dict) and adv.get("href"):
                fetch_json(adv["href"], "advocate_detail")

    # ── Justice profiles referenced in heard_by / decided_by ─────────────────
    for court_ref in list(case.get("heard_by") or []) + list(case.get("decided_by") or []):
        if isinstance(court_ref, dict):
            court_detail = fetch_href(court_ref, "courts")
            if court_detail:
                for member in (court_detail.get("members") or []):
                    if isinstance(member, dict) and member.get("href"):
                        fetch_json(member["href"], "justices")

    # ── Related cases (summary only — avoids infinite recursion) ─────────────
    for rel in (case.get("related_cases") or []):
        if isinstance(rel, dict) and rel.get("href"):
            fetch_json(rel["href"], "raw")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    download_justices()
    download_courts()

    print("\n=== Discovering terms ===")
    terms = fetch_terms()
    if not terms:
        print("ERROR: could not retrieve term list.", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(terms)} terms: {terms[0]} – {terms[-1]}")

    for term in terms:
        print(f"\n=== Term {term} ===", flush=True)
        summaries = fetch_cases_for_term(term)
        print(f"  {len(summaries)} cases", flush=True)
        for summary in summaries:
            download_case(summary, term)

    print("\nDownload complete.")


if __name__ == "__main__":
    main()
