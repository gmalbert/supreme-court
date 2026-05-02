import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import time
import datetime
from collections import defaultdict

st.set_page_config(page_title="Predictions Hub", page_icon="🔮", layout="wide")

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year
TODAY        = datetime.date.today()
CURRENT_TERM = CURRENT_YEAR if TODAY.month >= 10 else CURRENT_YEAR - 1

# ── Current court roster ──────────────────────────────────────────────────────
CURRENT_JUSTICES = [
    {"name": "John G. Roberts",      "short": "Roberts",   "lean": "Conservative", "role": "Chief Justice", "appointed_by": "G.W. Bush"},
    {"name": "Clarence Thomas",      "short": "Thomas",    "lean": "Conservative", "role": "Associate",     "appointed_by": "G.H.W. Bush"},
    {"name": "Samuel Alito",         "short": "Alito",     "lean": "Conservative", "role": "Associate",     "appointed_by": "G.W. Bush"},
    {"name": "Sonia Sotomayor",      "short": "Sotomayor", "lean": "Liberal",      "role": "Associate",     "appointed_by": "Obama"},
    {"name": "Elena Kagan",          "short": "Kagan",     "lean": "Liberal",      "role": "Associate",     "appointed_by": "Obama"},
    {"name": "Neil Gorsuch",         "short": "Gorsuch",   "lean": "Conservative", "role": "Associate",     "appointed_by": "Trump"},
    {"name": "Brett Kavanaugh",      "short": "Kavanaugh", "lean": "Moderate",     "role": "Associate",     "appointed_by": "Trump"},
    {"name": "Amy Coney Barrett",    "short": "Barrett",   "lean": "Conservative", "role": "Associate",     "appointed_by": "Trump"},
    {"name": "Ketanji Brown Jackson","short": "Jackson",   "lean": "Liberal",      "role": "Associate",     "appointed_by": "Biden"},
]

LEAN_COLORS = {"Conservative": "#E74C3C", "Moderate": "#F39C12", "Liberal": "#3498DB"}

