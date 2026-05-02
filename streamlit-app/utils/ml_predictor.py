"""
ML Prediction engine for SCOTUS case outcomes.

Pipeline:
  1. Fetch historical case + vote data from Oyez (cached to CSV)
  2. Engineer features (circuit, issue area, term year, court composition)
  3. Train three model types:
       - Outcome model  : Affirm (0) vs Reverse/Vacate (1)
       - Split model    : Multiclass vote split (9-0, 8-1, 7-2, 6-3, 5-4)
       - Justice models : One binary classifier per current justice
  4. Persist with joblib; load on subsequent calls
"""

import os, time, json, re
import numpy as np
import pandas as pd
import requests
import joblib
from pathlib import Path
from collections import defaultdict

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import cross_val_score
from sklearn.metrics import accuracy_score, classification_report

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE        = Path(__file__).parent.parent        # streamlit-app/
DATA_DIR     = _HERE / "data"
MODEL_DIR    = DATA_DIR / "models"
CACHE_CSV    = DATA_DIR / "scotus_training_data.csv"
OUTCOME_PKL  = MODEL_DIR / "outcome_model.pkl"
SPLIT_PKL    = MODEL_DIR / "split_model.pkl"
JUSTICE_PKL  = MODEL_DIR / "justice_models.pkl"
META_JSON    = MODEL_DIR / "model_meta.json"

DATA_DIR.mkdir(exist_ok=True)
MODEL_DIR.mkdir(exist_ok=True)

HEADERS  = {"Accept": "application/json", "User-Agent": "SCOTUS-MLPredictor/1.0"}
OYEZ_BASE = "https://api.oyez.org"

# ── Current justices we predict for ──────────────────────────────────────────
CURRENT_JUSTICES = [
    "Roberts", "Thomas", "Alito", "Sotomayor",
    "Kagan", "Gorsuch", "Kavanaugh", "Barrett", "Jackson",
]

# ── Conservative bench counts by term (for training context) ─────────────────
CONS_COUNT_BY_TERM = {
    2000:5, 2001:5, 2002:5, 2003:5, 2004:5, 2005:5,
    2006:5, 2007:5, 2008:5, 2009:4, 2010:4, 2011:4,
    2012:4, 2013:4, 2014:4, 2015:4, 2016:4, 2017:5,
    2018:5, 2019:5, 2020:6, 2021:6, 2022:6, 2023:6,
}

# ── Circuit extraction ────────────────────────────────────────────────────────
_CIRCUIT_MAP = {
    "first circuit": "1st Circuit",  "second circuit": "2nd Circuit",
    "third circuit": "3rd Circuit",  "fourth circuit": "4th Circuit",
    "fifth circuit":  "5th Circuit", "sixth circuit":  "6th Circuit",
    "seventh circuit":"7th Circuit", "eighth circuit": "8th Circuit",
    "ninth circuit":  "9th Circuit", "tenth circuit":  "10th Circuit",
    "eleventh circuit":"11th Circuit","d.c. circuit":  "D.C. Circuit",
    "federal circuit": "Federal Circuit",
    "1st cir": "1st Circuit", "2nd cir": "2nd Circuit",
    "3rd cir": "3rd Circuit", "4th cir": "4th Circuit",
    "5th cir": "5th Circuit", "6th cir": "6th Circuit",
    "7th cir": "7th Circuit", "8th cir": "8th Circuit",
    "9th cir": "9th Circuit","10th cir":"10th Circuit",
    "11th cir":"11th Circuit",
}
_STATE_COURTS = re.compile(
    r"(supreme court of|court of appeals of|court of criminal appeals|"
    r"supreme judicial court|commonwealth court|appellate court of)", re.I
)

def extract_circuit(court_name: str) -> str:
    if not court_name:
        return "Other"
    cn = court_name.lower()
    for key, val in _CIRCUIT_MAP.items():
        if key in cn:
            return val
    if _STATE_COURTS.search(cn):
        return "State Supreme Court"
    return "Other"

# ── Disposition parsing ───────────────────────────────────────────────────────
def parse_outcome(disp: str) -> int | None:
    """1 = reversed/vacated, 0 = affirmed. None = unclear."""
    if not disp:
        return None
    d = disp.lower()
    if any(w in d for w in ["affirm"]):
        return 0
    if any(w in d for w in ["revers", "vacat"]):
        return 1
    return None

def parse_split(votes: list[dict]) -> str | None:
    """Return 'X-Y' split string or None."""
    maj = sum(1 for v in votes if (v.get("vote") or "").lower() in ("majority", "concurrence", "concurring in judgment"))
    dis = sum(1 for v in votes if (v.get("vote") or "").lower() == "dissent")
    total = maj + dis
    if total < 5:
        return None
    return f"{maj}-{dis}"

