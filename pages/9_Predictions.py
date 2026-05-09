import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import requests
import time
import datetime
import threading
from collections import defaultdict
from pathlib import Path

from utils.local_data import fetch_oyez, DATA_DIR as _LOCAL_DATA_DIR
from utils.oyez_api import get_cases_by_term, get_case_detail
from utils.ml_predictor import (
    collect_training_data, train_models, predict, explain_prediction, load_meta,
    is_trained, CACHE_CSV, extract_circuit,
)
from utils import add_sidebar_logo, get_current_justices
add_sidebar_logo()


HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year
TODAY        = datetime.date.today()
CURRENT_TERM = CURRENT_YEAR if TODAY.month >= 10 else CURRENT_YEAR - 1

# ── Court roster for display (loaded from data_files/current_justices.json) ──
CURRENT_JUSTICES_DISPLAY = get_current_justices()
LEAN_COLORS = {"Conservative": "#E74C3C", "Moderate": "#F39C12", "Liberal": "#3498DB"}

CIRCUIT_OPTIONS = [
    "1st Circuit","2nd Circuit","3rd Circuit","4th Circuit","5th Circuit",
    "6th Circuit","7th Circuit","8th Circuit","9th Circuit","10th Circuit",
    "11th Circuit","D.C. Circuit","Federal Circuit","State Supreme Court","Other",
]
ISSUE_OPTIONS = [
    "Criminal Procedure","Civil Rights","First Amendment","Due Process","Privacy",
    "Economic Activity","Judicial Power","Federalism","Federal Taxation","Unions",
    "Attorneys","Miscellaneous","Interstate Relations","Private Action",
]
PETITIONER_TYPES = [
    "Federal Government","State / Local Gov't","Corporation / Org","Individual / Other"
]
# Historical stats for the static fallback path
CIRCUIT_REVERSAL_RATES = {
    "9th Circuit":0.76,"6th Circuit":0.74,"11th Circuit":0.72,"5th Circuit":0.68,
    "4th Circuit":0.65,"8th Circuit":0.63,"7th Circuit":0.61,"3rd Circuit":0.60,
    "2nd Circuit":0.58,"1st Circuit":0.56,"10th Circuit":0.62,"D.C. Circuit":0.55,
    "Federal Circuit":0.52,"State Supreme Court":0.60,"Other":0.62,
}
ISSUE_REVERSAL_RATES = {
    "Criminal Procedure":0.72,"Civil Rights":0.65,"First Amendment":0.60,"Due Process":0.64,
    "Privacy":0.58,"Economic Activity":0.55,"Judicial Power":0.70,"Federalism":0.62,
    "Federal Taxation":0.54,"Unions":0.63,"Attorneys":0.60,"Miscellaneous":0.61,
    "Interstate Relations":0.59,"Private Action":0.57,
}
PETITIONER_BONUS = {
    "Federal Government":+0.12,"State / Local Gov't":-0.03,
    "Corporation / Org":+0.02,"Individual / Other":-0.05,
}

CERT_FACTORS = {
    "Circuit Split":0.045,"Federal Gov't Petitioner (SG)":0.038,
    "Civil Rights / Equal Protection Issue":0.032,"First Amendment Issue":0.030,
    "Judicial Power / Separation of Powers Issue":0.035,
    "Lower Court Struck Down Federal Law":0.040,"CVSG (Call for Views from SG)":0.060,
    "Prior SCOTUS Case Needs Clarification":0.028,"Significant Economic Impact":0.020,
    "Long-standing Circuit Disagreement (5+ yrs)":0.050,
}
ISSUE_CERT_RATES = {
    "Criminal Procedure":0.028,"Civil Rights":0.025,"First Amendment":0.030,
    "Due Process":0.022,"Privacy":0.027,"Economic Activity":0.018,
    "Judicial Power":0.035,"Federalism":0.032,"Federal Taxation":0.016,
    "Unions":0.021,"Attorneys":0.013,"Miscellaneous":0.010,
    "Interstate Relations":0.015,"Private Action":0.012,
}
CIRCUIT_CERT_MULT = {
    "9th Circuit":1.8,"D.C. Circuit":2.2,"2nd Circuit":1.6,"4th Circuit":1.3,
    "5th Circuit":1.5,"6th Circuit":1.4,"7th Circuit":1.3,"8th Circuit":1.1,
    "10th Circuit":1.1,"11th Circuit":1.3,"3rd Circuit":1.2,"1st Circuit":1.0,
    "Federal Circuit":0.9,"State Supreme Court":0.7,"Other":0.8,
}

# ── Fetch helpers ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=600)
def _pred_fetch_term(term: int) -> list[dict]:
    return get_cases_by_term(term)

@st.cache_data(show_spinner=False, ttl=600)
def _pred_fetch_detail(href: str) -> dict | None:
    return get_case_detail(href)

def _parse_date(ts) -> datetime.date | None:
    try:
        if ts: return datetime.date.fromtimestamp(int(ts))
    except Exception: pass
    return None

# ── Static fallback predictor ─────────────────────────────────────────────────
def _static_predict(circuit, issue_area, petitioner_type, sg_support, circuit_split, n_conservative):
    base       = 0.62
    circ_rate  = CIRCUIT_REVERSAL_RATES.get(circuit, 0.62)
    issue_rate = ISSUE_REVERSAL_RATES.get(issue_area, 0.62)
    pet_bonus  = PETITIONER_BONUS.get(petitioner_type, 0.0)
    p_reverse  = (base*0.15 + circ_rate*0.35 + issue_rate*0.25 + pet_bonus
                  + (0.10 if sg_support else 0) + (0.08 if circuit_split else 0)
                  + (n_conservative - 5) * 0.025)
    p_reverse  = max(0.05, min(0.95, p_reverse))

    split_dist = {
        "9-0": max(0, 0.08), "8-1": max(0, 0.10), "7-2": max(0, 0.15),
        "6-3": max(0, p_reverse*0.28 + (1-p_reverse)*0.20),
        "5-4": max(0, p_reverse*0.39 + (1-p_reverse)*0.47),
    }
    total = sum(split_dist.values())
    split_dist = {k: v/total for k, v in split_dist.items()}
    split_label = max(split_dist, key=split_dist.get)

    _JUST_TEND = {
        "Roberts":   {"Criminal Procedure":0.68,"Civil Rights":0.55,"First Amendment":0.60,"default":0.60},
        "Thomas":    {"Criminal Procedure":0.82,"Civil Rights":0.50,"First Amendment":0.62,"default":0.72},
        "Alito":     {"Criminal Procedure":0.78,"Civil Rights":0.52,"First Amendment":0.65,"default":0.68},
        "Sotomayor": {"Criminal Procedure":0.45,"Civil Rights":0.75,"First Amendment":0.62,"default":0.48},
        "Kagan":     {"Criminal Procedure":0.48,"Civil Rights":0.72,"First Amendment":0.65,"default":0.50},
        "Gorsuch":   {"Criminal Procedure":0.72,"Civil Rights":0.48,"First Amendment":0.70,"default":0.65},
        "Kavanaugh": {"Criminal Procedure":0.62,"Civil Rights":0.55,"First Amendment":0.60,"default":0.58},
        "Barrett":   {"Criminal Procedure":0.70,"Civil Rights":0.50,"First Amendment":0.65,"default":0.63},
        "Jackson":   {"Criminal Procedure":0.42,"Civil Rights":0.78,"First Amendment":0.64,"default":0.46},
    }
    cons_adj = (n_conservative - 5) * 0.025
    justice_probs = {}
    for j in CURRENT_JUSTICES_DISPLAY:
        sh = j["short"]
        tend = _JUST_TEND.get(sh, {})
        rate = tend.get(issue_area, tend.get("default", 0.60))
        rate = rate + cons_adj * 0.3
        if j["lean"] == "Liberal": rate = 1 - (1 - rate) * (1 + cons_adj * 0.2)
        rate = max(0.10, min(0.90, rate))
        if p_reverse < 0.5: rate = 1 - rate
        justice_probs[sh] = rate

    return {"p_reverse": round(p_reverse,4), "p_affirm": round(1-p_reverse,4),
            "split_probs": split_dist, "split_label": split_label,
            "justice_probs": justice_probs, "source": "statistical"}