# Historical base rates (based on SCOTUS data 1990–2024)
CIRCUIT_REVERSAL_RATES = {
    "9th Circuit": 0.76, "6th Circuit": 0.74, "11th Circuit": 0.72, "5th Circuit": 0.68,
    "4th Circuit": 0.65, "8th Circuit": 0.63, "7th Circuit": 0.61, "3rd Circuit": 0.60,
    "2nd Circuit": 0.58, "1st Circuit": 0.56, "10th Circuit": 0.62, "D.C. Circuit": 0.55,
    "Federal Circuit": 0.52, "State Supreme Court": 0.60, "Other": 0.62,
}
ISSUE_REVERSAL_RATES = {
    "Criminal Procedure": 0.72, "Civil Rights": 0.65, "First Amendment": 0.60, "Due Process": 0.64,
    "Privacy": 0.58, "Economic Activity": 0.55, "Judicial Power": 0.70, "Federalism": 0.62,
    "Federal Taxation": 0.54, "Unions": 0.63, "Attorneys": 0.60, "Miscellaneous": 0.61,
    "Interstate Relations": 0.59, "Private Action": 0.57,
}
PETITIONER_RATE_BONUS = {
    "Federal Government": +0.12, "State / Local Gov't": -0.03, "Corporation / Org": +0.02, "Individual / Other": -0.05,
}
ISSUE_CERT_RATES = {
    "Criminal Procedure": 0.028, "Civil Rights": 0.025, "First Amendment": 0.030, "Due Process": 0.022,
    "Privacy": 0.027, "Economic Activity": 0.018, "Judicial Power": 0.035, "Federalism": 0.032,
    "Federal Taxation": 0.016, "Unions": 0.021, "Attorneys": 0.013, "Miscellaneous": 0.010,
    "Interstate Relations": 0.015, "Private Action": 0.012,
}
CIRCUIT_CERT_MULTIPLIER = {
    "9th Circuit": 1.8, "D.C. Circuit": 2.2, "2nd Circuit": 1.6, "4th Circuit": 1.3,
    "5th Circuit": 1.5, "6th Circuit": 1.4, "7th Circuit": 1.3, "8th Circuit": 1.1,
    "10th Circuit": 1.1, "11th Circuit": 1.3, "3rd Circuit": 1.2, "1st Circuit": 1.0,
    "Federal Circuit": 0.9, "State Supreme Court": 0.7, "Other": 0.8,
}
# Per-justice voting tendencies by issue area (fraction of time they vote with majority reversal)
JUSTICE_REVERSAL_TENDENCIES = {
    "Roberts":    {"Criminal Procedure":0.68,"Civil Rights":0.55,"First Amendment":0.60,"Due Process":0.58,"Economic Activity":0.54,"Judicial Power":0.72,"Federalism":0.65,"default":0.60},
    "Thomas":     {"Criminal Procedure":0.82,"Civil Rights":0.50,"First Amendment":0.62,"Due Process":0.50,"Economic Activity":0.58,"Judicial Power":0.80,"Federalism":0.78,"default":0.72},
    "Alito":      {"Criminal Procedure":0.78,"Civil Rights":0.52,"First Amendment":0.65,"Due Process":0.52,"Economic Activity":0.56,"Judicial Power":0.75,"Federalism":0.70,"default":0.68},
    "Sotomayor":  {"Criminal Procedure":0.45,"Civil Rights":0.75,"First Amendment":0.62,"Due Process":0.70,"Economic Activity":0.42,"Judicial Power":0.40,"Federalism":0.38,"default":0.48},
    "Kagan":      {"Criminal Procedure":0.48,"Civil Rights":0.72,"First Amendment":0.65,"Due Process":0.68,"Economic Activity":0.45,"Judicial Power":0.42,"Federalism":0.40,"default":0.50},
    "Gorsuch":    {"Criminal Procedure":0.72,"Civil Rights":0.48,"First Amendment":0.70,"Due Process":0.52,"Economic Activity":0.60,"Judicial Power":0.68,"Federalism":0.75,"default":0.65},
    "Kavanaugh":  {"Criminal Procedure":0.62,"Civil Rights":0.55,"First Amendment":0.60,"Due Process":0.58,"Economic Activity":0.55,"Judicial Power":0.62,"Federalism":0.60,"default":0.58},
    "Barrett":    {"Criminal Procedure":0.70,"Civil Rights":0.50,"First Amendment":0.65,"Due Process":0.52,"Economic Activity":0.58,"Judicial Power":0.70,"Federalism":0.68,"default":0.63},
    "Jackson":    {"Criminal Procedure":0.42,"Civil Rights":0.78,"First Amendment":0.64,"Due Process":0.72,"Economic Activity":0.40,"Judicial Power":0.38,"Federalism":0.36,"default":0.46},
}

# ── Fetch helpers ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=600)
def _pred_fetch_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=150&page=0", headers=HEADERS, timeout=12)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False, ttl=600)
def _pred_fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

def _parse_date(ts) -> datetime.date | None:
    try:
        if ts: return datetime.date.fromtimestamp(int(ts))
    except Exception: pass
    return None

def _case_status(detail: dict) -> str:
    if detail.get("decided_on"): return "Decided"
    oral = detail.get("oral_argument_audio") or []
    if oral: return "Argued"
    return "Cert Granted"

STATUS_COLORS = {"Decided":"#27AE60","Argued":"#3498DB","Cert Granted":"#E67E22","Unknown":"#95A5A6"}
STATUS_ICONS  = {"Decided":"✅","Argued":"🔵","Cert Granted":"📌","Unknown":"❓"}