def normalise_split(split: str) -> str:
    """Map any split to canonical label."""
    if not split:
        return "5-4"
    try:
        maj, dis = map(int, split.split("-"))
    except Exception:
        return "5-4"
    if maj >= 9:   return "9-0"
    if maj == 8:   return "8-1"
    if maj == 7:   return "7-2"
    if maj == 6:   return "6-3"
    return "5-4"

# ── Oyez fetchers ─────────────────────────────────────────────────────────────
def _fetch(url: str, timeout: int = 10) -> dict | list | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def _last_name(full: str) -> str:
    parts = (full or "").strip().split()
    return parts[-1] if parts else ""

# ── Data collection ───────────────────────────────────────────────────────────
def collect_training_data(
    terms: list[int],
    progress_cb=None,          # callable(done, total, msg)
    stop_event=None,           # threading.Event for cancellation
) -> pd.DataFrame:
    """
    Fetch case + vote data for given terms from Oyez.
    Returns a DataFrame with one row per justice-vote.
    Saves/updates CACHE_CSV automatically.
    """
    # Load existing cache if present
    cached_terms: set[int] = set()
    existing_rows: list[dict] = []
    if CACHE_CSV.exists():
        try:
            existing_df = pd.read_csv(CACHE_CSV)
            existing_rows = existing_df.to_dict("records")
            cached_terms = set(existing_df["term"].unique().astype(int))
        except Exception:
            pass

    needed = [t for t in terms if t not in cached_terms]
    if not needed:
        return pd.DataFrame(existing_rows)

    new_rows: list[dict] = []
    for ti, term in enumerate(needed):
        if stop_event and stop_event.is_set():
            break
        if progress_cb:
            progress_cb(ti, len(needed), f"Fetching {term}–{term+1} term cases…")

        cases = _fetch(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0") or []
        n_cases = len(cases)

        for ci, c in enumerate(cases):
            if stop_event and stop_event.is_set():
                break
            if progress_cb and ci % 10 == 0:
                progress_cb(ti, len(needed),
                            f"Term {term}: case {ci+1}/{n_cases} — {len(new_rows)} rows collected so far")

            href = c.get("href", "")
            if not href:
                continue
            detail = _fetch(href)
            if not detail:
                continue

            # Basic case fields
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name", "") if isinstance(lower, dict) else str(lower)
            circuit = extract_circuit(lc_name)

            ia = detail.get("issue_area") or {}
            issue = ia.get("label", "Unknown") if isinstance(ia, dict) else "Unknown"

            disp = detail.get("disposition") or {}
            disp_label = disp.get("label", "") if isinstance(disp, dict) else str(disp)
            outcome = parse_outcome(disp_label)
            if outcome is None:
                continue   # skip unclear dispositions

            n_cons = CONS_COUNT_BY_TERM.get(term, 5)
            case_name = detail.get("name", "")
            docket = detail.get("docket_number", "")

            # Vote rows
            for decision in (detail.get("decisions") or []):
                votes = decision.get("votes") or []
                split = parse_split(votes)
                split_norm = normalise_split(split) if split else None
                if not split_norm:
                    continue

                # Record per-justice rows
                for vote in votes:
                    member = vote.get("member") or {}
                    j_full = member.get("name", "") if isinstance(member, dict) else ""
                    j_last = _last_name(j_full)
                    v      = (vote.get("vote") or "").lower()
                    if not j_last or not v:
                        continue
                    is_majority = int(v in ("majority", "concurrence", "concurring in judgment"))

                    new_rows.append({
                        "term": term, "case": case_name, "docket": docket,
                        "circuit": circuit, "issue_area": issue,
                        "outcome": outcome, "split": split_norm,
                        "n_conservative": n_cons,
                        "justice": j_last, "is_majority": is_majority,
                    })

            time.sleep(0.03)

    # Merge + save
    all_rows = existing_rows + new_rows
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df.to_csv(CACHE_CSV, index=False)
    return df

# ── Feature engineering ───────────────────────────────────────────────────────
CAT_FEATURES = ["circuit", "issue_area"]
NUM_FEATURES = ["n_conservative", "term_year_norm"]

def _make_feature_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["circuit", "issue_area", "n_conservative", "term"]].copy()
    out["term_year_norm"] = (out["term"] - 2005) / 10.0   # scale around Roberts Court
    return out[CAT_FEATURES + NUM_FEATURES]

def _build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_FEATURES),
        ("num", StandardScaler(), NUM_FEATURES),
    ])