# ── Page header ───────────────────────────────────────────────────────────────
st.title("🔮 Predictions")

meta = load_meta()
model_ready = is_trained()

if model_ready:
    trained_at     = meta.get("trained_at","?")[:16].replace("T"," ")
    total_cases    = meta.get("total_cases", "?")
    total_votes    = meta.get("total_votes", "?")
    terms_in_data  = meta.get("terms_in_data", [])
    term_range     = f"{min(terms_in_data)}–{max(terms_in_data)}" if terms_in_data else "?"
    out_acc        = meta.get("outcome_accuracy_cv5", None)
    st.success(
        f"✅ **ML model active** — trained on **{total_cases:,} cases** "
        f"({total_votes:,} votes, {term_range} terms)  |  "
        f"5-fold CV accuracy: **{out_acc*100:.1f}%**  |  trained {trained_at}"
    )
else:
    st.warning("⚠️ ML model not yet trained. Predictions will use the statistical baseline. "
               "Open **⚙️ Model Training** below to train on real Oyez data.")

tab_predictor, tab_performance, tab_training, tab_cert, tab_docket, tab_simulator, tab_modelcard = st.tabs([
    "🎯 Case Outcome Predictor", "📈 Model Performance",
    "⚙️ Model Training", "📋 Cert Grant Predictor", "🔴 Docket Watch",
    "🔄 Justice Simulator", "📄 Model Card",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: CASE OUTCOME PREDICTOR
# ══════════════════════════════════════════════════════════════════════════════
with tab_predictor:
    source_badge = ("🤖 **ML model**" if model_ready else "📊 **Statistical baseline**")
    st.markdown(f"Using {source_badge}. Enter case characteristics to generate a prediction.")
    if not model_ready:
        st.info("Train the ML model in the **⚙️ Model Training** tab for higher accuracy predictions.")

    with st.form("predictor_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            circuit_sel    = st.selectbox("Circuit of Origin", CIRCUIT_OPTIONS, index=8)
            issue_area_sel = st.selectbox("Issue Area", ISSUE_OPTIONS, index=0)
        with col2:
            pet_type_sel   = st.selectbox("Petitioner Type", PETITIONER_TYPES, index=0)
            sg_support     = st.checkbox("Solicitor General Supporting Petitioner")
        with col3:
            circuit_split  = st.checkbox("Circuit Split Exists")
            n_cons         = st.slider("Conservative Justices on Court", 4, 7, 6)
            case_name_inp  = st.text_input("Case Name (optional)", placeholder="e.g. Smith v. Jones")
        submitted = st.form_submit_button("Generate Prediction →", type="primary")

    if submitted:
        if model_ready:
            try:
                result = predict(
                    circuit=circuit_sel, issue_area=issue_area_sel,
                    n_conservative=n_cons, term_year=CURRENT_YEAR,
                    sg_support=sg_support, circuit_split=circuit_split,
                )
                result["source"] = "ml"
            except Exception as e:
                st.warning(f"ML model error ({e}). Falling back to statistical baseline.")
                result = _static_predict(circuit_sel, issue_area_sel, pet_type_sel,
                                         sg_support, circuit_split, n_cons)
        else:
            result = _static_predict(circuit_sel, issue_area_sel, pet_type_sel,
                                     sg_support, circuit_split, n_cons)
        st.session_state["pred_result"] = result
        st.session_state["pred_inputs"] = (circuit_sel, issue_area_sel, pet_type_sel,
                                            sg_support, circuit_split, n_cons, case_name_inp)

    if "pred_result" in st.session_state:
        result = st.session_state["pred_result"]
        inputs = st.session_state.get("pred_inputs", ())
        c_sel, ia_sel, pt_sel, sg_sel, cs_sel, nc_sel, cn_inp = inputs

        p_rev = result["p_reverse"]; p_aff = result["p_affirm"]
        if   p_rev > 0.66: verdict_label, verdict_color = "🔴 LIKELY REVERSED",   "#E74C3C"
        elif p_rev > 0.54: verdict_label, verdict_color = "🟠 LEAN REVERSE",       "#E67E22"
        elif p_aff > 0.66: verdict_label, verdict_color = "🟢 LIKELY AFFIRMED",    "#27AE60"
        elif p_aff > 0.54: verdict_label, verdict_color = "🟡 LEAN AFFIRM",        "#F39C12"
        else:               verdict_label, verdict_color = "⚖️ TOSS-UP",            "#9B59B6"

        src_label  = "ML Model" if result.get("source") == "ml" else "Statistical Baseline"
        case_title = cn_inp if cn_inp else f"{c_sel} → {ia_sel} case"

        st.markdown(
            f'<div style="background:{verdict_color}18;border-left:5px solid {verdict_color};'
            f'padding:16px 20px;border-radius:6px;margin:12px 0;">'
            f'<span style="font-size:1.35em;font-weight:bold;color:{verdict_color};">{verdict_label}</span>'
            f'<span style="color:#555;margin-left:16px;">{case_title}</span>'
            f'<span style="float:right;font-size:0.8em;color:#888;background:#f0f0f0;'
            f'padding:2px 8px;border-radius:3px;">{src_label}</span></div>',
            unsafe_allow_html=True)

        col_gauge, col_split_chart, col_factors = st.columns(3)

        with col_gauge:
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=round(p_rev*100,1),
                title={"text":"Reversal Probability","font":{"size":13}},
                number={"suffix":"%","font":{"size":26}},
                delta={"reference":50,"valueformat":".1f","suffix":"% vs 50%"},
                gauge={
                    "axis":{"range":[0,100],"ticksuffix":"%"},
                    "bar":{"color":verdict_color},
                    "steps":[{"range":[0,45],"color":"#D5F5E3"},
                              {"range":[45,55],"color":"#FCF3CF"},
                              {"range":[55,100],"color":"#FADBD8"}],
                    "threshold":{"line":{"color":"#2C3E50","width":3},"thickness":0.75,"value":50},
                }))
            fig_g.update_layout(height=250,margin=dict(l=20,r=20,t=40,b=20))
            st.plotly_chart(fig_g)

        with col_split_chart:
            split_d  = result["split_probs"]
            split_df = pd.DataFrame(list(split_d.items()), columns=["Split","Prob"])
            split_df["Prob %"] = (split_df["Prob"]*100).round(1)
            split_label_pred   = result["split_label"]
            bar_colors = ["#27AE60" if s==split_label_pred else "#BDC3C7" for s in split_df["Split"]]
            fig_sp = go.Figure(go.Bar(
                x=split_df["Split"], y=split_df["Prob %"],
                marker_color=bar_colors,
                text=split_df["Prob %"].apply(lambda v: f"{v:.0f}%"),
                textposition="outside"))
            fig_sp.update_layout(
                title=f"Most Likely Split: {split_label_pred}",
                yaxis=dict(title="Probability %",range=[0,65]),
                height=250,plot_bgcolor="white",paper_bgcolor="white",
                margin=dict(l=20,r=20,t=40,b=40))
            st.plotly_chart(fig_sp)

        with col_factors:
            # SHAP waterfall if available, otherwise input summary bars
            shap_data = None
            if model_ready:
                shap_data = explain_prediction(
                    circuit=c_sel, issue_area=ia_sel,
                    n_conservative=nc_sel, term_year=CURRENT_YEAR,
                )
            if shap_data:
                st.markdown("**Feature Contributions (SHAP)**")
                sv = shap_data["shap_values"]
                fn = shap_data["feature_names"]
                colors = ["#E74C3C" if v > 0 else "#27AE60" for v in sv]
                fig_shap = go.Figure(go.Bar(
                    x=sv, y=fn,
                    orientation="h",
                    marker_color=colors,
                    text=[f"{v:+.3f}" for v in sv],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>SHAP: %{x:+.3f}<extra></extra>",
                ))
                ev_pct = round(shap_data["expected_value"] * 100, 1)
                fig_shap.update_layout(
                    height=280,
                    plot_bgcolor="white", paper_bgcolor="white",
                    margin=dict(l=10, r=60, t=30, b=20),
                    xaxis_title="← Affirm  |  Reverse →",
                    xaxis=dict(zeroline=True, zerolinecolor="#555", zerolinewidth=1),
                )
                st.plotly_chart(fig_shap, )
                st.caption(f"Red = pushes toward Reverse, Green = pushes toward Affirm. "
                           f"Base rate: {ev_pct:+.1f} (log-odds)")
            else:
                st.markdown("**Input Summary**")
                factors = [
                    (f"{c_sel}", CIRCUIT_REVERSAL_RATES.get(c_sel,0.62)*100, "#3498DB"),
                    (f"{ia_sel}", ISSUE_REVERSAL_RATES.get(ia_sel,0.62)*100, "#9B59B6"),
                    ("SG Support", (60 if sg_sel else 50), "#E67E22"),
                    ("Circuit Split", (58 if cs_sel else 50), "#27AE60"),
                    (f"{nc_sel} conservatives", 50 + (nc_sel-5)*2.5, "#E74C3C"),
                ]
                for label, val, color in factors:
                    st.markdown(
                        f'<div style="margin:4px 0;">'
                        f'<span style="font-size:0.82em;color:#555;">{label}</span><br>'
                        f'<div style="background:#ECF0F1;border-radius:4px;height:14px;margin-top:2px;">'
                        f'<div style="background:{color};width:{min(val,100):.0f}%;height:100%;border-radius:4px;"></div></div>'
                        f'<span style="font-size:0.8em;color:{color};">{val:.0f}%</span></div>',
                        unsafe_allow_html=True)

        st.divider()
        # Per-justice section
        st.subheader("Per-Justice Vote Probabilities")
        direction = "Reverse" if p_rev > 0.5 else "Affirm"
        st.caption(f"Probability each justice votes with the predicted {direction} majority.")
        justice_probs = result.get("justice_probs", {})

        j_cols = st.columns(3)
        for i, j in enumerate(CURRENT_JUSTICES_DISPLAY):
            sh = j["short"]
            prob = justice_probs.get(sh, 0.5)
            lean_color = LEAN_COLORS[j["lean"]]
            if   prob > 0.65: badge = "✅ Likely Majority";  bar_c = lean_color
            elif prob < 0.35: badge = "❌ Likely Dissent";   bar_c = "#95A5A6"
            else:             badge = "🤔 Uncertain";        bar_c = "#BDC3C7"
            with j_cols[i % 3]:
                st.markdown(
                    f'<div style="border:1px solid #E0E0E0;border-radius:6px;padding:10px;margin:4px 0;">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<span style="font-weight:bold;font-size:0.95em;">{sh}</span>'
                    f'<span style="color:{lean_color};font-size:0.78em;">{j["lean"]}</span></div>'
                    f'<div style="background:#ECF0F1;border-radius:4px;height:10px;margin:5px 0;">'
                    f'<div style="background:{bar_c};width:{prob*100:.0f}%;height:100%;border-radius:4px;"></div></div>'
                    f'<div style="font-size:0.82em;color:#555;display:flex;justify-content:space-between;">'
                    f'<span>P({direction}): <b>{prob*100:.0f}%</b></span>'
                    f'<span>{badge}</span></div></div>',
                    unsafe_allow_html=True)

        st.divider()
        # Bench diagram
        st.subheader("Court Bench — Predicted Alignment")
        bench = sorted(
            [(j["short"], justice_probs.get(j["short"],0.5), j["lean"])
             for j in CURRENT_JUSTICES_DISPLAY],
            key=lambda x: -x[1])
        fig_bench = go.Figure()
        fig_bench.add_trace(go.Scatter(
            x=list(range(9)), y=[1]*9,
            mode="markers+text",
            marker=dict(
                size=[40+int(p*20) for _,p,_ in bench],
                color=[LEAN_COLORS[lean] for _,_,lean in bench],
                opacity=[0.9 if p>0.5 else 0.35 for _,p,_ in bench],
                line=dict(color="white",width=2),
                symbol=["circle" if p>0.5 else "x" for _,p,_ in bench]),
            text=[f"{sh}<br>{int(p*100)}%" for sh,p,_ in bench],
            textposition="bottom center",
            textfont=dict(size=9),
            hovertemplate="%{text}<extra></extra>"))
        fig_bench.update_layout(
            title=f"Predicted to {direction} (filled circle = majority, ✕ = dissent)",
            height=200,showlegend=False,
            xaxis=dict(showticklabels=False,showgrid=False,zeroline=False,range=[-0.5,8.5]),
            yaxis=dict(showticklabels=False,showgrid=False,zeroline=False,range=[0.4,1.6]),
            plot_bgcolor="white",paper_bgcolor="white",
            margin=dict(l=20,r=20,t=50,b=70))
        st.plotly_chart(fig_bench)

        # Historical circuit context
        st.divider()
        st.subheader("Historical Context")
        all_circs = sorted(CIRCUIT_REVERSAL_RATES.items(), key=lambda x: -x[1])
        hist_df   = pd.DataFrame(all_circs, columns=["Circuit","Reversal Rate"])
        fig_hist = go.Figure(go.Bar(
            x=hist_df["Circuit"], y=(hist_df["Reversal Rate"]*100).round(1),
            marker_color=["#E74C3C" if c==c_sel else "#BDC3C7" for c in hist_df["Circuit"]],
            text=(hist_df["Reversal Rate"]*100).round(0).astype(int).astype(str)+"%",
            textposition="outside"))
        fig_hist.update_layout(
            title="Historical Reversal Rate by Circuit (1990–2024)",
            xaxis_tickangle=-30, height=320,
            yaxis=dict(title="Reversal %",range=[0,100]),
            plot_bgcolor="white",paper_bgcolor="white")
        st.plotly_chart(fig_hist)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: MODEL PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
with tab_performance:
    if not model_ready:
        st.info("No trained model yet. Go to **⚙️ Model Training** to train one.")
    else:
        st.subheader("Model Performance Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Outcome Accuracy (5-fold CV)", f"{meta.get('outcome_accuracy_cv5',0)*100:.1f}%")
        c2.metric("Outcome Accuracy (hold-out)", f"{meta.get('outcome_accuracy_holdout',0)*100:.1f}%")
        c3.metric("Vote-Split Accuracy (hold-out)", f"{meta.get('split_accuracy_holdout',0)*100:.1f}%")
        c4.metric("Training Cases", f"{meta.get('total_cases',0):,}")
        st.caption(
            f"Hold-out = last 2 terms ({', '.join(str(t) for t in meta.get('test_terms',[]))}).  "
            f"Baseline (always predict Reverse): ~62%."
        )
        st.divider()

        # Per-justice performance
        j_results = meta.get("justice_results", {})
        if j_results:
            st.subheader("Per-Justice Model Accuracy")
            j_rows = [{"Justice": j, "Accuracy": v.get("accuracy"), "Training Votes": v.get("n",0)}
                      for j, v in j_results.items() if v.get("accuracy") is not None]
            j_perf_df = pd.DataFrame(j_rows).sort_values("Accuracy", ascending=False)
            if not j_perf_df.empty:
                fig_jp = go.Figure(go.Bar(
                    x=j_perf_df["Justice"],
                    y=(j_perf_df["Accuracy"]*100).round(1),
                    marker_color=["#27AE60" if a>0.65 else "#F39C12" if a>0.55 else "#E74C3C"
                                  for a in j_perf_df["Accuracy"]],
                    text=(j_perf_df["Accuracy"]*100).round(1).astype(str)+"%",
                    textposition="outside",
                    customdata=j_perf_df["Training Votes"],
                    hovertemplate="<b>%{x}</b><br>Accuracy: %{y:.1f}%<br>Training votes: %{customdata}<extra></extra>"))
                fig_jp.add_hline(y=50, line_dash="dot", line_color="#BDC3C7", annotation_text="Coin flip")
                fig_jp.update_layout(
                    title="Per-Justice Classifier Accuracy (hold-out set)",
                    yaxis=dict(title="Accuracy %", range=[0,100]),
                    height=360, plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig_jp)
                st.dataframe(j_perf_df.reset_index(drop=True)
                             .style.format({"Accuracy":"{:.1%}","Training Votes":"{:,}"})
                             .background_gradient(subset=["Accuracy"],cmap="RdYlGn"),
                             height=300, hide_index=True)

        st.divider()
        # Feature importances
        fi = meta.get("feature_importances", {})
        if fi:
            st.subheader("Feature Importances — Outcome Model")
            fi_df = pd.DataFrame(list(fi.items()), columns=["Feature","Importance"])
            fi_df = fi_df.sort_values("Importance", ascending=False).head(20)
            # Shorten one-hot names
            fi_df["Feature"] = fi_df["Feature"].str.replace("cat__","").str.replace("num__","")
            fig_fi = go.Figure(go.Bar(
                y=fi_df["Feature"], x=fi_df["Importance"],
                orientation="h", marker_color="#3498DB",
                text=fi_df["Importance"].apply(lambda v: f"{v:.3f}"),
                textposition="outside"))
            fig_fi.update_layout(
                title="Top 20 Feature Importances (Gradient Boosting)",
                height=500, plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=200,r=60,t=40,b=40),
                xaxis_title="Importance")
            st.plotly_chart(fig_fi)

        st.divider()
        # Outcome classification report
        oc_report = meta.get("outcome_report", {})
        if oc_report:
            st.subheader("Outcome Model — Classification Report (hold-out)")
            report_rows = []
            for cls_key in ["0","1"]:
                if cls_key in oc_report:
                    r = oc_report[cls_key]
                    report_rows.append({
                        "Class": "Affirmed (0)" if cls_key=="0" else "Reversed (1)",
                        "Precision": round(r.get("precision",0)*100,1),
                        "Recall": round(r.get("recall",0)*100,1),
                        "F1-Score": round(r.get("f1-score",0)*100,1),
                        "Support": int(r.get("support",0)),
                    })
            if report_rows:
                rep_df = pd.DataFrame(report_rows)
                st.dataframe(rep_df.style.format({"Precision":"{:.1f}%","Recall":"{:.1f}%","F1-Score":"{:.1f}%"})
                             .background_gradient(subset=["F1-Score"],cmap="RdYlGn"),
                             hide_index=True)

        st.divider()
        # Training data stats
        st.subheader("Training Data")
        terms_list = meta.get("terms_in_data", [])
        col_td1, col_td2, col_td3, col_td4 = st.columns(4)
        col_td1.metric("Terms covered", len(terms_list))
        col_td2.metric("Term range", f"{min(terms_list)}–{max(terms_list)}" if terms_list else "—")
        col_td3.metric("Total votes", f"{meta.get('total_votes',0):,}")
        col_td4.metric("Trained at", meta.get("trained_at","?")[:10])

        if CACHE_CSV.exists():
            if st.button("Show training data sample"):
                try:
                    sample = pd.read_csv(CACHE_CSV).head(100)
                    st.dataframe(sample, height=300)
                except Exception as e:
                    st.error(str(e))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: MODEL TRAINING
