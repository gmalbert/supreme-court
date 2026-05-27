"""
Build data/transcripts_YYYY_YYYY.parquet from the local Oyez oral argument JSON cache.

Creates one Parquet file per SCOTUS-term decade, each containing one row per
transcript turn.  The resulting files are ~15-30 MB each (Zstd-compressed) vs.
the ~2.96 GB of raw JSON, making them safe to commit to the repository.

Schema per row
--------------
  argument_id    int32    Oyez oral_argument_audio ID
  argument_title string   Title of the argument session
  term           int16    SCOTUS term (October start year)
  section_idx    int8     Section index within the argument (0-based)
  section_title  string   Section title — used by transcript_parser to infer side
  turn_idx       int16    Turn index within the section (0-based)
  speaker_name   string   Speaker full name
  speaker_id     int32    Oyez person ID (nullable)
  start          float32  Start time within the audio (seconds)
  stop           float32  Stop time within the audio (seconds)
  text           string   Concatenated text_blocks for the turn

Run from the repo root:
    python scripts/build_transcripts_parquet.py

Options:
    --terms YYYY [YYYY ...]   Only rebuild specific term years (useful for incremental updates)
    --out DIR                 Output directory (default: data/)
"""

import argparse
import json
import os
import sys

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORAL_DIR   = os.path.join(REPO_ROOT, "data_files", "oyez_data", "oral_arguments")
DETAIL_DIR = os.path.join(REPO_ROOT, "data_files", "oyez_data", "case_detail")
OUT_DIR    = os.path.join(REPO_ROOT, "data")