# ── Model training ─────────────────────────────────────────────────────────────
def train_models(
    df: pd.DataFrame,
    progress_cb=None,
) -> dict:
    """
    Train outcome, split, and per-justice models.
    Returns a results dict with accuracy metrics.
    """
    results: dict = {}

    # ── Deduplicate at case level for outcome + split models ──────────────────
    case_df = (
        df.groupby(["docket", "term", "circuit", "issue_area", "outcome", "split", "n_conservative"])
        .size().reset_index(name="_cnt")
        .drop(columns="_cnt")
    )
    case_df["term_year_norm"] = (case_df["term"] - 2005) / 10.0
    X_case = case_df[CAT_FEATURES + NUM_FEATURES]
    y_outcome = case_df["outcome"]
    y_split   = case_df["split"]

    # Temporal train/test: test on last 2 terms
    test_terms = sorted(case_df["term"].unique())[-2:]
    train_mask = ~case_df["term"].isin(test_terms)
    test_mask  =  case_df["term"].isin(test_terms)
    X_train, X_test   = X_case[train_mask], X_case[test_mask]
    yo_train, yo_test = y_outcome[train_mask], y_outcome[test_mask]
    ys_train, ys_test = y_split[train_mask], y_split[test_mask]

    if progress_cb:
        progress_cb(0, 3, f"Training outcome model on {len(X_train)} cases…")

    # ── Outcome model ─────────────────────────────────────────────────────────
    prep_o = _build_preprocessor()
    gb_o = GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.08,
        subsample=0.85, random_state=42,
    )
    outcome_pipeline = Pipeline([("prep", prep_o), ("clf", gb_o)])
    outcome_pipeline.fit(X_train, yo_train)
    # Calibrate
    cal_outcome = CalibratedClassifierCV(outcome_pipeline, method="sigmoid", cv="prefit")
    cal_outcome.fit(X_test, yo_test)

    yo_pred = cal_outcome.predict(X_test)
    acc_o = accuracy_score(yo_test, yo_pred)
    cv_o  = cross_val_score(outcome_pipeline, X_case, y_outcome, cv=5, scoring="accuracy").mean()
    results["outcome_accuracy_holdout"] = round(float(acc_o), 4)
    results["outcome_accuracy_cv5"]     = round(float(cv_o),  4)
    results["outcome_n_train"]          = int(len(X_train))
    results["outcome_n_test"]           = int(len(X_test))
    results["test_terms"]               = [int(t) for t in test_terms]
    results["outcome_report"]           = classification_report(yo_test, yo_pred, output_dict=True)

    joblib.dump(cal_outcome, OUTCOME_PKL)

    if progress_cb:
        progress_cb(1, 3, f"Training vote-split model (5 classes)…")

    # ── Split model ───────────────────────────────────────────────────────────
    prep_s = _build_preprocessor()
    gb_s = GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.08,
        subsample=0.85, random_state=42,
    )
    split_pipeline = Pipeline([("prep", prep_s), ("clf", gb_s)])
    split_pipeline.fit(X_train, ys_train)
    cal_split = CalibratedClassifierCV(split_pipeline, method="sigmoid", cv="prefit")
    cal_split.fit(X_test, ys_test)

    ys_pred  = cal_split.predict(X_test)
    acc_s    = accuracy_score(ys_test, ys_pred)
    results["split_accuracy_holdout"] = round(float(acc_s), 4)
    results["split_classes"]          = list(cal_split.classes_)
    joblib.dump(cal_split, SPLIT_PKL)

    if progress_cb:
        progress_cb(2, 3, "Training per-justice models…")

    # ── Per-justice models ────────────────────────────────────────────────────
    justice_models: dict = {}
    justice_results: dict = {}
    df["term_year_norm"] = (df["term"] - 2005) / 10.0
    X_all_j = df[CAT_FEATURES + NUM_FEATURES]

    for justice in CURRENT_JUSTICES:
        j_df = df[df["justice"] == justice]
        if len(j_df) < 30:
            continue
        Xj = j_df[CAT_FEATURES + NUM_FEATURES]
        yj = j_df["is_majority"]

        # Temporal split for justice
        j_test_terms  = sorted(j_df["term"].unique())[-2:]
        j_train_mask  = ~j_df["term"].isin(j_test_terms)
        j_test_mask   =  j_df["term"].isin(j_test_terms)
        Xj_train, Xj_test = Xj[j_train_mask], Xj[j_test_mask]
        yj_train, yj_test = yj[j_train_mask], yj[j_test_mask]

        if len(Xj_train) < 20:
            continue

        prep_j = _build_preprocessor()
        lr_j   = LogisticRegression(C=0.8, max_iter=500, class_weight="balanced", random_state=42)
        j_pipeline = Pipeline([("prep", prep_j), ("clf", lr_j)])
        j_pipeline.fit(Xj_train, yj_train)

        if len(Xj_test) >= 10:
            cal_j = CalibratedClassifierCV(j_pipeline, method="sigmoid", cv="prefit")
            cal_j.fit(Xj_test, yj_test)
            yj_pred = cal_j.predict(Xj_test)
            j_acc   = accuracy_score(yj_test, yj_pred)
            justice_models[justice]  = cal_j
            justice_results[justice] = {"accuracy": round(float(j_acc), 4), "n": int(len(j_df))}
        else:
            justice_models[justice]  = j_pipeline
            justice_results[justice] = {"accuracy": None, "n": int(len(j_df))}

    joblib.dump(justice_models, JUSTICE_PKL)
    results["justice_results"] = justice_results

    # ── Feature importances from outcome model ────────────────────────────────
    try:
        inner_pipeline = cal_outcome.estimator
        prep_fitted    = inner_pipeline.named_steps["prep"]
        clf_fitted     = inner_pipeline.named_steps["clf"]
        feature_names  = list(prep_fitted.get_feature_names_out())
        importances    = clf_fitted.feature_importances_.tolist()
        results["feature_importances"] = dict(zip(feature_names, importances))
    except Exception:
        results["feature_importances"] = {}

    # ── Save metadata ─────────────────────────────────────────────────────────
    import datetime
    results["trained_at"]   = datetime.datetime.now().isoformat()
    results["terms_in_data"] = sorted(int(t) for t in df["term"].unique())
    results["total_votes"]  = int(len(df))
    results["total_cases"]  = int(case_df["docket"].nunique())

    with open(META_JSON, "w") as f:
        json.dump(results, f, indent=2)

    return results

