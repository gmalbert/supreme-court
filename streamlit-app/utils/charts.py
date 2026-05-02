import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

LEVEL_COLORS = {
    "Lower Court": "#4A90D9",
    "Appeals Court": "#E67E22",
    "Supreme Court": "#C0392B",
}

def build_journey_diagram(steps: list[dict], case_name: str) -> go.Figure:
    """Build a vertical flowchart of the case journey through courts."""
    if not steps:
        return None

    n = len(steps)
    node_x = [0.5] * n
    node_y = [1 - i / max(n - 1, 1) for i in range(n)]

    # Edge traces (arrows between nodes)
    edge_traces = []
    for i in range(n - 1):
        edge_traces.append(go.Scatter(
            x=[node_x[i], node_x[i + 1]],
            y=[node_y[i], node_y[i + 1]],
            mode="lines",
            line=dict(width=3, color="#7F8C8D"),
            hoverinfo="none",
            showlegend=False,
        ))

    # Node trace
    node_text = []
    node_colors = []
    hover_texts = []
    for step in steps:
        level = step.get("level", "Court")
        decision = step.get("decision", "")
        node_text.append(f"<b>{step['court']}</b><br><i>{level}</i>")
        node_colors.append(LEVEL_COLORS.get(level, "#95A5A6"))
        hover = f"<b>{step['court']}</b><br>Level: {level}"
        if decision:
            hover += f"<br>Decision: {decision}"
        hover_texts.append(hover)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        marker=dict(size=60, color=node_colors, line=dict(width=2, color="white")),
        text=node_text,
        textposition="middle center",
        textfont=dict(size=11, color="white"),
        hovertext=hover_texts,
        hoverinfo="text",
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title=dict(text=f"Case Journey: {case_name}", font=dict(size=16)),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 1]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.2, 1.2]),
        height=max(300, 150 * n),
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
