"""
Build data/case_detail.parquet from the local Oyez JSON cache.

Reads every data_files/oyez_data/case_detail/<term>/<case>.json and
combines them into a single Parquet file keyed by href.

Scalar fields become proper Parquet columns.
Nested fields (lists / dicts) are stored as JSON strings so the
existing get_case_detail() callers receive the exact same structure.

Run from the repo root:
    python scripts/build_case_detail_parquet.py
"""

import json
import os
import sys

import pandas as pd

REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DETAIL_DIR  = os.path.join(REPO_ROOT, "data_files", "oyez_data", "case_detail")
OUT_DIR     = os.path.join(REPO_ROOT, "data")
OUT_FILE    = os.path.join(OUT_DIR, "case_detail.parquet")

# Fields stored as plain columns (scalar values only)
SCALAR_FIELDS = [
    "ID", "name", "href", "docket_number", "term",
    "first_party", "second_party", "first_party_label", "second_party_label",
    "manner_of_jurisdiction", "facts_of_the_case", "question", "conclusion",
    "description", "justia_url", "argument2_url", "view_count",
]

# Fields that can be dicts or lists — stored as JSON strings
JSON_FIELDS = [
    "timeline", "lower_court", "citation", "decided_by", "heard_by",
    "decisions", "advocates", "oral_argument_audio", "opinion_announcement",
    "written_opinion", "related_cases", "additional_docket_numbers", "location",
]


def _j(value) -> str | None:
    """Serialize a value to a JSON string, or None if the value is None."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def load_all_details() -> pd.DataFrame:
    rows = []
    terms = sorted(
        d for d in os.listdir(DETAIL_DIR)
        if os.path.isdir(os.path.join(DETAIL_DIR, d))
    )
    total_files = 0
    for term in terms:
        term_dir = os.path.join(DETAIL_DIR, term)
        for fname in os.listdir(term_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(term_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    d = json.load(fh)
            except Exception:
                continue

            row = {f: d.get(f) for f in SCALAR_FIELDS}
            for f in JSON_FIELDS:
                row[f] = _j(d.get(f))
            rows.append(row)
            total_files += 1

        if total_files % 1000 == 0 and total_files > 0:
            print(f"  ... {total_files:,} files loaded", end="\r")

    print(f"  ... {total_files:,} files loaded")
    return pd.DataFrame(rows)


def main():
    print(f"Reading case details from {DETAIL_DIR} ...")
    df = load_all_details()
    print(f"  Loaded {len(df):,} cases across {df['term'].nunique()} terms")

    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_parquet(OUT_FILE, index=False, compression="zstd")

    size_mb = os.path.getsize(OUT_FILE) / 1_048_576
    print(f"  Written to {OUT_FILE}")
    print(f"  Parquet size: {size_mb:.1f} MB")

    # Compare against raw JSON total
    json_bytes = sum(
        os.path.getsize(os.path.join(DETAIL_DIR, t, f))
        for t in os.listdir(DETAIL_DIR)
        for f in os.listdir(os.path.join(DETAIL_DIR, t))
        if f.endswith(".json")
    )
    print(f"  Raw JSON size: {json_bytes / 1_048_576:.1f} MB")
    print(f"  Compression ratio: {json_bytes / os.path.getsize(OUT_FILE):.1f}x")

    # Sanity check: round-trip one record
    df2 = pd.read_parquet(OUT_FILE)
    row = df2[df2["href"].str.contains("cases/2024/", na=False)].iloc[0]
    print(f"\nSample record: {row['name']} ({row['term']})")
    decisions = json.loads(row["decisions"]) if row["decisions"] else None
    if decisions:
        print(f"  decisions[0] keys: {list(decisions[0].keys())}")


if __name__ == "__main__":
    main()
