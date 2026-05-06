import base64
import os

import streamlit as st


def add_sidebar_logo():
    """Inject the site logo at the bottom-center of the sidebar."""
    logo_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data_files", "logo.png")
    )
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()

    st.sidebar.markdown(
        f"""
        <div style="text-align:center; padding: 0.5rem 1rem 0 1rem;">
            <img src="data:image/png;base64,{logo_b64}"
                 style="width:100%;max-width:330px;height:auto;display:block;margin:0 auto;"
                 alt="Supreme Scrutiny Logo">
        </div>
        """,
        unsafe_allow_html=True,
    )
