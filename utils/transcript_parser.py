"""
Oral argument transcript parser.

Extracts speaker-attributed turns from Oyez oral argument transcript data
(the `oral_argument_audio[].transcript.sections[].turns` structure).

Usage (offline — operates on already-downloaded case_detail.parquet):

    from utils.transcript_parser import parse_case_transcript, compute_question_counts

    detail = get_case_detail(href)
    turns  = parse_case_transcript(detail)
    counts = compute_question_counts(turns)
    # counts → {'petitioner': 12, 'respondent': 8, 'q_ratio': 1.5, 'by_justice': {...}}

Usage (live — downloads a single argument from Oyez API):

    from utils.transcript_parser import fetch_and_parse_argument
    turns = fetch_and_parse_argument("https://api.oyez.org/case_media/oral_argument_audio/20890")
"""
import re
import os
import json
import requests
from typing import NamedTuple

_REPO      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_DIR = os.path.join(_REPO, "data_files", "oyez_data", "oral_arguments")
_DATA_DIR  = os.path.join(_REPO, "data")
_HEADERS   = {"Accept": "application/json", "User-Agent": "SCOTUS-TranscriptParser/1.0"}

os.makedirs(_CACHE_DIR, exist_ok=True)

# Decade boundaries — must match scripts/build_transcripts_parquet.py
_PARQUET_DECADES = [
    (1955, 1964),
    (1965, 1974),
    (1975, 1984),
    (1985, 1994),
    (1995, 2004),
    (2005, 2014),
    (2015, 2025),
]


class Turn(NamedTuple):
    speaker: str          # full name as it appears in the transcript
    role: str             # 'justice', 'advocate', or 'unknown'
    side: str             # 'petitioner', 'respondent', or 'unknown'
    text: str             # concatenated text blocks
    question_count: int   # sentences ending in '?'


_JUSTICE_KEYWORDS = {
    "roberts", "thomas", "alito", "sotomayor", "kagan",
    "gorsuch", "kavanaugh", "barrett", "jackson",
    "ginsburg", "breyer", "kennedy", "o'connor", "scalia",
    "rehnquist", "stevens", "souter", "white", "powell",
}


def _count_questions(text: str) -> int:
    return len(re.findall(r"\?", text))


def _side_from_section_title(section_title: str) -> str:
    """Derive the arguing side from a transcript section title."""
    low = (section_title or "").lower()
    if "petitioner" in low or "appellant" in low:
        return "petitioner"
    if "respondent" in low or "appellee" in low:
        return "respondent"
    return "unknown"


def _classify_role(speaker_name: str) -> str:
    low = speaker_name.lower()
    if any(j in low for j in _JUSTICE_KEYWORDS):
        return "justice"
    if any(t in low for t in ("counsel", "general", "solicitor", "attorney")):
        return "advocate"
    return "unknown"


def _load_parquet_turns(
    argument_ids: list[int],
    term: int,
    advocate_sides: dict[str, str],
) -> list[Turn] | None:
    """
    Load transcript turns from the decade Parquet file for *term*.

    Returns a list of Turn objects, or None if the Parquet is unavailable or
    contains no matching rows (so callers can fall back to JSON).
    """
    try:
        import pandas as pd
    except ImportError:
        return None

    parquet_path: str | None = None
    for start, end in _PARQUET_DECADES:
        if start <= term <= end:
            candidate = os.path.join(_DATA_DIR, f"transcripts_{start}_{end}.parquet")
            if os.path.exists(candidate):
                parquet_path = candidate
            break

    if parquet_path is None:
        return None

    try:
        df = pd.read_parquet(
            parquet_path,
            filters=[("argument_id", "in", argument_ids)],
        )
    except Exception:
        # Fallback: some pyarrow/pandas versions have issues with predicate pushdown;
        # read the full file and filter in Python instead.
        try:
            df = pd.read_parquet(parquet_path)
            df = df[df["argument_id"].isin(argument_ids)]
        except Exception:
            return None

    if df.empty:
        return None

    turns: list[Turn] = []
    for _, row in df.sort_values(["argument_id", "section_idx", "turn_idx"]).iterrows():
        speaker_name = row["speaker_name"] or "Unknown"
        role         = _classify_role(speaker_name)
        section_side = _side_from_section_title(str(row.get("section_title") or ""))

        if role == "justice":
            side = section_side
        else:
            side = "unknown"
            for known_adv, known_side in advocate_sides.items():
                if known_adv.lower() in speaker_name.lower():
                    side = known_side
                    break
            if side == "unknown":
                side = section_side

        text = row["text"] or ""
        turns.append(Turn(
            speaker=speaker_name,
            role=role,
            side=side,
            text=text,
            question_count=_count_questions(text),
        ))

    return turns if turns else None