# ── Inference ─────────────────────────────────────────────────────────────────
def load_models() -> tuple[object, object, dict]:
    """Return (outcome_model, split_model, justice_models_dict). Raises if not trained."""
    if not OUTCOME_PKL.exists():
        raise FileNotFoundError("Models not yet trained.")
    outcome_model  = joblib.load(OUTCOME_PKL)
    split_model    = joblib.load(SPLIT_PKL)
    justice_models = joblib.load(JUSTICE_PKL) if JUSTICE_PKL.exists() else {}
    return outcome_model, split_model, justice_models

def load_meta() -> dict:
    if not META_JSON.exists():
        return {}
    try:
        with open(META_JSON) as f:
            return json.load(f)
    except Exception:
        return {}

def is_trained() -> bool:
    return OUTCOME_PKL.exists() and META_JSON.exists()

def predict(
    circuit: str,
    issue_area: str,
    n_conservative: int = 6,
    term_year: int = 2024,
    sg_support: bool = False,       # used as post-hoc adjustment only
    circuit_split: bool = False,    # used as post-hoc adjustment only
) -> dict:
    """
    Run inference using trained models.
    Returns dict with p_reverse, p_affirm, split_probs, justice_probs.
    """
    outcome_model, split_model, justice_models = load_models()

    X = pd.DataFrame([{
        "circuit":       circuit,
        "issue_area":    issue_area,
        "n_conservative": n_conservative,
        "term_year_norm": (term_year - 2005) / 10.0,
    }])

    # Outcome probability
    p_proba = outcome_model.predict_proba(X)[0]
    classes_o = list(outcome_model.classes_)
    p_reverse = float(p_proba[classes_o.index(1)]) if 1 in classes_o else 0.5
    p_affirm  = 1.0 - p_reverse

    # Post-hoc adjustments (not in training data but known influential)
    if sg_support:    p_reverse = min(0.93, p_reverse + 0.07)
    if circuit_split: p_reverse = min(0.93, p_reverse + 0.05)
    p_affirm = 1.0 - p_reverse

    # Split probability
    split_proba  = split_model.predict_proba(X)[0]
    split_classes = list(split_model.classes_)
    split_probs   = {cls: float(prob) for cls, prob in zip(split_classes, split_proba)}
    split_label   = split_classes[int(np.argmax(split_proba))]

    # Per-justice probabilities
    justice_probs: dict[str, float] = {}
    for justice, jmodel in justice_models.items():
        try:
            jp = jmodel.predict_proba(X)[0]
            jclasses = list(jmodel.classes_)
            # P(is_majority=1)
            p_maj = float(jp[jclasses.index(1)]) if 1 in jclasses else 0.5
            justice_probs[justice] = p_maj
        except Exception:
            justice_probs[justice] = 0.5

    return {
        "p_reverse":    round(p_reverse, 4),
        "p_affirm":     round(p_affirm, 4),
        "split_probs":  split_probs,
        "split_label":  split_label,
        "justice_probs": justice_probs,
    }