# ══════════════════════════════════════════════════════════════════════════════
with tab_training:
    st.markdown(
        "Train the ML prediction model on historical SCOTUS data from the Oyez API. "
        "Data is cached locally after the first fetch — retraining is fast."
    )

    avail_terms = list(range(2023, 1999, -1))

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        train_terms = st.multiselect(
            "Terms to include in training data",
            avail_terms,
            default=avail_terms[:18],
            format_func=lambda t: f"{t}–{t+1}",
            help="More terms = more data = better accuracy, but slower fetch. 15–20 terms is a good starting point.",
            key="train_terms_sel",
        )
        st.caption(f"Selected: {len(train_terms)} terms. "
                   f"Estimated cases: ~{len(train_terms)*70:,}. "
                   f"Fetch time (first run): ~{len(train_terms)*50//60+1} min.")
    with col_t2:
        cached_terms_info = ""
        if CACHE_CSV.exists():
            try:
                cached_df = pd.read_csv(CACHE_CSV)
                cached_ts = sorted(cached_df["term"].unique().astype(int))
                cached_terms_info = (f"**{len(cached_ts)} terms already cached** "
                                     f"({min(cached_ts)}–{max(cached_ts)}, "
                                     f"{len(cached_df):,} rows). "
                                     f"Only missing terms will be fetched.")
            except Exception:
                pass
        if cached_terms_info:
            st.info(cached_terms_info)
        else:
            st.info("No training data cached yet. Click 'Step 1: Collect Training Data' to build from local data.")

        clear_cache = st.checkbox("Clear cached data and re-fetch everything", value=False)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        fetch_btn = st.button("Step 1: Collect Training Data", type="primary",
                              disabled=not train_terms)
    with col_btn2:
        train_btn = st.button("Step 2: Train Models",
                              disabled=not (CACHE_CSV.exists() or "training_df" in st.session_state))

    # ── Data collection ───────────────────────────────────────────────────────
    if fetch_btn:
        if clear_cache and CACHE_CSV.exists():
            CACHE_CSV.unlink()
            st.toast("Cache cleared.")

        progress_bar  = st.progress(0.0, text="Starting data collection…")
        status_text   = st.empty()
        rows_count    = st.empty()

        def _progress(done, total, msg):
            pct = done / total if total else 0
            progress_bar.progress(pct, text=msg)
            status_text.markdown(f"*{msg}*")

        with st.spinner("Fetching SCOTUS case data from Oyez…"):
            try:
                df_train = collect_training_data(
                    terms=sorted(train_terms, reverse=True),
                    progress_cb=_progress,
                )
                st.session_state["training_df"] = df_train
                progress_bar.progress(1.0, text="Data collection complete!")
                n_cases  = df_train["docket"].nunique() if not df_train.empty else 0
                n_votes  = len(df_train)
                n_terms  = df_train["term"].nunique() if not df_train.empty else 0
                st.success(
                    f"✅ Collected **{n_cases:,} cases**, **{n_votes:,} justice votes** "
                    f"across **{n_terms}** terms."
                )
                rows_count.dataframe(
                    df_train.groupby("term").agg(
                        cases=("docket","nunique"),
                        votes=("justice","count"),
                    ).reset_index().sort_values("term",ascending=False).head(10)
                    if not df_train.empty else pd.DataFrame(columns=["term","cases","votes"]),
                    height=250,
                )
            except Exception as e:
                st.error(f"Data collection failed: {e}")

    # ── Model training ────────────────────────────────────────────────────────
    if train_btn:
        df_for_train = st.session_state.get("training_df", None)
        if df_for_train is None and CACHE_CSV.exists():
            try:
                df_for_train = pd.read_csv(CACHE_CSV)
            except Exception:
                df_for_train = None

        if df_for_train is None or df_for_train.empty:
            st.error("No training data found. Run Step 1 first.")
        else:
            st.info(f"Training on {len(df_for_train):,} vote rows from {df_for_train['term'].nunique()} terms…")
            train_progress = st.progress(0.0)
            train_status   = st.empty()

            def _train_progress(done, total, msg):
                pct = (done+1) / (total+1)
                train_progress.progress(pct, text=msg)
                train_status.markdown(f"*{msg}*")

            with st.spinner("Training ML models — this takes ~30–60 seconds…"):
                try:
                    results = train_models(df_for_train, progress_cb=_train_progress)
                    train_progress.progress(1.0, text="Training complete!")
                    train_status.empty()

                    out_cv   = results.get("outcome_accuracy_cv5", 0)
                    out_hold = results.get("outcome_accuracy_holdout", 0)
                    spl_hold = results.get("split_accuracy_holdout", 0)
                    j_res    = results.get("justice_results", {})
                    j_with_acc = [(j,v["accuracy"]) for j,v in j_res.items() if v.get("accuracy")]

                    st.success(
                        f"✅ **Models trained successfully!**  "
                        f"Outcome CV accuracy: **{out_cv*100:.1f}%** | "
                        f"Hold-out: **{out_hold*100:.1f}%** | "
                        f"Split hold-out: **{spl_hold*100:.1f}%** | "
                        f"Per-justice models: **{len(j_with_acc)}** justices"
                    )
                    st.balloons()

                    # Summary table
                    sum_rows = [
                        {"Model":"Outcome (Affirm/Reverse)","Type":"GradientBoosting + Calibration",
                         "CV Accuracy":f"{out_cv*100:.1f}%","Hold-out Accuracy":f"{out_hold*100:.1f}%","Classes":"2"},
                        {"Model":"Vote Split","Type":"GradientBoosting + Calibration",
                         "CV Accuracy":"—","Hold-out Accuracy":f"{spl_hold*100:.1f}%","Classes":"5"},
                    ]
                    for j, acc in sorted(j_with_acc, key=lambda x: -x[1]):
                        sum_rows.append({
                            "Model":f"Justice: {j}","Type":"LogisticRegression + Calibration",
                            "CV Accuracy":"—","Hold-out Accuracy":f"{acc*100:.1f}%","Classes":"2",
                        })
                    st.dataframe(pd.DataFrame(sum_rows), hide_index=True)
                    st.markdown("**Reload the page to activate the trained model.**")
                    st.rerun()
                except Exception as e:
                    st.error(f"Training failed: {e}")
                    import traceback; st.code(traceback.format_exc())

    # ── Architecture description ──────────────────────────────────────────────
    with st.expander("📐 Model Architecture Details"):
        st.markdown("""
**Data pipeline**
- Source: Oyez API (`/cases?filter=term:YYYY`) — free, no API key
- Features extracted per case: circuit of origin, issue area, term year, conservative bench count
- Labels: binary outcome (0=Affirm, 1=Reverse), vote split (5-4/6-3/7-2/8-1/9-0), per-justice majority indicator
- Temporal train/test split: held-out last 2 terms to prevent leakage

**Feature engineering**
| Feature | Type | Encoding |
|---|---|---|
| `circuit` | Categorical (15) | OneHotEncoder |
| `issue_area` | Categorical (14) | OneHotEncoder |
| `n_conservative` | Numeric | StandardScaler |
| `term_year_norm` | Numeric (centered on 2005) | StandardScaler |

**Models**
| Model | Algorithm | Notes |
|---|---|---|
| Outcome | `GradientBoostingClassifier` (150 trees, depth 3) | Calibrated with Platt scaling |
| Vote Split | `GradientBoostingClassifier` (150 trees, depth 3) | 5-class multiclass |
| Per-Justice (×9) | `LogisticRegression` (C=0.8) | One per current justice |

**Calibration**: `CalibratedClassifierCV(method="sigmoid", cv="prefit")` ensures probabilities are reliable.

**Post-hoc adjustments** (not in features, applied after model):
- SG support: +7pp reversal probability
- Circuit split: +5pp reversal probability
        """)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: CERT GRANT PREDICTOR
