"""Build data_files/date_index.json — a lookup of cases by calendar month-day.

Run once (or whenever new terms are cached) to power the Today-in-History widget:

    python scripts/build_date_index.py

Output: data_files/date_index.json
  {
    "MM-DD": [
      {"name": "...", "term": 2020, "href": "...", "date_field": "decided_on", "date": "YYYY-MM-DD"},
      ...
    ],
    ...
  }
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-DateIndex/1.0"}
OYEZ_BASE = "https://api.oyez.org"
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_files", "date_index.json")

TERMS = list(range(1990, datetime.today().year + 1))


def _fetch(url: str) -> list | dict | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  WARNING: {url} → {exc}", flush=True)
        return None


def _parse_date_str(raw) -> str | None:
    """Extract an ISO date string from various Oyez date formats."""
    if not raw:
        return None
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if not raw:
        return None
    if isinstance(raw, dict):
        raw = raw.get("date") or raw.get("value")
    if not raw:
        return None
    # Handle Unix epoch integers (Oyez's primary date format)
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            return None
    raw = str(raw)
    if raw.isdigit() and len(raw) >= 9:
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            return None
    try:
        return datetime.fromisoformat(raw[:10]).strftime("%Y-%m-%d")
    except ValueError:
        return None


# Maps Oyez timeline event labels to semantic categories
_DECIDED_EVENTS = {"decided", "affirmed", "reversed", "remanded", "per curiam"}
_ARGUED_EVENTS  = {"argued", "oral argument"}


def _extract_timeline_dates(case: dict) -> dict[str, str | None]:
    """Return {'decided': 'YYYY-MM-DD'|None, 'argued': 'YYYY-MM-DD'|None} from timeline."""
    decided_date = None
    argued_date = None
    for entry in case.get("timeline") or []:
        if not entry or not isinstance(entry, dict):
            continue
        event = (entry.get("event") or "").lower()
        dates = entry.get("dates") or []
        date_str = _parse_date_str(dates[0]) if dates else None
        if not date_str:
            continue
        if any(kw in event for kw in _DECIDED_EVENTS) and decided_date is None:
            decided_date = date_str
        elif any(kw in event for kw in _ARGUED_EVENTS) and argued_date is None:
            argued_date = date_str
    return {"decided": decided_date, "argued": argued_date}


def build_index() -> dict:
    index: dict[str, list] = {}
    total_cases = 0

    for term in TERMS:
        url = f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=300&page=0"
        print(f"Fetching term {term}...", end=" ", flush=True)
        cases = _fetch(url)
        if not isinstance(cases, list):
            print("no data")
            continue
        print(f"{len(cases)} cases")
        for case in cases:
            name = case.get("name", "Unknown")
            href = case.get("href", "")
            dates = _extract_timeline_dates(case)
            pairs = [
                ("decided_on", dates["decided"]),
                ("argued_on",  dates["argued"]),
            ]
            for date_field, date_str in pairs:
                if not date_str:
                    continue
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    key = dt.strftime("%m-%d")
                except ValueError:
                    continue
                index.setdefault(key, []).append({
                    "name": name,
                    "term": term,
                    "href": href,
                    "date_field": date_field,
                    "date": date_str,
                })
        total_cases += len(cases)
        time.sleep(0.05)  # be polite to the API

    # De-duplicate within each day (same case may appear for multiple date fields)
    for key in index:
        seen = set()
        deduped = []
        for entry in index[key]:
            uid = (entry["name"], entry["date_field"])
            if uid not in seen:
                seen.add(uid)
                deduped.append(entry)
        index[key] = deduped

    return index


if __name__ == "__main__":
    print(f"Building date index for {len(TERMS)} terms ({TERMS[0]}–{TERMS[-1]})...")
    index = build_index()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    total_entries = sum(len(v) for v in index.values())
    print(f"\nDone. {len(index)} date keys, {total_entries} total entries → {OUTPUT_PATH}")