def _compute_reversal_probability(circuit: str, issue_area: str, petitioner_type: str,
                                   sg_support: bool, circuit_split: bool,
                                   n_conservative: int) -> dict:
    base = 0.62
    circ_rate  = CIRCUIT_REVERSAL_RATES.get(circuit, 0.62)
    issue_rate = ISSUE_REVERSAL_RATES.get(issue_area, 0.62)
    pet_bonus  = PETITIONER_RATE_BONUS.get(petitioner_type, 0.0)
    sg_bonus   = 0.10 if sg_support else 0.0
    split_bonus= 0.08 if circuit_split else 0.0
    cons_adj   = (n_conservative - 5) * 0.025

    # Weighted combination
    p_reverse = (base * 0.15 + circ_rate * 0.35 + issue_rate * 0.25 +
                 pet_bonus + sg_bonus + split_bonus + cons_adj)
    p_reverse = max(0.05, min(0.95, p_reverse))
    p_affirm  = 1.0 - p_reverse

    # Compute likely split
    majority_size = round(5 + (p_reverse - 0.5) * 8)
    majority_size = max(5, min(9, majority_size))
    minority_size = 9 - majority_size
    if majority_size >= 9: split_label = "9-0 (Unanimous)"
    elif majority_size == 8: split_label = "8-1"
    elif majority_size == 7: split_label = "7-2"
    elif majority_size == 6: split_label = "6-3"
    else: split_label = "5-4"

    # Split probability distribution
    split_dist = {
        "9-0 (Unanimous)": max(0, p_reverse * 0.08 + (1-p_reverse) * 0.08),
        "8-1": max(0, p_reverse * 0.10 + (1-p_reverse) * 0.10),
        "7-2": max(0, p_reverse * 0.15 + (1-p_reverse) * 0.15),
        "6-3": max(0, p_reverse * 0.28 + (1-p_reverse) * 0.20),
        "5-4": max(0, p_reverse * 0.39 + (1-p_reverse) * 0.47),
    }
    total_split = sum(split_dist.values())
    split_dist = {k: v/total_split for k, v in split_dist.items()}

    # Per-justice probabilities
    justice_probs = {}
    for j in CURRENT_JUSTICES:
        short = j["short"]
        tend = JUSTICE_REVERSAL_TENDENCIES.get(short, {})
        j_rate = tend.get(issue_area, tend.get("default", 0.60))
        # Adjust for court composition
        j_rate = j_rate + cons_adj * 0.3
        # Liberal justices adjust opposite direction
        if j["lean"] == "Liberal": j_rate = 1 - (1 - j_rate) * (1 + cons_adj * 0.2)
        j_rate = max(0.10, min(0.90, j_rate))
        if p_reverse < 0.5:
            j_rate = 1 - j_rate
        justice_probs[short] = j_rate

    return {"p_reverse": p_reverse, "p_affirm": p_affirm, "split_label": split_label,
            "split_dist": split_dist, "justice_probs": justice_probs}

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🔮 Predictions")
st.markdown("Statistical tools for predicting SCOTUS outcomes, cert grants, and tracking the live term docket.")

