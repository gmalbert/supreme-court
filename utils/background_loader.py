"""
Background parallel data loader.

Uses concurrent.futures.ThreadPoolExecutor to fetch multiple Oyez case detail
records in parallel, with a configurable concurrency cap and polite inter-batch
delay to avoid hammering the API or filesystem.

Usage:
    from utils.background_loader import parallel_fetch_details

    details = parallel_fetch_details(hrefs, max_workers=5)
    # Returns {href: detail_dict_or_None, ...}
"""

from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from utils.local_data import fetch_oyez


def parallel_fetch_details(
    hrefs: list[str],
    max_workers: int = 5,
    batch_delay: float = 0.05,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[str, dict | None]:
    """Fetch case detail dicts for a list of Oyez hrefs in parallel.

    Parameters
    ----------
    hrefs : list[str]
        Oyez API hrefs to fetch (e.g. ``https://api.oyez.org/cases/2020/19-783``).
    max_workers : int
        Maximum concurrent threads.  Keep ≤ 5 to stay within Oyez's informal
        rate limits.  When LOCAL_ONLY=True (the default) this is just filesystem
        reads and can safely be higher.
    batch_delay : float
        Seconds to sleep between launching each worker.  Ignored when the local
        cache always hits.
    progress_cb : callable(done, total) | None
        Optional callback invoked after each completed fetch so callers can
        update a progress bar.

    Returns
    -------
    dict[str, dict | None]
        Map of href → parsed detail dict (or None on failure).
    """
    results: dict[str, dict | None] = {}
    total = len(hrefs)

    if total == 0:
        return results

    def _fetch_one(href: str) -> tuple[str, dict | None]:
        data = fetch_oyez(href)
        return href, (data if isinstance(data, dict) else None)

    done_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, href in enumerate(hrefs):
            if i > 0:
                time.sleep(batch_delay)
            futures[executor.submit(_fetch_one, href)] = href

        for future in as_completed(futures):
            try:
                href, detail = future.result()
            except Exception:
                href = futures[future]
                detail = None
            results[href] = detail
            done_count += 1
            if progress_cb:
                progress_cb(done_count, total)

    return results


def parallel_fetch_terms(
    terms: list[int],
    max_workers: int = 4,
    batch_delay: float = 0.05,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[int, list]:
    """Fetch case lists for multiple terms in parallel.

    Returns dict of term → list of case dicts.
    """
    results: dict[int, list] = {}
    total = len(terms)

    if total == 0:
        return results

    def _fetch_term(term: int) -> tuple[int, list]:
        data = fetch_oyez(f"https://api.oyez.org/cases?filter=term:{term}&per_page=300&page=0")
        return term, (data if isinstance(data, list) else [])

    done_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, term in enumerate(terms):
            if i > 0:
                time.sleep(batch_delay)
            futures[executor.submit(_fetch_term, term)] = term

        for future in as_completed(futures):
            try:
                term, cases = future.result()
            except Exception:
                term = futures[future]
                cases = []
            results[term] = cases
            done_count += 1
            if progress_cb:
                progress_cb(done_count, total)

    return results