def _parse_sections(sections: list, advocate_sides: dict[str, str] | None = None) -> list[Turn]:
    """
    Convert raw Oyez transcript sections into a flat list of Turns.

    advocate_sides: optional map from advocate name to 'petitioner'|'respondent'
    """
    advocate_sides = advocate_sides or {}
    turns: list[Turn] = []

    for section in sections:
        # Determine which side is arguing in this section from the title
        section_side = _side_from_section_title(section.get("section_title") or "")

        for turn_raw in (section.get("turns") or []):
            speaker_info = turn_raw.get("speaker") or {}
            speaker_name = speaker_info.get("name") or turn_raw.get("speaker_name") or "Unknown"
            role = _classify_role(speaker_name)

            # Justices: side = the section's side (who they are questioning)
            # Advocates: side from advocate_sides map, or section_side
            if role == "justice":
                side = section_side
            else:
                side = "unknown"
                for known_adv, known_side in advocate_sides.items():
                    if known_adv.lower() in speaker_name.lower():
                        side = known_side
                        break
                if side == "unknown":
                    side = section_side


            blocks = turn_raw.get("text_blocks") or []
            text = " ".join(b.get("text", "") for b in blocks if b.get("text"))
            turns.append(Turn(
                speaker=speaker_name,
                role=role,
                side=side,
                text=text,
                question_count=_count_questions(text),
            ))

    return turns


def parse_case_transcript(detail: dict) -> list[Turn]:
    """
    Parse all oral argument transcripts for a case.

    Resolution order:
      1. Transcript Parquet files (fast, repo-committed, preferred)
      2. Embedded transcript data in *detail* (live API response)
      3. Individual JSON files in data_files/oyez_data/oral_arguments/

    The detail dict is the result of get_case_detail(href) from utils/oyez_api.
    Returns a flat list of Turn objects across all argument sessions.
    """
    oa_list = detail.get("oral_argument_audio") or []
    if isinstance(oa_list, str):
        try:
            oa_list = json.loads(oa_list)
        except Exception:
            return []

    # Build advocate → side map from 'advocates' field
    advocates_raw = detail.get("advocates") or []
    if isinstance(advocates_raw, str):
        try:
            advocates_raw = json.loads(advocates_raw)
        except Exception:
            advocates_raw = []
    advocate_sides: dict[str, str] = {}
    for adv_entry in (advocates_raw if isinstance(advocates_raw, list) else []):
        adv  = adv_entry.get("advocate") or {}
        name = adv.get("name") or adv_entry.get("advocate_description") or ""
        desc = (adv_entry.get("advocate_description") or "").lower()
        side = "petitioner" if "petition" in desc or "appellant" in desc else (
               "respondent" if "respond" in desc or "appellee" in desc else "unknown")
        if name:
            advocate_sides[name] = side

    # Collect argument IDs for Parquet lookup
    argument_ids: list[int] = [
        int(oa["id"]) for oa in oa_list
        if isinstance(oa, dict) and "id" in oa
    ]

    term = detail.get("term")
    if isinstance(term, str):
        try:
            term = int(term)
        except Exception:
            term = None

    # 1. Try Parquet
    if argument_ids and isinstance(term, int):
        parquet_turns = _load_parquet_turns(argument_ids, term, advocate_sides)
        if parquet_turns is not None:
            return parquet_turns

    # 2. Embedded transcript (live API response)
    all_turns: list[Turn] = []
    for oa in oa_list:
        if not isinstance(oa, dict):
            continue
        transcript = oa.get("transcript") or {}
        sections   = transcript.get("sections") or []
        if sections:
            all_turns.extend(_parse_sections(sections, advocate_sides))
            continue

        # 3. Individual JSON cache file
        if "id" in oa:
            cache_file = os.path.join(
                _CACHE_DIR,
                f"case_media_oral_argument_audio_{oa['id']}.json",
            )
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, encoding="utf-8") as fh:
                        oa_data = json.load(fh)
                    cached_sections = (oa_data.get("transcript") or {}).get("sections") or []
                    all_turns.extend(_parse_sections(cached_sections, advocate_sides))
                except Exception:
                    pass

    # 4. Live Oyez API fallback — used when the Parquet file is absent (e.g. first
    #    deploy before parquet is committed) or the JSON cache doesn't exist on the
    #    cloud.  fetch_and_parse_argument makes a direct requests.get call.
    if not all_turns:
        for oa in oa_list:
            if isinstance(oa, dict) and "href" in oa:
                fetched = fetch_and_parse_argument(oa["href"])
                all_turns.extend(fetched)

    return all_turns


