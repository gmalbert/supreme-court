import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

LEVEL_COLORS = {
    "Lower Court": "#4A90D9",
    "Appellate Court": "#E67E22",
    "Appeals Court": "#E67E22",   # legacy alias
    "Supreme Court": "#C0392B",
}

LEVEL_LABELS = {
    "Lower Court": "Trial Court",
    "Appellate Court": "Appeals Ct.",
    "Appeals Court": "Appeals Ct.",  # legacy alias
    "Supreme Court": "SCOTUS",
}

def build_journey_diagram(steps: list[dict], case_name: str) -> go.Figure:
    """Build a vertical flowchart using a single data coordinate system.
    Circles sit in the left column (x=2), labels in the right column (x=5.5).
    All annotations use xref='x', yref='y' so they align perfectly.
    """
    if not steps:
        return None

    n = len(steps)
    # Y positions in data space: top = (n-1)*4, bottom = 0, step = 4
    node_y = [(n - 1 - i) * 4 for i in range(n)]
    node_x = [2] * n  # circles in left column

    # Connecting lines between circles
    edge_traces = []
    for i in range(n - 1):
        edge_traces.append(go.Scatter(
            x=[node_x[i], node_x[i + 1]],
            y=[node_y[i], node_y[i + 1]],
            mode="lines",
            line=dict(width=4, color="#B0BEC5"),
            hoverinfo="none",
            showlegend=False,
        ))

    node_inner = []
    node_colors = []
    hover_texts = []
    for step in steps:
        level = step.get("level", "Court")
        decision = step.get("decision", "")
        node_inner.append(LEVEL_LABELS.get(level, level))
        node_colors.append(LEVEL_COLORS.get(level, "#95A5A6"))
        hover = f"<b>{step['court']}</b><br>Level: {level}"
        if decision:
            hover += f"<br>Outcome: {decision}"
        hover_texts.append(hover)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        marker=dict(
            size=90,
            color=node_colors,
            line=dict(width=3, color="white"),
            opacity=0.95,
        ),
        text=node_inner,
        textposition="middle center",
        textfont=dict(size=11, color="white", family="Arial Black, Arial, sans-serif"),
        hovertext=hover_texts,
        hoverinfo="text",
        showlegend=False,
    )

    # Annotations in data coordinates so they line up with the circles
    annotations = []
    for i, step in enumerate(steps):
        court = step.get("court", "")
        decision = step.get("decision", "")

        annotations.append(dict(
            x=5.5,
            y=node_y[i] + 0.35,
            xref="x",
            yref="y",
            text=f"<b>{court}</b>",
            showarrow=False,
            font=dict(size=15, color="#2C3E50"),
            align="left",
            xanchor="left",
            yanchor="bottom",
        ))
        if decision:
            annotations.append(dict(
                x=5.5,
                y=node_y[i] - 0.35,
                xref="x",
                yref="y",
                text=f"<i>Outcome: {decision}</i>",
                showarrow=False,
                font=dict(size=12, color="#7F8C8D"),
                align="left",
                xanchor="left",
                yanchor="top",
            ))

    x_max = 14  # enough room for long court names
    y_min = -2
    y_max = (n - 1) * 4 + 2

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title=dict(text=f"Case Journey: {case_name}", font=dict(size=16)),
        annotations=annotations,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, x_max]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[y_min, y_max]),
        height=max(380, 260 * n),
        margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def build_voting_chart(justices: list[dict]) -> go.Figure:
    """Build a bar chart of justice votes.

    Accepts both the flat shape ``{"name": ..., "vote": ...}`` and the Oyez API
    shape ``{"member": {"name": ...}, "vote": ...}``.
    """
    if not justices:
        return None

    def _name(j: dict) -> str:
        # Oyez API: member is a nested dict
        member = j.get("member")
        if isinstance(member, dict):
            return member.get("name", "Unknown")
        return j.get("name", "Unknown")

    vote_map = {"majority": "#27AE60", "concurrence": "#2ECC71", "dissent": "#E74C3C", "minority": "#E74C3C", "recusal": "#95A5A6"}
    names = [_name(j) for j in justices]
    votes = [j.get("vote", "") or "" for j in justices]
    colors = [vote_map.get(v.lower() if v else "", "#BDC3C7") for v in votes]

    fig = go.Figure(go.Bar(
        x=names,
        y=[1] * len(names),
        marker_color=colors,
        text=[v.title() if v else "" for v in votes],
        textposition="inside",
        hovertext=[f"{n}: {v}" for n, v in zip(names, votes)],
        hoverinfo="text",
    ))
    fig.update_layout(
        title="Justice Votes",
        xaxis_title="Justice",
        yaxis=dict(showgrid=False, showticklabels=False),
        height=280,
        margin=dict(l=20, r=20, t=50, b=80),
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis_tickangle=-30,
    )
    return fig


def build_issue_area_chart(cases: list[dict]) -> go.Figure:
    """Build a pie chart of issue areas for a set of cases."""
    area_counts: dict[str, int] = {}
    for c in cases:
        # Prefer pre-computed "Issue Area" key (set by infer_issue_area) if present,
        # otherwise fall back to raw Oyez field
        if "Issue Area" in c:
            label = c["Issue Area"] or "Unknown"
        else:
            area = c.get("issue_area", {})
            if isinstance(area, dict):
                label = area.get("label", "Unknown")
            elif area:
                label = str(area)
            else:
                label = "Unknown"
        area_counts[label] = area_counts.get(label, 0) + 1

    if not area_counts:
        return None

    labels = list(area_counts.keys())
    values = list(area_counts.values())
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.35,
        textinfo="label+percent",
    ))
    fig.update_layout(
        title="Cases by Issue Area",
        height=400,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def build_decision_trend_chart(cases_by_term: dict[int, list]) -> go.Figure:
    """Build a line chart of case counts per term."""
    terms = sorted(cases_by_term.keys())
    counts = [len(cases_by_term[t]) for t in terms]
    fig = px.line(
        x=terms,
        y=counts,
        labels={"x": "Term", "y": "Number of Cases"},
        title="Cases Decided per Term",
        markers=True,
    )
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig
