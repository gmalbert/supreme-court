"""
Build data_files/circuit_reversal_rates.json from circuit_stats.parquet.

Output schema:
{
  "<circuit>": {
    "total": int,
    "reversed_vacated": int,
    "affirmed": int,
    "remanded": int,
    "reversal_rate": float,   # reversed_vacated / (reversed_vacated + affirmed)
    "by_term": {
      "<term>": {"total": int, "reversed_vacated": int, "reversal_rate": float}
    },
    "by_issue_area": {
      "<issue_area>": {"total": int, "reversed_vacated": int, "reversal_rate": float}
    }
  }
}
"""
import os
import json
import pandas as pd

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(_REPO, "data_files", "circuit_stats.parquet")
DEST = os.path.join(_REPO, "data_files", "circuit_reversal_rates.json")


def _rate(rev: int, aff: int) -> float:
    denom = rev + aff
    return round(rev / denom, 4) if denom else 0.0


def build(src: str = SRC, dest: str = DEST) -> dict:
    df = pd.read_parquet(src)

    result: dict = {}

    for circuit, grp in df.groupby("circuit"):
        total   = len(grp)
        rev     = int((grp["outcome"] == "Reversed/Vacated").sum())
        aff     = int((grp["outcome"] == "Affirmed").sum())
        rem     = int((grp["outcome"] == "Remanded").sum())

        by_term: dict = {}
        for term, tgrp in grp.groupby("term"):
            t_total = len(tgrp)
            t_rev   = int((tgrp["outcome"] == "Reversed/Vacated").sum())
            t_aff   = int((tgrp["outcome"] == "Affirmed").sum())
            by_term[str(term)] = {
                "total": t_total,
                "reversed_vacated": t_rev,
                "reversal_rate": _rate(t_rev, t_aff),
            }

        by_issue: dict = {}
        for issue, igrp in grp.groupby("issue_area"):
            i_total = len(igrp)
            i_rev   = int((igrp["outcome"] == "Reversed/Vacated").sum())
            i_aff   = int((igrp["outcome"] == "Affirmed").sum())
            by_issue[str(issue)] = {
                "total": i_total,
                "reversed_vacated": i_rev,
                "reversal_rate": _rate(i_rev, i_aff),
            }

        result[str(circuit)] = {
            "total": total,
            "reversed_vacated": rev,
            "affirmed": aff,
            "remanded": rem,
            "reversal_rate": _rate(rev, aff),
            "by_term": by_term,
            "by_issue_area": by_issue,
        }

    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(f"Wrote {len(result)} circuits → {dest}")
    return result


if __name__ == "__main__":
    build()