# Decade boundaries — one Parquet file per decade keeps each file under ~30 MB
DECADES = [
    (1955, 1964),
    (1965, 1974),
    (1975, 1984),
    (1985, 1994),
    (1995, 2004),
    (2005, 2014),
    (2015, 2025),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_id_to_term_map() -> dict[int, int]:
    """Walk case_detail JSON files and build {argument_id: term} mapping."""
    mapping: dict[int, int] = {}
    if not os.path.isdir(DETAIL_DIR):
        return mapping

    for rootdir, _dirs, files in os.walk(DETAIL_DIR):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            path = os.path.join(rootdir, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    j = json.load(fh)
            except Exception:
                continue

            oa_list = j.get("oral_argument_audio") or []
            if not oa_list:
                continue

            term = j.get("term")
            if isinstance(term, str):
                try:
                    term = int(term)
                except Exception:
                    term = None
            if not isinstance(term, int):
                # Fall back: try to parse term from the filename (cases_YYYY_N.json)
                try:
                    term = int(fn.split("_")[1])
                except Exception:
                    continue

            for entry in oa_list:
                if isinstance(entry, dict) and "id" in entry:
                    mapping[int(entry["id"])] = term

    return mapping


def _extract_rows(oral_id: int, title: str, term: int, j: dict) -> list[dict]:
    """Flatten one oral argument JSON into a list of turn dicts."""
    transcript = j.get("transcript") or {}
    sections   = transcript.get("sections") or []
    rows: list[dict] = []

    for sec_idx, section in enumerate(sections):
        sec_title = section.get("section_title") or ""
        for turn_idx, turn in enumerate(section.get("turns") or []):
            speaker_info = turn.get("speaker") or {}
            if isinstance(speaker_info, dict):
                speaker_name = speaker_info.get("name") or "Unknown"
                speaker_id   = speaker_info.get("ID") or speaker_info.get("id")
            else:
                speaker_name = str(speaker_info) if speaker_info else "Unknown"
                speaker_id   = None

            blocks = turn.get("text_blocks") or []
            text   = " ".join(
                b.get("text", "") for b in blocks
                if isinstance(b, dict) and b.get("text")
            )

            rows.append({
                "argument_id":    oral_id,
                "argument_title": title or "",
                "term":           term,
                "section_idx":    sec_idx,
                "section_title":  sec_title,
                "turn_idx":       turn_idx,
                "speaker_name":   speaker_name,
                "speaker_id":     speaker_id,
                "start":          float(turn.get("start") or 0.0),
                "stop":           float(turn.get("stop")  or 0.0),
                "text":           text,
            })

    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main(out_dir: str = OUT_DIR, only_terms: list[int] | None = None) -> None:
    print(f"Building argument_id -> term map from {DETAIL_DIR} ...")
    id_to_term = _build_id_to_term_map()
    print(f"  Mapped {len(id_to_term):,} argument IDs to SCOTUS terms")

    if not os.path.isdir(ORAL_DIR):
        print(
            f"\nERROR: oral_arguments directory not found at {ORAL_DIR}\n"
            "Run scripts/download_oyez_data.py first to populate the local cache.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Decide which decades to (re)build
    if only_terms:
        rebuild_decades = []
        for term in only_terms:
            for d in DECADES:
                if d[0] <= term <= d[1] and d not in rebuild_decades:
                    rebuild_decades.append(d)
    else:
        rebuild_decades = list(DECADES)

    print(f"\nReading oral argument JSON from {ORAL_DIR} ...")

    # Group turns by decade
    by_decade: dict[tuple[int, int], list[dict]] = {d: [] for d in DECADES}
    unmapped  = 0
    no_turns  = 0
    processed = 0

    oral_files = sorted(fn for fn in os.listdir(ORAL_DIR) if fn.endswith(".json"))
    for fn in oral_files:
        try:
            oral_id = int(fn.split("_")[-1].split(".")[0])
        except Exception:
            continue

        term = id_to_term.get(oral_id)
        if term is None:
            unmapped += 1
            continue

        # If only rebuilding specific decades, skip files outside them
        target_decade = next(
            (d for d in rebuild_decades if d[0] <= term <= d[1]), None
        )
        if target_decade is None:
            continue

        path = os.path.join(ORAL_DIR, fn)
        try:
            with open(path, encoding="utf-8") as fh:
                j = json.load(fh)
        except Exception:
            continue

        title = j.get("title") or j.get("display_title") or ""
        rows  = _extract_rows(oral_id, title, term, j)

        if rows:
            by_decade[target_decade].extend(rows)
        else:
            no_turns += 1

        processed += 1
        if processed % 500 == 0:
            total_rows = sum(len(v) for v in by_decade.values())
            print(f"  ... {processed:,} files processed ({total_rows:,} turns)", end="\r")

    total_rows = sum(len(v) for v in by_decade.values())
    print(
        f"  Processed {processed:,} files -> {total_rows:,} turns "
        f"({unmapped} unmapped, {no_turns} with no turn data)"
    )

    os.makedirs(out_dir, exist_ok=True)

    print("\nWriting Parquet files ...")
    total_parquet_bytes = 0

    for start, end in DECADES:
        rows = by_decade.get((start, end), [])
        if not rows:
            print(f"  {start}-{end}: no rows, skipping")
            continue

        df = pd.DataFrame(rows)

        # Enforce dtypes — use int64 for argument_id/term so Python `int` filter
        # values match without silent type-mismatch failures in pyarrow 14+.
        df["argument_id"]  = df["argument_id"].astype("int64")
        df["term"]         = df["term"].astype("int64")
        df["section_idx"]  = df["section_idx"].astype("int8")
        df["turn_idx"]     = df["turn_idx"].astype("int16")
        df["speaker_id"]   = pd.to_numeric(df["speaker_id"], errors="coerce").fillna(0).astype("int64")
        df["start"]        = df["start"].astype("float32")
        df["stop"]         = df["stop"].astype("float32")
        # Fill string nulls so pd.NA can't appear when reading with pandas 3.0+
        for _c in ["argument_title", "section_title", "speaker_name", "text"]:
            df[_c] = df[_c].fillna("").astype(str)

        # Write with explicit pyarrow schema: utf8 strings (not large_string) for
        # broadest compatibility across pyarrow versions.
        _schema = pa.schema([
            pa.field("argument_id",    pa.int64()),
            pa.field("argument_title", pa.utf8()),
            pa.field("term",           pa.int64()),
            pa.field("section_idx",    pa.int8()),
            pa.field("section_title",  pa.utf8()),
            pa.field("turn_idx",       pa.int16()),
            pa.field("speaker_name",   pa.utf8()),
            pa.field("speaker_id",     pa.int64()),
            pa.field("start",          pa.float32()),
            pa.field("stop",           pa.float32()),
            pa.field("text",           pa.utf8()),
        ])
        tbl = pa.Table.from_pandas(df[list(_schema.names)], schema=_schema, preserve_index=False)
        out_path = os.path.join(out_dir, f"transcripts_{start}_{end}.parquet")
        pq.write_table(tbl, out_path, compression="zstd")

        size_mb = os.path.getsize(out_path) / 1_048_576
        total_parquet_bytes += os.path.getsize(out_path)
        print(f"  {start}-{end}: {len(df):,} turns -> {out_path}  ({size_mb:.1f} MB)")

    json_bytes = sum(
        os.path.getsize(os.path.join(ORAL_DIR, fn))
        for fn in os.listdir(ORAL_DIR)
        if fn.endswith(".json")
    )
    print(
        f"\nRaw JSON size:    {json_bytes / 1_048_576:,.0f} MB\n"
        f"Parquet total:    {total_parquet_bytes / 1_048_576:,.1f} MB  "
        f"({100 * total_parquet_bytes / json_bytes:.1f}% of raw)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flatten Oyez oral argument JSON into decade-split Parquet files."
    )
    parser.add_argument(
        "--terms", nargs="+", type=int, metavar="YYYY",
        help="Only rebuild the decade(s) containing these term years",
    )
    parser.add_argument(
        "--out", default=OUT_DIR, metavar="DIR",
        help=f"Output directory (default: {OUT_DIR})",
    )
    args = parser.parse_args()
    main(out_dir=args.out, only_terms=args.terms)
