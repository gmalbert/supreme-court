"""Drop-in CSV download button for any pandas DataFrame.

Usage:
    from utils.export import csv_download_button

    st.dataframe(df)
    csv_download_button(df, filename="scotus_cases_2024.csv")
"""

from __future__ import annotations

import streamlit as st
import pandas as pd


def csv_download_button(
    df: pd.DataFrame,
    filename: str,
    label: str = "⬇️ Download CSV",
    key: str | None = None,
) -> None:
    """Render a download button beneath any DataFrame."""
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=label,
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
        key=key or f"csv_{filename}",
        width="content",
    )

