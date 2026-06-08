"""Plotly chart helpers with a consistent dark theme.

These functions take already-extracted series (lists) and return Plotly figures.
They never touch the store directly, keeping rendering and data separate.
"""
from __future__ import annotations

import plotly.graph_objects as go

# NVIDIA-flavoured dark palette.
GREEN = "#76b900"
BLUE = "#2e9bff"
ORANGE = "#ff9f1c"
RED = "#ff4b4b"
PURPLE = "#b388ff"
PAPER = "#0e1117"
PLOT = "#161a23"
GRID = "#2a2f3a"

PALETTE = [GREEN, BLUE, ORANGE, PURPLE, RED, "#00d1b2", "#f368e0", "#feca57"]


def _base_layout(fig: go.Figure, title: str, ylabel: str = "", height: int = 280):
    fig.update_layout(
        # Pin the title to the very top of the figure (container-relative) so it
        # never overlaps the legend or the plot area.
        title=dict(text=title, font=dict(size=14, color="#e6e6e6"),
                   x=0.5, xanchor="center", xref="paper",
                   y=0.98, yanchor="top", yref="container"),
        paper_bgcolor=PAPER,
        plot_bgcolor=PLOT,
        font=dict(color="#cfd3dc", size=11),
        # Extra top margin leaves a clear band for the title + legend row.
        margin=dict(l=50, r=20, t=64, b=30),
        height=height,
        hovermode="x unified",
        # Legend sits just below the title, above the plot area.
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    font=dict(size=10)),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, showgrid=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, showgrid=True, title=ylabel)
    return fig


def line(times, series: dict[str, list], title: str, ylabel: str = "",
         height: int = 280, fill: bool = False, ymax: float | None = None) -> go.Figure:
    """``series`` maps a legend label -> list of y values (aligned with ``times``)."""
    fig = go.Figure()
    for i, (label, ys) in enumerate(series.items()):
        color = PALETTE[i % len(PALETTE)]
        fig.add_trace(go.Scatter(
            x=times, y=ys, mode="lines", name=label,
            line=dict(color=color, width=2),
            fill="tozeroy" if fill and len(series) == 1 else None,
            fillcolor="rgba(118,185,0,0.12)" if fill else None,
        ))
    _base_layout(fig, title, ylabel, height)
    if ymax is not None:
        fig.update_yaxes(range=[0, ymax])
    return fig


def gauge(value: float, title: str, vmax: float = 100.0,
          suffix: str = "%", thresholds: tuple[float, float] = (70, 90),
          height: int = 220) -> go.Figure:
    warn, crit = thresholds
    if value >= crit:
        bar = RED
    elif value >= warn:
        bar = ORANGE
    else:
        bar = GREEN
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": suffix, "font": {"size": 26, "color": "#e6e6e6"}},
        title={"text": title, "font": {"size": 13, "color": "#cfd3dc"}},
        gauge={
            "axis": {"range": [0, vmax], "tickcolor": "#cfd3dc"},
            "bar": {"color": bar},
            "bgcolor": PLOT,
            "borderwidth": 0,
            "steps": [
                {"range": [0, warn], "color": "#1f2530"},
                {"range": [warn, crit], "color": "#33291a"},
                {"range": [crit, vmax], "color": "#3a1f1f"},
            ],
        },
    ))
    fig.update_layout(paper_bgcolor=PAPER, height=height,
                      margin=dict(l=20, r=20, t=40, b=10),
                      font=dict(color="#cfd3dc"))
    return fig


def heatmap(matrix, x_labels, y_labels, title: str, height: int = 280,
            zmax: float = 100.0) -> go.Figure:
    fig = go.Figure(go.Heatmap(
        z=matrix, x=x_labels, y=y_labels,
        colorscale=[[0, "#10331a"], [0.5, ORANGE], [1.0, RED]],
        zmin=0, zmax=zmax, colorbar=dict(title="%"),
    ))
    _base_layout(fig, title, "", height)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    return fig


def bars(labels, values, title: str, ylabel: str = "", height: int = 280,
         color: str = GREEN) -> go.Figure:
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=color))
    _base_layout(fig, title, ylabel, height)
    return fig
