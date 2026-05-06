"""
Build data/cases_by_term.parquet from the local Oyez JSON cache.

Reads every data_files/oyez_data/cases/<term>/cases.json and combines
them into a single Parquet file, then prints a size comparison.

Run from the repo root:
    python scripts/build_cases_parquet.py
"""

import json
import os
import sys

import pandas as pd

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_DIR  = os.path.join(REPO_ROOT, "data_files", "oyez_data", "cases")
OUT_DIR    = os.path.join(REPO_ROOT, "data")
OUT_FILE   = os.path.join(OUT_DIR, "cases_by_term.parquet")


def load_all_terms() -> pd.DataFrame:
    rows = []
    terms = sorted(
        d for d in os.listdir(CASES_DIR)
        if os.path.isdir(os.path.join(CASES_DIR, d))
    )
    for term in terms:
        path = os.path.join(CASES_DIR, term, "cases.json")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            cases = json.load(fh)
        if not isinstance(cases, list):
            continue
        for c in cases:
            # Flatten timeline list → earliest/latest date strings
            timeline = c.get("timeline") or []
            dates = [t.get("dates", []) for t in timeline if isinstance(t, dict)]
            flat_dates = [d for sublist in dates for d in sublist]

            # Flatten citation dict
            citation = c.get("citation") or {}
            cite_vol  = citation.get("volume")  if isinstance(citation, dict) else None
            cite_page = citation.get("page")    if isinstance(citation, dict) else None
            cite_year = citation.get("year")    if isinstance(citation, dict) else None

            rows.append({
                "term":           c.get("term") or int(term),
                "ID":             c.get("ID"),
                "name":           c.get("name"),
                "href":           c.get("href"),
                "docket_number":  c.get("docket_number"),
                "question":       c.get("question"),
                "description":    c.get("description"),
                "justia_url":     c.get("justia_url"),
                "view_count":     c.get("view_count"),
                "cite_volume":    cite_vol,
                "cite_page":      cite_page,
                "cite_year":      cite_year,
            })

    return pd.DataFrame(rows)


def main():
    print(f"Reading cases from {CASES_DIR} ...")
    df = load_all_terms()
    print(f"  Loaded {len(df):,} cases across {df['term'].nunique()} terms")

    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_parquet(OUT_FILE, index=False, compression="zstd")

    size_mb = os.path.getsize(OUT_FILE) / 1_048_576
    print(f"  Written to {OUT_FILE}")
    print(f"  Parquet size: {size_mb:.2f} MB")

    # Compare against raw JSON total
    json_bytes = sum(
        os.path.getsize(os.path.join(CASES_DIR, t, "cases.json"))
        for t in os.listdir(CASES_DIR)
        if os.path.exists(os.path.join(CASES_DIR, t, "cases.json"))
    )
    print(f"  Raw JSON size: {json_bytes / 1_048_576:.2f} MB")
    print(f"  Compression ratio: {json_bytes / os.path.getsize(OUT_FILE):.1f}x")

    # Quick sanity check
    df2 = pd.read_parquet(OUT_FILE)
    sample = df2[df2["term"] == df2["term"].max()]
    print(f"\nSample — most recent term ({sample['term'].iloc[0]}): {len(sample)} cases")
    print(sample[["name", "docket_number"]].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
