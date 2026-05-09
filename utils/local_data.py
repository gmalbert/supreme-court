"""
Cache-first Oyez data access.

Checks data_files/oyez_data/ before hitting the live API.
Every cache miss is appended to data_files/oyez_data/api_fallback.log
so you can see exactly which URLs still need to be downloaded.
"""

import os
import json
import logging
import datetime
import re
import requests
from urllib.parse import urlparse, parse_qs


def strip_html(text) -> str:
    """Remove HTML tags and normalise whitespace from an Oyez text field."""
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def safe_md(text: str) -> str:
    """Strip HTML then escape characters that Streamlit's markdown renderer
    would misinterpret (e.g. $ as LaTeX delimiters)."""
    t = strip_html(text)
    if not t:
        return t
    return t.replace("$", r"\$")


# ── Issue area inference ──────────────────────────────────────────────────────
# Oyez does not expose issue_area in its API; derive from question/description.

_ISSUE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Criminal Procedure",  ["criminal", "defendant", "conviction", "sentence", "arrest", "search", "seizure",
                              "fourth amendment", "fifth amendment", "sixth amendment", "eighth amendment",
                              "habeas", "miranda", "double jeopardy", "plea", "guilty", "felony", "prison",
                              "jury", "trial", "indictment", "warrant", "exclusionary", "suppression",
                              "confrontation clause", "speedy trial", "cruel and unusual", "capital",
                              "death penalty", "incarceration", "parole", "probation", "restitution",
                              "prosecutor", "grand jury", "sentencing", "guidelines", "forfeiture"]),
    ("Civil Rights",        ["discrimination", "equal protection", "civil rights", "race", "gender", "sex",
                              "disability", "title vii", "title ix", "ada", "affirmative action", "voting rights",
                              "gerrymandering", "redistricting", "reapportionment", "section 1983",
                              "qualified immunity", "police", "excessive force", "lgbt", "transgender",
                              "same-sex", "sexual orientation", "national origin", "color", "section 2",
                              "voting", "ballot", "election", "voter", "minority", "segregation"]),
    ("First Amendment",     ["first amendment", "free speech", "freedom of speech", "freedom of religion",
                              "establishment clause", "free exercise", "press", "assembly", "petition",
                              "compelled speech", "defamation", "obscenity", "religious", "religion",
                              "church", "school prayer", "campaign finance", "political speech",
                              "content-based", "viewpoint", "public forum", "prior restraint",
                              "retaliation", "expressive", "sincerely held", "substantial burden"]),
    ("Due Process",         ["due process", "procedural", "substantive due process", "property interest",
                              "liberty interest", "notice", "hearing", "deprivation", "process",
                              "fundamental right", "liberty", "life", "property", "takings",
                              "just compensation", "eminent domain", "regulatory taking"]),
    ("Privacy",             ["privacy", "abortion", "contraception", "reproductive", "intimate", "personal data",
                              "bodily autonomy", "medical", "health care", "patient", "roe", "dobbs"]),
    ("Federal Taxation",    ["tax", "taxation", "irs", "internal revenue", "deduction", "income tax",
                              "estate tax", "excise", "tax code", "taxpayer", "levy", "fbar", "penalty",
                              "tax court", "treasury", "revenue"]),
    ("Judicial Power",      ["jurisdiction", "standing", "mootness", "ripeness", "article iii",
                              "sovereign immunity", "eleventh amendment", "exhaustion", "federal court",
                              "removal", "abstention", "class action", "consolidation", "mandamus",
                              "appellate jurisdiction", "certiorari", "original jurisdiction",
                              "non-delegation", "separation of powers", "appointment", "removal power"]),
    ("Federalism",          ["commerce clause", "federal preemption", "preempt", "tenth amendment",
                              "state authority", "federal law", "supremacy clause", "intergovernmental",
                              "state sovereignty", "anti-commandeering", "dormant commerce clause",
                              "state law", "federal statute", "conflict preemption", "field preemption"]),
    ("Economic Activity",   ["antitrust", "patent", "copyright", "trademark", "contract", "bankruptcy",
                              "arbitration", "securities", "commerce", "business", "corporation",
                              "intellectual property", "trade secret", "fair use", "monopoly",
                              "sherman act", "clayton act", "ftc", "sec", "fraud", "consumer",
                              "financial", "bank", "insurance", "rico", "wire fraud"]),
    ("Labor & Unions",      ["union", "collective bargaining", "nlra", "nlrb", "labor", "employee", "employer",
                              "workers", "wage", "erisa", "pension", "benefit", "flsa", "overtime",
                              "discrimination", "retaliation", "whistleblower", "fmla", "workforce"]),
    ("Immigration",         ["immigration", "deportation", "asylum", "alien", "visa", "citizenship",
                              "removal", "dhs", "border", "undocumented", "daca", "naturalization",
                              "ina", "refugee", "immigration judge", "country of origin"]),
    ("Administrative Law",  ["agency", "administrative", "chevron", "apa", "rulemaking", "regulation",
                              "deference", "arbitrary", "capricious", "notice and comment", "final rule",
                              "loper", "major questions", "executive order", "fda", "epa", "nlrb",
                              "ftc", "sec", "ferc", "fcc", "cfpb", "osha", "department of"]),
    ("Environmental Law",   ["environmental", "clean water", "clean air", "epa", "wetland", "wetlands",
                              "pollution", "endangered species", "climate", "carbon", "superfund",
                              "cercla", "waters of the united states", "wotus", "natural resource",
                              "national park", "public land", "mining", "drilling", "fracking"]),
    ("Veterans & Military", ["veteran", "military", "army", "navy", "marine", "service member",
                              "va ", "department of veterans", "court of appeals for the armed",
                              "ucmj", "discharge", "benefits", "service-connected", "combat"]),
    ("Interstate Relations", ["interstate", "compact", "water rights", "boundary", "escheat",
                               "unclaimed property", "state v. state", "original jurisdiction"]),
]