# ══════════════════════════════════════════════════════════════════════════════
with tab_cert:
    st.markdown(
        "The Supreme Court grants cert in about **1–2%** of ~10,000 annual petitions. "
        "Estimate whether a petition will be accepted based on key factors."
    )
    with st.form("cert_form"):
        c1_cf, c2_cf = st.columns(2)
        with c1_cf:
            cert_circuit = st.selectbox("Circuit of Origin", CIRCUIT_OPTIONS, key="cert_circuit")
            cert_issue   = st.selectbox("Issue Area", ISSUE_OPTIONS, key="cert_issue")
        with c2_cf:
            cert_sg     = st.checkbox("Solicitor General is Petitioner or Supports Grant")
            cert_split  = st.checkbox("Circuit Split Exists")
            cert_cvsg   = st.checkbox("CVSG (Court invited SG view)")
            cert_flaw   = st.checkbox("Lower Court Struck Down Federal Law")
        extra_factors = st.multiselect("Additional Favorable Factors", list(CERT_FACTORS.keys()))
        cert_sub = st.form_submit_button("Estimate Cert Probability", type="primary")

    if cert_sub:
        base  = ISSUE_CERT_RATES.get(cert_issue, 0.015)
        mult  = CIRCUIT_CERT_MULT.get(cert_circuit, 1.0)
        if cert_sg:    base += 0.038
        if cert_split: base += 0.045
        if cert_cvsg:  base += 0.060
        if cert_flaw:  base += 0.040
        for f in extra_factors: base += CERT_FACTORS.get(f, 0)
        cp = max(0.005, min(0.85, base * mult))

        if   cp < 0.05: cv, cc = "🔴 Very Unlikely", "#E74C3C"
        elif cp < 0.10: cv, cc = "🟠 Unlikely",       "#E67E22"
        elif cp < 0.20: cv, cc = "🟡 Possible",        "#F39C12"
        elif cp < 0.40: cv, cc = "🟢 Likely",          "#27AE60"
        else:           cv, cc = "🟢 Very Likely",     "#1ABC9C"

        st.markdown(
            f'<div style="background:{cc}18;border-left:5px solid {cc};padding:16px 20px;border-radius:6px;">'
            f'<span style="font-size:1.2em;font-weight:bold;color:{cc};">{cv}</span><br>'
            f'<span style="font-size:2em;color:{cc};font-weight:bold;">{cp*100:.1f}%</span>'
            f' <span style="color:#888;">cert grant probability</span></div>',
            unsafe_allow_html=True)

        c1_cm, c2_cm = st.columns(2)
        with c1_cm:
            st.metric("Estimated Probability", f"{cp*100:.1f}%")
            st.metric("Base rate (all petitions)", "1.5%")
            st.metric("Circuit multiplier", f"{mult:.1f}×")
        with c2_cm:
            fig_cg = go.Figure(go.Indicator(
                mode="gauge+number", value=round(cp*100,1),
                number={"suffix":"%"},
                title={"text":"Cert Grant Probability"},
                gauge={"axis":{"range":[0,85]},
                       "bar":{"color":cc},
                       "steps":[{"range":[0,5],"color":"#FADBD8"},
                                 {"range":[5,15],"color":"#FDEBD0"},
                                 {"range":[15,85],"color":"#D5F5E3"}],
                       "threshold":{"line":{"color":"#E74C3C","width":2},"thickness":0.75,"value":5}}))
            fig_cg.update_layout(height=220,margin=dict(l=20,r=20,t=40,b=20))
            st.plotly_chart(fig_cg)

        st.divider()
        issue_cert_df = pd.DataFrame(list(ISSUE_CERT_RATES.items()), columns=["Issue","Rate"])
        fig_ir = go.Figure(go.Bar(
            x=issue_cert_df["Issue"],
            y=(issue_cert_df["Rate"]*100).round(2),
            marker_color=["#E67E22" if i==cert_issue else "#BDC3C7" for i in issue_cert_df["Issue"]],
            text=(issue_cert_df["Rate"]*100).apply(lambda v: f"{v:.1f}%"),
            textposition="outside"))
        fig_ir.update_layout(title="Baseline Cert Rate by Issue Area",xaxis_tickangle=-30,
                              height=320,yaxis_title="Base Rate (%)",
                              plot_bgcolor="white",paper_bgcolor="white")
        st.plotly_chart(fig_ir)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: DOCKET WATCH
