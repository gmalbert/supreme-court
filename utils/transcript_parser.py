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
_HEADERS   = {"Accept": "application/json", "User-Agent": "SCOTUS-TranscriptParser/1.0"}

os.makedirs(_CACHE_DIR, exist_ok=True)


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


def _classify_role(speaker_name: str) -> str:
    low = speaker_name.lower()
    if any(j in low for j in _JUSTICE_KEYWORDS):
        return "justice"
    if any(t in low for t in ("counsel", "general", "solicitor", "attorney")):
        return "advocate"
    return "unknown"


def _parse_sections(sections: list, advocate_sides: dict[str, str] | None = None) -> list[Turn]:
    """
    Convert raw Oyez transcript sections into a flat list of Turns.

    advocate_sides: optional map from advocate name to 'petitioner'|'respondent'
    """
    advocate_sides = advocate_sides or {}
    turns: list[Turn] = []

    for section in sections:
        # Determine which side is arguing in this section from the title
        sec_title = (section.get("section_title") or "").lower()
        if "petitioner" in sec_title or "appellant" in sec_title:
            section_side = "petitioner"
        elif "respondent" in sec_title or "appellee" in sec_title:
            section_side = "respondent"
        else:
            section_side = "unknown"

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
    Parse all oral argument transcripts embedded in a case detail dict.

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
        adv = adv_entry.get("advocate") or {}
        name = adv.get("name") or adv_entry.get("advocate_description") or ""
        desc = (adv_entry.get("advocate_description") or "").lower()
        side = "petitioner" if "petition" in desc or "appellant" in desc else (
               "respondent" if "respond" in desc or "appellee" in desc else "unknown")
        if name:
            advocate_sides[name] = side

    all_turns: list[Turn] = []
    for oa in oa_list:
        if not isinstance(oa, dict):
            continue
        transcript = oa.get("transcript") or {}
        sections = transcript.get("sections") or []
        all_turns.extend(_parse_sections(sections, advocate_sides))

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
    Download a single oral argument from the Oyez API and parse its transcript.
    Caches the raw JSON to data_files/oyez_data/oral_arguments/.

    This requires a live network connection on the first call.
    """
    # Check cache
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", oa_href.split("/")[-1])
    cache_file = os.path.join(_CACHE_DIR, f"{safe}.json")
    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as fh:
            oa_detail = json.load(fh)
    else:
        try:
            r = requests.get(oa_href, headers=_HEADERS, timeout=15)
            r.raise_for_status()
            oa_detail = r.json()
            with open(cache_file, "w", encoding="utf-8") as fh:
                json.dump(oa_detail, fh)
        except Exception:
            return []

    transcript = oa_detail.get("transcript") or {}
    sections   = transcript.get("sections") or []
    return _parse_sections(sections)