def _safe_str(val) -> str:
    """Return val as str, treating None/NaN/non-str as empty string."""
    if val is None:
        return ""
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return ""
    except Exception:
        pass
    return str(val) if not isinstance(val, str) else val


def infer_issue_area(detail: dict) -> str:
    """Infer issue area from case question/description text (Oyez does not expose it directly)."""
    text = " ".join([
        _safe_str(detail.get("question")),
        _safe_str(detail.get("description")),
        _safe_str(detail.get("facts_of_the_case")),
    ]).lower()
    if not text.strip():
        return "Unknown"
    best_label, best_score = "Unknown", 0
    for label, keywords in _ISSUE_KEYWORDS:
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score, best_label = score, label
    return best_label


def _normalize_party_name(value: str) -> str:
    text = _safe_str(value).lower()
    return " ".join(w for w in re.split(r"\W+", text) if len(w) > 2)


def _party_matches(candidate: str, target: str) -> bool:
    if not candidate or not target:
        return False
    candidate_words = candidate.split()
    target_words = target.split()
    return any(w in target for w in candidate_words) or any(w in candidate for w in target_words)


def infer_disposition(detail: dict) -> str:
    """Infer a rough disposition label from Oyez case detail data."""
    if not isinstance(detail, dict):
        return "Unknown"

    decs = detail.get("decisions") or []
    if decs and isinstance(decs, list):
        dec = decs[0] if decs else {}
        winner = _safe_str(dec.get("winning_party")).strip()
        case_name = _safe_str(detail.get("name")).strip()
        if winner and case_name:
            parts = re.split(r"\s+v\.?\s+", case_name, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                petitioner = _normalize_party_name(parts[0])
                respondent = _normalize_party_name(parts[1])
                winner_norm = _normalize_party_name(winner)
                if _party_matches(winner_norm, petitioner) and not _party_matches(winner_norm, respondent):
                    return "Reversed"
                if _party_matches(winner_norm, respondent) and not _party_matches(winner_norm, petitioner):
                    return "Affirmed"

        decision_type = _safe_str(dec.get("decision_type")).strip()
        if decision_type:
            return decision_type.title()

    return "Unknown"


# ── Paths ─────────────────────────────────────────────────────────────────────
_UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR  = os.path.dirname(_UTILS_DIR)
DATA_DIR   = os.path.join(_ROOT_DIR, "data_files", "oyez_data")
_LOG_FILE  = os.path.join(DATA_DIR, "api_fallback.log")

_SUBDIRS = (
    "cases", "case_detail", "justices", "courts",
    "decisions", "written_opinions", "oral_arguments",
    "opinion_announcements", "advocate_detail", "raw",
)

_HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe_name(url: str) -> str:
    """Convert a URL's path component to a cache filename."""
    path = urlparse(url).path.strip("/")
    return (path.replace("/", "_") + ".json") if path else "index.json"


def _find_local(url: str) -> str | None:
    """
    Search DATA_DIR for a locally cached file matching *url*.
    Returns the absolute path if found, else None.
    """
    parsed = urlparse(url)
    qs     = parse_qs(parsed.query)

    # ── Special case: cases-by-term list ─────────────────────────────────────
    # URL like  .../cases?filter=term:2024&per_page=...
    # Download script stores this as  cases/<term>/cases.json
    filt = qs.get("filter", [""])[0]
    if "term:" in filt:
        term = filt.split("term:")[1].split("&")[0].strip()
        candidate = os.path.join(DATA_DIR, "cases", term, "cases.json")
        if os.path.exists(candidate):
            return candidate
        # Term folder not cached — must hit the live API; do NOT fall through
        # to the general path search (which would match unrelated files like
        # raw/cases.json and return wrong data for the wrong term).
        return None

    # Any other URL that still has a query string is parameterised enough that
    # a filename-based match would be unreliable.  Force a live API call.
    if parsed.query:
        return None

    # ── General case: match on safe filename across all subdirs ──────────────
    target = _safe_name(url)
    if not os.path.isdir(DATA_DIR):
        return None

    for subdir in _SUBDIRS:
        subdir_path = os.path.join(DATA_DIR, subdir)
        if not os.path.isdir(subdir_path):
            continue

        # Direct hit in subdir root
        candidate = os.path.join(subdir_path, target)
        if os.path.exists(candidate):
            return candidate

        # One level deeper (e.g. case_detail/<term>/<file>.json)
        try:
            for entry in os.listdir(subdir_path):
                nested = os.path.join(subdir_path, entry, target)
                if os.path.exists(nested):
                    return nested
        except OSError:
            pass

    return None


def _log_miss(url: str) -> None:
    """Append a timestamped miss entry to the fallback log."""
    logging.debug("[oyez cache MISS] %s", url)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            ts = datetime.datetime.now().isoformat(timespec="seconds")
            fh.write(f"{ts} MISS {url}\n")
    except OSError:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

# Set to True to never make live API calls — serve only from local cache /
# parquet files.  The app's parquet data covers SCOTUS terms 1955–2025 which
# is sufficient for all current functionality.
LOCAL_ONLY: bool = True


def fetch_oyez(url: str) -> dict | list | None:
    """
    Return the parsed JSON for *url*.

    When LOCAL_ONLY is True (default):
      1. Checks DATA_DIR for a locally cached file.
      2. Returns None on a cache miss (no network call).

    When LOCAL_ONLY is False:
      1. Checks DATA_DIR first.
      2. On a miss, calls the live Oyez API, logs the miss, and caches
         the response to DATA_DIR/raw/ for future runs.
    """
    # ── Local hit ─────────────────────────────────────────────────────────────
    local_path = _find_local(url)
    if local_path:
        try:
            with open(local_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            pass  # corrupt file → fall through

    if LOCAL_ONLY:
        return None

    # ── Cache miss: log and call live API ─────────────────────────────────────
    _log_miss(url)
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    # Opportunistically cache the fresh response in raw/ for future runs
    try:
        raw_dir = os.path.join(DATA_DIR, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        dest = os.path.join(raw_dir, _safe_name(url))
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass

    return data
