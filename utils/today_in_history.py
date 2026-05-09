"""Utility for the Today-in-SCOTUS-History widget.

Reads data_files/date_index.json (built by scripts/build_date_index.py) and
returns a random case decided or argued on today's calendar date.
"""

from __future__ import annotations

import json
import os
import random
from datetime import date

_INDEX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data_files",
    "date_index.json",
)

_cached_index: dict | None = None


def _load_index() -> dict:
    global _cached_index
    if _cached_index is None:
        if os.path.exists(_INDEX_PATH):
            with open(_INDEX_PATH, encoding="utf-8") as f:
                _cached_index = json.load(f)
        else:
            _cached_index = {}
    return _cached_index


def get_today_in_history(seed: int | None = None) -> dict | None:
    """Return a random case decided or argued on today's month/day.

    Returns a dict with keys: name, term, href, date_field, date
    or None if no matching cases or the index hasn't been built yet.
    """
    index = _load_index()
    if not index:
        return None
    today_key = date.today().strftime("%m-%d")
    matches = index.get(today_key, [])
    if not matches:
        return None
    rng = random.Random(seed)
    return rng.choice(matches)


def index_exists() -> bool:
    """Return True if the date index file has been built."""
    return os.path.exists(_INDEX_PATH) and os.path.getsize(_INDEX_PATH) > 10
