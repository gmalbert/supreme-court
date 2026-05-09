"""
TF-IDF semantic case search.

Builds a TF-IDF index from the case_detail parquet's 'facts_of_the_case' and
'question' columns. Fully offline — no API key or internet required.
"""

from __future__ import annotations
import os
import pandas as pd
import numpy as np

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DETAIL_PARQUET = os.path.join(_REPO_ROOT, "data", "case_detail.parquet")

# Module-level cache so the index is built once per Streamlit process
_vectorizer = None
_tfidf_matrix = None
_index_df: pd.DataFrame | None = None


def _build_index() -> None:
    global _vectorizer, _tfidf_matrix, _index_df
    from sklearn.feature_extraction.text import TfidfVectorizer

    df = pd.read_parquet(
        _DETAIL_PARQUET,
        columns=["name", "term", "href", "docket_number", "facts_of_the_case", "question", "description"],
    )

    # Combine text fields into a single search corpus
    def _combine(row: pd.Series) -> str:
        parts = [
            row.get("facts_of_the_case"),
            row.get("question"),
            row.get("description"),
            row.get("name"),
        ]
        return " ".join(str(p) for p in parts if p and str(p) not in ("nan", "None")).lower()

    df["_text"] = df.apply(_combine, axis=1)
    df = df[df["_text"].str.len() > 20].reset_index(drop=True)

    vec = TfidfVectorizer(
        max_features=30_000,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
        stop_words="english",
    )
    matrix = vec.fit_transform(df["_text"])

    _vectorizer = vec
    _tfidf_matrix = matrix
    _index_df = df[["name", "term", "href", "docket_number"]].copy()


def search(query: str, top_k: int = 10) -> list[dict]:
    """Return up to top_k cases whose text best matches the query string.

    Each result dict has: name, term, href, docket_number, score.
    """
    global _vectorizer, _tfidf_matrix, _index_df

    if _vectorizer is None:
        _build_index()

    if not query or not query.strip():
        return []

    from sklearn.metrics.pairwise import cosine_similarity

    q_vec = _vectorizer.transform([query.lower()])
    scores = cosine_similarity(q_vec, _tfidf_matrix).flatten()
    top_idx = scores.argsort()[::-1][:top_k]

    results = []
    for i in top_idx:
        score = float(scores[i])
        if score < 0.01:
            break
        row = _index_df.iloc[i]
        results.append({
            "name": row["name"],
            "term": row["term"],
            "href": row["href"],
            "docket_number": row.get("docket_number", ""),
            "score": round(score, 4),
        })
    return results


def is_available() -> bool:
    """Return True if the detail parquet exists and sklearn is importable."""
    if not os.path.exists(_DETAIL_PARQUET):
        return False
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False