def compute_question_counts(turns: list[Turn]) -> dict:
    """
    Aggregate question counts from a list of turns.

    Returns:
        {
          'petitioner': int,   # questions asked by justices while petitioner argued
          'respondent': int,
          'q_ratio': float,    # petitioner / respondent (>1 → more questions to petitioner)
          'by_justice': {name: {'total_questions': int, 'to_petitioner': int, 'to_respondent': int}}
        }
    """
    pet_q = 0
    res_q = 0
    by_justice: dict[str, dict] = {}

    for turn in turns:
        if turn.role != "justice":
            continue
        j = turn.speaker
        if j not in by_justice:
            by_justice[j] = {"total_questions": 0, "to_petitioner": 0, "to_respondent": 0}
        by_justice[j]["total_questions"] += turn.question_count
        if turn.side == "petitioner":
            pet_q += turn.question_count
            by_justice[j]["to_petitioner"] += turn.question_count
        elif turn.side == "respondent":
            res_q += turn.question_count
            by_justice[j]["to_respondent"] += turn.question_count

    q_ratio = round(pet_q / res_q, 3) if res_q else None
    return {
        "petitioner": pet_q,
        "respondent": res_q,
        "q_ratio": q_ratio,
        "by_justice": by_justice,
    }


def fetch_and_parse_argument(oa_href: str) -> list[Turn]:
    """
    Return parsed turns for a single oral argument.

    Resolution order:
      1. Transcript Parquet files (scans all decade files by argument_id)
      2. Local JSON cache (data_files/oyez_data/oral_arguments/)
      3. Live Oyez API (requires network; caches result locally)
    """
    # Extract the numeric argument ID from the href
    oa_id: int | None = None
    try:
        oa_id = int(oa_href.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        pass

    # 1. Try Parquet (scan all decade files — O(7) stat calls)
    if oa_id is not None:
        try:
            import pandas as pd
            for start, end in _PARQUET_DECADES:
                path = os.path.join(_DATA_DIR, f"transcripts_{start}_{end}.parquet")
                if not os.path.exists(path):
                    continue
                df = pd.read_parquet(path, filters=[("argument_id", "==", oa_id)])
                if df.empty:
                    continue
                turns: list[Turn] = []
                for _, row in df.sort_values(["section_idx", "turn_idx"]).iterrows():
                    speaker_name = row["speaker_name"] or "Unknown"
                    role         = _classify_role(speaker_name)
                    side         = _side_from_section_title(str(row.get("section_title") or ""))
                    if role != "justice" and side == "unknown":
                        side = _side_from_section_title(str(row.get("section_title") or ""))
                    text = row["text"] or ""
                    turns.append(Turn(
                        speaker=speaker_name,
                        role=role,
                        side=side,
                        text=text,
                        question_count=_count_questions(text),
                    ))
                if turns:
                    return turns
        except Exception:
            pass

    # 2. Local JSON cache (correct filename convention used by download_oyez_data.py)
    if oa_id is not None:
        cache_file = os.path.join(_CACHE_DIR, f"case_media_oral_argument_audio_{oa_id}.json")
    else:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", oa_href.strip("/").replace("/", "_"))
        cache_file = os.path.join(_CACHE_DIR, f"{safe}.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, encoding="utf-8") as fh:
                oa_detail = json.load(fh)
            transcript = oa_detail.get("transcript") or {}
            sections   = transcript.get("sections") or []
            return _parse_sections(sections)
        except Exception:
            pass

    # 3. Live Oyez API
    try:
        r = requests.get(oa_href, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        oa_detail = r.json()
        # Cache the response for future runs
        try:
            with open(cache_file, "w", encoding="utf-8") as fh:
                json.dump(oa_detail, fh)
        except OSError:
            pass
    except Exception:
        return []

    transcript = oa_detail.get("transcript") or {}
    sections   = transcript.get("sections") or []
    return _parse_sections(sections)