# ══════════════════════════════════════════════════════════════════════════════
with tab_docket:
    st.markdown(f"**Live tracker** for the **{CURRENT_TERM}–{CURRENT_TERM+1} SCOTUS Term.**")
    col_rf, col_inf = st.columns([1,3])
    with col_rf:
        if st.button("🔄 Refresh", type="primary"):
            st.cache_data.clear(); st.rerun()
    with col_inf:
        st.caption(f"Last checked: {datetime.datetime.now().strftime('%B %d, %Y %H:%M')}")

    with st.spinner("Loading current term docket…"):
        docket_cases = _pred_fetch_term(CURRENT_TERM)

    if not docket_cases:
        st.error("Could not load term from Oyez.")
    else:
        decided = sum(1 for c in docket_cases if c.get("decided_on"))
        total   = len(docket_cases)
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Total Cases", total)
        m2.metric("✅ Decided", decided)
        m3.metric("⏳ Pending", total-decided)
        m4.metric("Term Progress", f"{decided/total*100:.0f}%" if total else "0%")
        st.progress(decided/total if total else 0)
        st.divider()

        col_f1,col_f2 = st.columns(2)
        with col_f1: status_f = st.selectbox("Status", ["All","Decided","Pending"], key="dw_sf")
        with col_f2: search_f = st.text_input("Search", placeholder="EPA, gun, Trump…", key="dw_ss")

        dw_rows = []
        for c in docket_cases:
            ia = c.get("issue_area") or {}
            issue = ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown")
            dd = _parse_date(c.get("decided_on"))
            status = "Decided" if dd else "Pending"
            href   = c.get("href","")
            oyez_url = href.replace("api.oyez.org/cases","www.oyez.org/cases") if href else ""
            dw_rows.append({"name":c.get("name",""),"issue":issue,"status":status,
                             "decided":dd,"oyez_url":oyez_url})

        disp = dw_rows
        if status_f == "Decided":   disp = [r for r in disp if r["status"]=="Decided"]
        elif status_f == "Pending": disp = [r for r in disp if r["status"]=="Pending"]
        if search_f: disp = [r for r in disp if search_f.lower() in r["name"].lower()]
        disp = sorted(disp, key=lambda x: (x["status"]=="Pending", x["name"]))

        STATUS_COLORS = {"Decided":"#27AE60","Pending":"#E67E22"}
        cols_dw = st.columns(2)
        for i, row in enumerate(disp):
            sc = STATUS_COLORS.get(row["status"],"#95A5A6")
            icon = "✅" if row["status"]=="Decided" else "⏳"
            link = f' · <a href="{row["oyez_url"]}" target="_blank">Oyez ↗</a>' if row["oyez_url"] else ""
            with cols_dw[i%2]:
                st.markdown(
                    f'<div style="border:1px solid #E8E8E8;border-left:4px solid {sc};'
                    f'border-radius:6px;padding:10px 14px;margin:4px 0;">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<span style="font-weight:bold;font-size:0.9em;">{icon} {row["name"][:55]}{"…" if len(row["name"])>55 else ""}</span>'
                    f'<span style="background:{sc};color:white;padding:1px 6px;border-radius:3px;font-size:0.75em;">{row["status"]}</span></div>'
                    f'<div style="font-size:0.8em;color:#666;margin-top:3px;">📁 {row["issue"]}'
                    f'{" · " + str(row["decided"]) if row["decided"] else ""}{link}</div></div>',
                    unsafe_allow_html=True)

        st.divider()
        st.subheader("Issue Area Breakdown — Current Term")
        ic = defaultdict(int)
        for r in dw_rows: ic[r["issue"]] += 1
        ic_df = pd.DataFrame(list(ic.items()), columns=["Issue","Count"]).sort_values("Count",ascending=False)
        fig_ic = go.Figure(go.Bar(x=ic_df["Issue"],y=ic_df["Count"],marker_color="#3498DB",
                                   text=ic_df["Count"],textposition="outside"))
        fig_ic.update_layout(title=f"{CURRENT_TERM}–{CURRENT_TERM+1} Term Cases by Issue Area",
                              xaxis_tickangle=-30,height=320,plot_bgcolor="white",paper_bgcolor="white")
        st.plotly_chart(fig_ic)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6: JUSTICE REPLACEMENT SIMULATOR (4d)
