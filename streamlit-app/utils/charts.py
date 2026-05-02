import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

LEVEL_COLORS = {
    "Lower Court": "#4A90D9",
    "Appeals Court": "#E67E22",
    "Supreme Court": "#C0392B",
}

LEVEL_LABELS = {
    "Lower Court": "Trial\nCourt",
    "Appeals Court": "Appeals\nCourt",
    "Supreme Court": "SCOTUS",
}

def build_journey_diagram(steps: list[dict], case_name: str) -> go.Figure:
    """Build a vertical flowchart of the case journey through courts."""
    if not steps:
        return None

    n = len(steps)
    # Spread nodes evenly between 0.15 and 0.85 on the y axis
    if n == 1:
        node_y = [0.5]
    else:
        node_y = [0.85 - i * (0.70 / (n - 1)) for i in range(n)]
    node_x = [0.5] * n

    # Edge traces with arrowhead effect
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

    # Short label inside the circle
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
            size=120,
            color=node_colors,
            line=dict(width=4, color="white"),
            opacity=0.95,
        ),
        text=node_inner,
        textposition="middle center",
        textfont=dict(size=13, color="white", family="Arial Black, Arial, sans-serif"),
        hovertext=hover_texts,
        hoverinfo="text",
        showlegend=False,
    )

    # Build annotations: court name to the right, decision below
    annotations = []
    for i, step in enumerate(steps):
        court = step.get("court", "")
        decision = step.get("decision", "")
        level = step.get("level", "")

        # Court name label to the right of the circle
        annotations.append(dict(
            x=0.62,
            y=node_y[i],
            xref="paper",
            yref="paper",
            text=f"<b>{court}</b>",
            showarrow=False,
            font=dict(size=14, color="#2C3E50"),
            align="left",
            xanchor="left",
            yanchor="middle",
        ))
        # Decision sub-label
        if decision:
            annotations.append(dict(
                x=0.62,
                y=node_y[i] - 0.04,
                xref="paper",
                yref="paper",
                text=f"<i>Outcome: {decision}</i>",
                showarrow=False,
                font=dict(size=11, color="#7F8C8D"),
                align="left",
                xanchor="left",
                yanchor="top",
            ))

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title=dict(text=f"Case Journey: {case_name}", font=dict(size=16)),
        annotations=annotations,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 1]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 1]),
        height=max(350, 220 * n),
        margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def build_voting_chart(justices: list[dict]) -> go.Figure:
    """Build a bar chart of justice votes."""
    if not justices:
        return None

    vote_map = {"majority": "#27AE60", "concurrence": "#2ECC71", "dissent": "#E74C3C", "recusal": "#95A5A6"}
    names = [j["name"] for j in justices]
    votes = [j["vote"] for j in justices]
    colors = [vote_map.get(v.lower() if v else "", "#BDC3C7") for v in votes]

    fig = go.Figure(go.Bar(
        x=names,
        y=[1] * len(names),
        marker_color=colors,
        text=votes,
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