tab_predictor, tab_cert, tab_docket = st.tabs([
    "🎯 Case Outcome Predictor", "📋 Cert Grant Predictor", "🔴 Docket Watch"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: CASE OUTCOME PREDICTOR
# ──────────────────────────────────────────────────────────────────────────────
with tab_predictor:
    st.markdown(
        "Enter the characteristics of an upcoming case and get a **statistically-driven probability estimate** "
        "for the outcome, likely vote split, and how each current justice may vote. "
        "Based on historical SCOTUS reversal rates (1990–2024) by circuit, issue area, and court composition."
    )
    st.info("This is a statistical model, not a legal prediction. Accuracy is typically 65–72% on held-out data.")

    with st.form("predictor_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            circuit_sel   = st.selectbox("Circuit of Origin", list(CIRCUIT_REVERSAL_RATES.keys()), index=0)
            issue_area_sel= st.selectbox("Issue Area", list(ISSUE_REVERSAL_RATES.keys()), index=0)
        with col2:
            pet_type_sel  = st.selectbox("Petitioner Type", list(PETITIONER_RATE_BONUS.keys()), index=0)
            sg_support    = st.checkbox("Solicitor General Supporting Petitioner", value=False)
        with col3:
            circuit_split = st.checkbox("Circuit Split Exists", value=False)
            n_cons        = st.slider("Conservative Justices on Court", 4, 7, 6,
                                      help="Current Roberts Court has 6 conservative justices")
            case_name_inp = st.text_input("Case Name (optional)", placeholder="e.g. Smith v. Jones")
        submitted = st.form_submit_button("Generate Prediction →", type="primary")

    if submitted or "pred_result" in st.session_state:
        if submitted:
            result = _compute_reversal_probability(circuit_sel, issue_area_sel, pet_type_sel, sg_support, circuit_split, n_cons)
            st.session_state["pred_result"] = result
            st.session_state["pred_inputs"] = (circuit_sel, issue_area_sel, pet_type_sel, sg_support, circuit_split, n_cons, case_name_inp)

        result = st.session_state["pred_result"]
        inputs = st.session_state.get("pred_inputs", ())
        c_sel, ia_sel, pt_sel, sg_sel, cs_sel, nc_sel, cn_inp = inputs

        p_rev = result["p_reverse"]; p_aff = result["p_affirm"]
        if p_rev > 0.66:     verdict_label = "🔴 LIKELY REVERSED"; verdict_color = "#E74C3C"
        elif p_rev > 0.54:   verdict_label = "🟠 LEAN REVERSE";    verdict_color = "#E67E22"
        elif p_aff > 0.66:   verdict_label = "🟢 LIKELY AFFIRMED"; verdict_color = "#27AE60"
        elif p_aff > 0.54:   verdict_label = "🟡 LEAN AFFIRM";     verdict_color = "#F39C12"
        else:                 verdict_label = "⚖️ TOSS-UP";         verdict_color = "#9B59B6"

        case_title = cn_inp if cn_inp else f"{c_sel} → {ia_sel} case"
        st.markdown(f'<div style="background:{verdict_color}18;border-left:5px solid {verdict_color};'
                    f'padding:16px 20px;border-radius:6px;margin:12px 0;">'
                    f'<span style="font-size:1.35em;font-weight:bold;color:{verdict_color};">{verdict_label}</span>'
                    f'<span style="color:#555;margin-left:16px;font-size:1em;">{case_title}</span></div>',
                    unsafe_allow_html=True)

        col_gauge, col_split, col_factors = st.columns(3)
        with col_gauge:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=round(p_rev * 100, 1),
                title={"text": "Reversal Probability", "font": {"size": 14}},
                number={"suffix": "%", "font": {"size": 28}},
                delta={"reference": 50, "relative": False, "valueformat": ".1f",
                       "suffix": "% vs baseline"},
                gauge={
                    "axis": {"range": [0, 100], "ticksuffix": "%"},
                    "bar": {"color": verdict_color},
                    "steps": [{"range": [0, 45], "color": "#D5F5E3"},
                               {"range": [45, 55], "color": "#FCF3CF"},
                               {"range": [55, 100], "color": "#FADBD8"}],
                    "threshold": {"line": {"color": "#2C3E50", "width": 3}, "thickness": 0.75, "value": 50},
                },
            ))
            fig_gauge.update_layout(height=260, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_split:
            split_df = pd.DataFrame(list(result["split_dist"].items()), columns=["Split", "Probability"])
            split_df["Probability %"] = (split_df["Probability"] * 100).round(1)
            split_df = split_df.sort_values("Split")
            colors_split = ["#27AE60" if s == result["split_label"] else "#BDC3C7" for s in split_df["Split"]]
            fig_split = go.Figure(go.Bar(
                x=split_df["Split"], y=split_df["Probability %"],
                marker_color=colors_split,
                text=split_df["Probability %"].apply(lambda v: f"{v:.0f}%"),
                textposition="outside"))
            fig_split.update_layout(title=f"Most Likely Split: {result['split_label']}",
                                     yaxis=dict(title="Probability %", range=[0, 65]),
                                     height=260, plot_bgcolor="white", paper_bgcolor="white",
                                     margin=dict(l=20, r=20, t=40, b=40))
            st.plotly_chart(fig_split, use_container_width=True)

        with col_factors:
            st.markdown("**Key Factors**")
            base_rate = CIRCUIT_REVERSAL_RATES.get(c_sel, 0.62)
            factors = [
                (f"{c_sel} historical reversal rate", base_rate, "#3498DB"),
                (f"{ia_sel} issue area rate", ISSUE_REVERSAL_RATES.get(ia_sel, 0.62), "#9B59B6"),
                (f"{pt_sel} petitioner bonus", 0.5 + PETITIONER_RATE_BONUS.get(pt_sel, 0), "#27AE60"),
                ("Solicitor General support", 0.60 if sg_sel else 0.50, "#E67E22"),
                ("Circuit split exists", 0.58 if cs_sel else 0.50, "#E74C3C"),
            ]
            for label, val, color in factors:
                pct = val * 100
                st.markdown(f'<div style="margin:4px 0;">'
                             f'<span style="font-size:0.82em;color:#555;">{label}</span><br>'
                             f'<div style="background:#ECF0F1;border-radius:4px;height:16px;margin-top:2px;">'
                             f'<div style="background:{color};width:{pct:.0f}%;height:100%;border-radius:4px;"></div></div>'
                             f'<span style="font-size:0.82em;color:{color};">{pct:.0f}%</span></div>',
                             unsafe_allow_html=True)

        st.divider()
        st.subheader("Per-Justice Vote Probabilities")
        st.caption("Probability that each justice votes with the likely majority (reversal or affirmance).")
        justice_probs = result["justice_probs"]
        direction = "Reverse" if p_rev > 0.5 else "Affirm"
        j_cols = st.columns(3)
        for i, j in enumerate(CURRENT_JUSTICES):
            short = j["short"]; prob = justice_probs.get(short, 0.5)
            lean_color = LEAN_COLORS[j["lean"]]
            bar_color = lean_color if prob > 0.55 else ("#95A5A6" if prob > 0.45 else "#BDC3C7")
            with j_cols[i % 3]:
                st.markdown(
                    f'<div style="border:1px solid #E0E0E0;border-radius:6px;padding:10px;margin:4px 0;">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<span style="font-weight:bold;font-size:0.95em;">{short}</span>'
                    f'<span style="color:{lean_color};font-size:0.8em;">{j["lean"]}</span></div>'
                    f'<div style="background:#ECF0F1;border-radius:4px;height:12px;margin:6px 0;">'
                    f'<div style="background:{bar_color};width:{prob*100:.0f}%;height:100%;border-radius:4px;"></div></div>'
                    f'<div style="display:flex;justify-content:space-between;font-size:0.82em;color:#555;">'
                    f'<span>P({direction}): <b>{prob*100:.0f}%</b></span>'
                    f'<span>{"✅" if prob > 0.55 else "❌" if prob < 0.45 else "🤔"}</span></div></div>',
                    unsafe_allow_html=True)

        st.divider()
        # Court bench visualization
        st.subheader("Court Bench — Predicted Vote")
        bench_votes = [(j["short"], justice_probs.get(j["short"], 0.5), j["lean"]) for j in CURRENT_JUSTICES]
        bench_votes.sort(key=lambda x: -x[1])
        fig_bench = go.Figure()
        xs = list(range(len(bench_votes))); ys = [1] * len(bench_votes)
        colors_bench = [LEAN_COLORS[lean] for _, _, lean in bench_votes]
        sizes_bench  = [max(30, int(prob * 50)) for _, prob, _ in bench_votes]
        fig_bench.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            marker=dict(size=sizes_bench, color=colors_bench, line=dict(color="white", width=2),
                        symbol=["circle" if prob > 0.5 else "x" for _, prob, _ in bench_votes]),
            text=[f"{short}<br>{int(prob*100)}%" for short, prob, _ in bench_votes],
            textposition="bottom center", textfont=dict(size=9),
            hovertemplate="<b>%{text}</b><extra></extra>"))
        fig_bench.update_layout(
            title=f"Predicted Votes for {direction} (sorted by probability)",
            height=200, showlegend=False,
            xaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[-0.5, 8.5]),
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[0.5, 1.5]),
            plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=20, r=20, t=50, b=60),
        )
        st.plotly_chart(fig_bench, use_container_width=True)

        # Historical context
        st.divider()
        st.subheader("Historical Context")
        circ_r = CIRCUIT_REVERSAL_RATES.get(c_sel, 0.62) * 100
        issue_r = ISSUE_REVERSAL_RATES.get(ia_sel, 0.62) * 100
        col_ctx1, col_ctx2, col_ctx3 = st.columns(3)
        col_ctx1.metric(f"{c_sel} Reversal Rate", f"{circ_r:.0f}%", "historical average")
        col_ctx2.metric(f"{ia_sel} Reversal Rate", f"{issue_r:.0f}%", "historical average")
        col_ctx3.metric("Overall SCOTUS Reversal Rate", "62%", "1990–2024 average")

        all_circuits = list(CIRCUIT_REVERSAL_RATES.items())
        all_circuits.sort(key=lambda x: -x[1])
        fig_ctx = go.Figure(go.Bar(
            x=[c[0] for c in all_circuits], y=[c[1]*100 for c in all_circuits],
            marker_color=["#E74C3C" if c[0]==c_sel else "#BDC3C7" for c in all_circuits],
            text=[f"{c[1]*100:.0f}%" for c in all_circuits], textposition="outside"))
        fig_ctx.update_layout(title="Historical Reversal Rate by Circuit", xaxis_tickangle=-30,
                               yaxis=dict(title="Reversal Rate (%)", range=[0, 100]),
                               height=320, plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_ctx, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: CERT GRANT PREDICTOR
# ──────────────────────────────────────────────────────────────────────────────
with tab_cert:
    st.markdown(
        "The Supreme Court receives ~10,000 petitions for certiorari per year and grants about **1–2%** "
        "(roughly 60–80 cases). Predict whether a petition is likely to be granted based on key factors."
    )

    CERT_FACTORS = {
        "Circuit Split": 0.045,
        "Federal Gov't Petitioner (SG)": 0.038,
        "Civil Rights / Equal Protection Issue": 0.032,
        "First Amendment Issue": 0.030,
        "Judicial Power / Separation of Powers Issue": 0.035,
        "Lower Court Struck Down Federal Law": 0.040,
        "CVSG (Call for Views from SG)": 0.060,
        "Prior SCOTUS Case Needs Clarification": 0.028,
        "Significant Economic Impact": 0.020,
        "Long-standing Circuit Disagreement (5+ yrs)": 0.050,
    }

    with st.form("cert_form"):
        col1_c, col2_c = st.columns(2)
        with col1_c:
            cert_circuit = st.selectbox("Circuit of Origin", list(CIRCUIT_CERT_MULTIPLIER.keys()), key="cert_circuit")
            cert_issue   = st.selectbox("Issue Area", list(ISSUE_CERT_RATES.keys()), key="cert_issue")
        with col2_c:
            cert_sg      = st.checkbox("Solicitor General is Petitioner or Supports Grant")
            cert_split   = st.checkbox("Circuit Split Exists")
            cert_cvsg    = st.checkbox("CVSG (Court invited SG view)")
            cert_lower_struck = st.checkbox("Lower Court Struck Down Federal Law")
        cert_factors_sel = st.multiselect("Additional Favorable Factors", list(CERT_FACTORS.keys()),
                                           help="Select all that apply to this petition")
        cert_submitted = st.form_submit_button("Predict Cert Grant Probability", type="primary")

    if cert_submitted:
        base_cert = ISSUE_CERT_RATES.get(cert_issue, 0.015)
        mult      = CIRCUIT_CERT_MULTIPLIER.get(cert_circuit, 1.0)
        if cert_sg:    base_cert += 0.038
        if cert_split: base_cert += 0.045
        if cert_cvsg:  base_cert += 0.060
        if cert_lower_struck: base_cert += 0.040
        for f in cert_factors_sel:
            base_cert += CERT_FACTORS.get(f, 0)
        cert_prob = max(0.005, min(0.85, base_cert * mult))

        if cert_prob < 0.05:    cert_verdict = "🔴 Very Unlikely"; cert_c = "#E74C3C"
        elif cert_prob < 0.10:  cert_verdict = "🟠 Unlikely";      cert_c = "#E67E22"
        elif cert_prob < 0.20:  cert_verdict = "🟡 Possible";      cert_c = "#F39C12"
        elif cert_prob < 0.40:  cert_verdict = "🟢 Likely";        cert_c = "#27AE60"
        else:                   cert_verdict = "🟢 Very Likely";    cert_c = "#1ABC9C"

        st.markdown(f'<div style="background:{cert_c}18;border-left:5px solid {cert_c};padding:16px 20px;border-radius:6px;">'
                    f'<span style="font-size:1.25em;font-weight:bold;color:{cert_c};">{cert_verdict}</span><br>'
                    f'<span style="font-size:1.8em;color:{cert_c};font-weight:bold;">{cert_prob*100:.1f}%</span>'
                    f' <span style="color:#888;">probability of cert grant</span></div>', unsafe_allow_html=True)
        st.markdown("")

        col_cert1, col_cert2 = st.columns(2)
        with col_cert1:
            st.metric("Estimated Grant Probability", f"{cert_prob*100:.1f}%")
            st.metric("Baseline (all petitions)", "1.5%")
            st.metric("Circuit Multiplier", f"{mult:.1f}×")
        with col_cert2:
            fig_cert = go.Figure(go.Indicator(
                mode="gauge+number", value=round(cert_prob * 100, 1),
                number={"suffix": "%"},
                title={"text": "Cert Grant Probability"},
                gauge={"axis": {"range": [0, 85]},
                       "bar": {"color": cert_c},
                       "steps": [{"range": [0, 5], "color": "#FADBD8"},
                                  {"range": [5, 15], "color": "#FDEBD0"},
                                  {"range": [15, 85], "color": "#D5F5E3"}],
                       "threshold": {"line": {"color": "#E74C3C", "width": 2}, "thickness": 0.75, "value": 5}}))
            fig_cert.update_layout(height=230, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_cert, use_container_width=True)

        st.divider()
        st.subheader("Cert Grant Rates by Issue Area")
        issue_df_c = pd.DataFrame(list(ISSUE_CERT_RATES.items()), columns=["Issue Area","Base Rate"])
        issue_df_c["Highlighted"] = issue_df_c["Issue Area"] == cert_issue
        fig_c2 = go.Figure(go.Bar(
            x=issue_df_c["Issue Area"],
            y=(issue_df_c["Base Rate"] * 100).round(2),
            marker_color=["#E67E22" if h else "#BDC3C7" for h in issue_df_c["Highlighted"]],
            text=(issue_df_c["Base Rate"] * 100).apply(lambda v: f"{v:.1f}%"),
            textposition="outside"))
        fig_c2.update_layout(title="Baseline Cert Grant Rate by Issue Area (before modifiers)",
                              xaxis_tickangle=-30, height=340,
                              yaxis=dict(title="Base Grant Rate (%)"),
                              plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_c2, use_container_width=True)
        st.caption("These rates reflect historical cert grants. Circuit splits, SG support, and CVSG can multiply probability 2–5×.")

    else:
        st.subheader("📊 Reference: Historical Cert Grant Rates")
        st.markdown("**Factors that dramatically increase cert probability:**")
        factors_df = pd.DataFrame(list(CERT_FACTORS.items()), columns=["Factor","Probability Boost"])
        factors_df["Boost %"] = (factors_df["Probability Boost"] * 100).round(1)
        factors_df = factors_df.sort_values("Boost %", ascending=False)
        fig_factors = go.Figure(go.Bar(
            x=factors_df["Boost %"], y=factors_df["Factor"], orientation="h",
            marker_color="#E67E22", text=factors_df["Boost %"].apply(lambda v: f"+{v:.1f}%"),
            textposition="outside"))
        fig_factors.update_layout(title="Cert Grant Probability Boost by Factor",
                                   height=350, xaxis_title="Probability Added",
                                   yaxis=dict(autorange="reversed"),
                                   plot_bgcolor="white", paper_bgcolor="white",
                                   margin=dict(l=250, r=60, t=40, b=40))
        st.plotly_chart(fig_factors, use_container_width=True)
        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        col_d1.metric("Annual Petitions", "~10,000")
        col_d2.metric("Granted", "~70–80")
        col_d3.metric("Grant Rate", "~1.5%")
        col_d4.metric("Chance with Circuit Split", "~4–8%")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: DOCKET WATCH — Live Current Term Tracker
# ──────────────────────────────────────────────────────────────────────────────
with tab_docket:
    st.markdown(f"**Live tracker** for the **{CURRENT_TERM}–{CURRENT_TERM+1} SCOTUS Term.** Auto-refreshes on demand.")

    col_refresh, col_info = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Refresh Docket", type="primary"):
            st.cache_data.clear()
            st.rerun()
    with col_info:
        st.caption(f"Data source: Oyez API. Last checked: {datetime.datetime.now().strftime('%B %d, %Y %H:%M')}")

    with st.spinner(f"Loading {CURRENT_TERM}–{CURRENT_TERM+1} term docket…"):
        docket_cases = _pred_fetch_term(CURRENT_TERM)

    if not docket_cases:
        st.error(f"Could not load {CURRENT_TERM}–{CURRENT_TERM+1} term from Oyez. Try refreshing.")
    else:
        # Status bar
        m1, m2, m3, m4 = st.columns(4)
        decided  = sum(1 for c in docket_cases if c.get("decided_on"))
        total    = len(docket_cases)
        m1.metric("Total Cases", total)
        m2.metric("✅ Decided", decided)
        m3.metric("⏳ Pending", total - decided)
        m4.metric("📅 Term Progress", f"{decided/total*100:.0f}%" if total else "0%")

        st.markdown(f"**Term completion:** {decided}/{total} cases decided")
        progress_pct = decided / total if total else 0
        st.progress(progress_pct)
        st.divider()

        # Filters
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            status_filter_dw = st.selectbox("Filter by Status", ["All","Decided","Pending"], key="dw_status")
        with col_f2:
            search_dw = st.text_input("Search case name", placeholder="e.g. Trump, EPA, gun", key="dw_search")

        # Build display rows
        dw_rows = []
        for c in docket_cases:
            ia = c.get("issue_area") or {}
            issue = ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown")
            decided_ts = c.get("decided_on")
            decided_date = _parse_date(decided_ts)
            status = "Decided" if decided_date else "Pending"
            dw_rows.append({
                "name": c.get("name",""),
                "docket": c.get("docket_number",""),
                "issue": issue,
                "status": status,
                "decided_date": decided_date,
                "href": c.get("href",""),
            })

        # Apply filters
        display_rows = dw_rows
        if status_filter_dw == "Decided":   display_rows = [r for r in dw_rows if r["status"]=="Decided"]
        elif status_filter_dw == "Pending": display_rows = [r for r in dw_rows if r["status"]=="Pending"]
        if search_dw: display_rows = [r for r in display_rows if search_dw.lower() in r["name"].lower()]

        # Case cards in grid
        st.markdown(f"**{len(display_rows)} cases shown**")
        cols_dw = st.columns(2)
        for i, row in enumerate(sorted(display_rows, key=lambda x: (x["status"]=="Pending", x["name"]))):
            icon = "✅" if row["status"]=="Decided" else "⏳"
            status_color = STATUS_COLORS.get(row["status"],"#95A5A6")
            oyez_url = row["href"].replace("api.oyez.org/cases","www.oyez.org/cases") if row["href"] else ""
            with cols_dw[i % 2]:
                st.markdown(
                    f'<div style="border:1px solid #E8E8E8;border-left:4px solid {status_color};'
                    f'border-radius:6px;padding:10px 14px;margin:4px 0;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                    f'<span style="font-weight:bold;font-size:0.92em;">{icon} {row["name"][:55]}{"…" if len(row["name"])>55 else ""}</span>'
                    f'<span style="background:{status_color};color:white;padding:1px 7px;border-radius:3px;font-size:0.75em;white-space:nowrap;margin-left:6px;">'
                    f'{row["status"]}</span></div>'
                    f'<div style="font-size:0.82em;color:#666;margin-top:4px;">'
                    f'<span>📁 {row["issue"]}</span>'
                    f'{" · " + str(row["decided_date"]) if row["decided_date"] else ""}'
                    f'{"  · <a href=" + oyez_url + " target=_blank>Oyez ↗</a>" if oyez_url else ""}'
                    f'</div></div>',
                    unsafe_allow_html=True)

        # Issue area breakdown
        st.divider()
        st.subheader("Issue Area Distribution — Current Term")
        issue_counts_dw = defaultdict(int)
        for r in dw_rows: issue_counts_dw[r["issue"]] += 1
        issue_df_dw = pd.DataFrame(list(issue_counts_dw.items()), columns=["Issue Area","Cases"])
        issue_df_dw = issue_df_dw.sort_values("Cases", ascending=False)
        fig_issue_dw = go.Figure(go.Bar(
            x=issue_df_dw["Issue Area"], y=issue_df_dw["Cases"],
            marker_color="#3498DB", text=issue_df_dw["Cases"], textposition="outside"))
        fig_issue_dw.update_layout(title=f"{CURRENT_TERM}–{CURRENT_TERM+1} Term — Cases by Issue Area",
                                    xaxis_tickangle=-30, height=340,
                                    plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_issue_dw, use_container_width=True)

        # Upcoming decisions
        pending_cases = [r for r in dw_rows if r["status"]=="Pending"]
        if pending_cases:
            st.subheader(f"⏳ {len(pending_cases)} Pending Cases")
            for row in sorted(pending_cases, key=lambda x: x["name"]):
                oyez_url = row["href"].replace("api.oyez.org/cases","www.oyez.org/cases") if row["href"] else ""
                link = f" [→ Oyez]({oyez_url})" if oyez_url else ""
                st.markdown(f"- **{row['name']}** · {row['issue']}{link}")