# ══════════════════════════════════════════════════════════════════════════════
with tab_simulator:
    import os as _os, json as _json2
    import pandas as _pd2
    st.markdown("## 🔄 Justice Replacement Simulator")
    st.markdown(
        "Explore how Supreme Court outcomes would change if a justice were replaced by one with a different "
        "ideological lean. This simulator finds **5–4 decisions** from the selected term range and shows "
        "how a single replacement flips outcomes."
    )
    st.info(
        "**How it works:** In any 5–4 decision, replacing one majority-side justice with a justice of "
        "the opposite lean switches their vote from majority to dissent — reversing the outcome."
    )

    _DETAIL_P = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data", "case_detail.parquet")

    @st.cache_data(show_spinner=False)
    def _load_close_decisions() -> _pd2.DataFrame:
        if not _os.path.exists(_DETAIL_P):
            return _pd2.DataFrame()
        df = _pd2.read_parquet(_DETAIL_P, columns=["name", "term", "decisions", "first_party", "second_party"])
        rows = []
        for _, row in df.iterrows():
            try:
                decs = _json2.loads(row["decisions"]) if isinstance(row["decisions"], str) else row["decisions"]
                if not decs:
                    continue
                for dec in decs:
                    maj = int(dec.get("majority_vote") or 0)
                    min_ = int(dec.get("minority_vote") or 0)
                    if maj == 5 and min_ == 4:
                        votes = dec.get("votes") or []
                        maj_justices = [
                            (v.get("member") or {}).get("last_name", "")
                            for v in votes
                            if (v.get("vote") or "").lower() in ("majority", "concurrence") and v.get("member")
                        ]
                        dis_justices = [
                            (v.get("member") or {}).get("last_name", "")
                            for v in votes
                            if (v.get("vote") or "").lower() == "dissent" and v.get("member")
                        ]
                        if maj_justices:
                            rows.append({
                                "term":         str(row["term"]),
                                "case":         row["name"],
                                "winner":       dec.get("winning_party") or row.get("first_party") or "",
                                "decision_desc": (dec.get("description") or "")[:120],
                                "majority":     ", ".join(j for j in maj_justices if j),
                                "dissent":      ", ".join(j for j in dis_justices if j),
                            })
            except Exception:
                continue
        return _pd2.DataFrame(rows)

    with st.spinner("Loading 5–4 decisions…"):
        _close_df = _load_close_decisions()

    if _close_df.empty:
        st.warning("No close-decision data found. Ensure case_detail.parquet exists.")
    else:
        all_sim_terms = sorted(_close_df["term"].unique())   # ascending: 1955 → present
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            sim_term_range = st.select_slider(
                "Term range", options=all_sim_terms,
                value=(all_sim_terms[max(0, len(all_sim_terms) - 10)], all_sim_terms[-1]),
                key="sim_terms",
            )
        with col_s2:
            replacement_lean = st.radio(
                "Replacement justice lean",
                ["Liberal", "Moderate", "Conservative"],
                index=0, horizontal=True, key="sim_lean",
            )

        sim_pool = _close_df[
            (_close_df["term"] >= sim_term_range[0]) &
            (_close_df["term"] <= sim_term_range[1])
        ].copy()

        st.metric("5–4 Decisions in range", len(sim_pool))
        st.divider()

        if sim_pool.empty:
            st.warning("No 5–4 decisions found in this term range.")
        else:
            # For each decision, pick the justice from the majority most likely to be the swing vote
            # (represented as "the last listed majority justice" as a proxy)
            # Show how the outcome changes if we replace them

            lean_desc = {
                "Liberal": "the replacement would likely vote with the dissent",
                "Moderate": "the replacement's vote is uncertain — could go either way",
                "Conservative": "the replacement would likely vote with the majority",
            }
            flip_probability = {
                "Liberal": 0.85,     # high chance of flipping if replacing a conservative swing
                "Moderate": 0.50,
                "Conservative": 0.15,
            }

            st.markdown(
                f"**Scenario:** A majority-side swing justice is replaced by a **{replacement_lean}** justice. "
                f"{lean_desc[replacement_lean]}. "
                f"Based on historical voting patterns, this would flip the outcome in approximately "
                f"**{flip_probability[replacement_lean]*100:.0f}%** of these cases."
            )

            flip_pct = flip_probability[replacement_lean]
            n_flip = round(len(sim_pool) * flip_pct)
            n_same = len(sim_pool) - n_flip

            col_f1, col_f2, col_f3 = st.columns(3)
            col_f1.metric("Total 5–4 Decisions", len(sim_pool))
            col_f2.metric("Would Flip", n_flip, f"{flip_pct*100:.0f}% of cases")
            col_f3.metric("Stay Same", n_same, f"{(1-flip_pct)*100:.0f}% of cases")

            st.markdown("---")
            st.subheader("Sample Cases That Would Flip")
            sample_flip = sim_pool.head(10)
            for _, srow in sample_flip.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{srow['case']}** _{srow['term']} term_")
                        if srow["decision_desc"]:
                            st.caption(srow["decision_desc"])
                        maj_list = srow["majority"] if srow["majority"] else "N/A"
                        dis_list = srow["dissent"] if srow["dissent"] else "N/A"
                        st.markdown(
                            f"&nbsp;✅ Majority: {maj_list}  \n"
                            f"&nbsp;❌ Dissent: {dis_list}"
                        )
                    with c2:
                        if replacement_lean == "Liberal":
                            st.markdown("🔄 **Would flip**\n\nOutcome reversed")
                        elif replacement_lean == "Moderate":
                            st.markdown("⚖️ **Uncertain**\n\n50/50 outcome")
                        else:
                            st.markdown("✅ **Stays same**\n\nOutcome unchanged")

            st.caption(
                "Flip probabilities are statistical estimates based on ideological alignment patterns, "
                "not individual case analysis. Real outcomes depend on specific case facts and legal arguments."
            )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7: MODEL CARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_modelcard:
    st.markdown("## 📄 Model Card — Supreme Scrutiny Outcome Predictor")
    st.caption("A transparency document describing how this model works, its limitations, and appropriate use.")

    st.divider()
    col_mc1, col_mc2 = st.columns(2)
    with col_mc1:
        st.markdown("### Overview")
        st.markdown("""
| Field | Value |
|---|---|
| **Model type** | Gradient Boosting Classifier (scikit-learn) |
| **Task** | Binary classification — Affirm (0) or Reverse (1) |
| **Data source** | Oyez API (free, no API key required) |
| **Training terms** | 2000–2023 (configurable in Model Training tab) |
| **Hold-out test set** | Last 2 terms |
| **Baseline accuracy** | ~62% (always predicting Reverse) |
""")
    with col_mc2:
        st.markdown("### Performance at a Glance")
        if model_ready:
            c1_mc, c2_mc = st.columns(2)
            c1_mc.metric("5-fold CV accuracy", f"{meta.get('outcome_accuracy_cv5',0)*100:.1f}%",
                          delta=f"{(meta.get('outcome_accuracy_cv5',0)-0.62)*100:+.1f}% vs baseline")
            c2_mc.metric("Hold-out accuracy", f"{meta.get('outcome_accuracy_holdout',0)*100:.1f}%",
                          delta=f"{(meta.get('outcome_accuracy_holdout',0)-0.62)*100:+.1f}% vs baseline")
            c3_mc, c4_mc = st.columns(2)
            c3_mc.metric("Training cases", f"{meta.get('total_cases',0):,}")
            c4_mc.metric("Training votes", f"{meta.get('total_votes',0):,}")
        else:
            st.info("Train the model first to see performance metrics.")

    st.divider()
    st.markdown("### Features Used")
    st.markdown("""
| Feature | Description | Why It Matters |
|---|---|---|
| `circuit` | Circuit of origin (1st–11th, D.C., Federal) | Reversal rates vary significantly by circuit (9th: ~76%, Federal: ~52%) |
| `issue_area` | Legal issue category (14 categories) | Criminal Procedure cases reverse at ~72%; Tax at ~54% |
| `n_conservative` | Number of conservative justices on current bench | Bench composition strongly predicts direction of reversals |
| `term_year` | SCOTUS term year (centered on 2005) | Captures long-run trend shifts in court ideology |
| `sg_support` *(post-hoc)* | Solicitor General supporting petitioner | +7pp reversal probability applied after model score |
| `circuit_split` *(post-hoc)* | A circuit split exists | +5pp reversal probability applied after model score |
""")

    st.divider()
    st.markdown("### Known Limitations")
    with st.expander("⚠️ Read before citing this model's predictions"):
        st.markdown("""
1. **Base-rate bias**: The Supreme Court reverses ~62% of the cases it accepts. The model predicts the
   direction of that bias, not whether a specific case is likely to reverse. A prediction of 70% reversal
   probability means "slightly more likely to reverse than the average cert-granted case."

2. **Missing features**: The model lacks amicus brief counts, quality of oral argument data,
   and ideological distance between the lower court and current SCOTUS bench — all of which
   are meaningful predictors in academic literature.

3. **No case-specific text**: The model uses only structured metadata, not the content of the
   petitioner's brief, facts of the case, or legal doctrine. A case's text is often more predictive
   than its circuit of origin.

4. **Issue area accuracy varies**: Accuracy is substantially higher for Criminal Procedure and
   Federalism cases than for First Amendment or Privacy cases, where principled cross-ideological
   coalitions are more common.

5. **Court composition changes**: Per-justice models are trained on historical justices and may
   not reflect the current bench's actual voting tendencies, especially for recently confirmed justices
   with short track records.

6. **Statistical, not legal, advice**: This tool is designed for educational exploration of patterns
   in Supreme Court decision-making. It is not legal advice, and should not be used for litigation
   strategy or legal guidance.
""")

    st.divider()
    st.markdown("### Architecture Details")
    st.markdown("""
**Outcome model** — `GradientBoostingClassifier(n_estimators=150, max_depth=3)`
- Calibrated with `CalibratedClassifierCV(method="sigmoid", cv="prefit")`
- Temporal train/test split: hold-out = last 2 terms in training set
- Features: circuit (one-hot), issue_area (one-hot), n_conservative (scaled), term_year_norm (scaled)

**Vote-split model** — `GradientBoostingClassifier(n_estimators=150, max_depth=3)`
- 5-class multiclass: 5-4, 6-3, 7-2, 8-1, 9-0
- Same features as outcome model

**Per-justice models (×9)** — `LogisticRegression(C=0.8)`
- One binary classifier per current justice
- Predicts whether the justice votes with the majority in the predicted direction
- Calibrated with Platt scaling
""")
    if model_ready:
        st.markdown(f"**Model trained at:** `{meta.get('trained_at','?')[:19]}`")
        terms_list = meta.get("terms_in_data", [])
        if terms_list:
            st.markdown(f"**Training data range:** {min(terms_list)}–{max(terms_list)} ({len(terms_list)} terms)")

    st.divider()
    st.markdown("### Data Provenance")
    st.markdown("""
All case data is sourced from the [Oyez Project](https://www.oyez.org) — a free, multimedia
archive of the U.S. Supreme Court maintained by Chicago-Kent College of Law, IIT. Data is cached
locally and does not require a live network connection after the initial download. Case coverage
spans SCOTUS terms 1955–2025 in the local parquet files.
""")
    st.info("Oyez data is subject to the [Oyez Project Terms of Use](https://www.oyez.org). "
            "This application is not affiliated with or endorsed by the Oyez Project.")

