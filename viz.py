"""
viz.py - Plotly chart builders for RAG BenchX results.
"""
from __future__ import annotations

from typing import List

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from evaluation import TechniqueMetrics
import config

# Colour palette (one per technique, consistent across charts)
PALETTE = [
    "#6C63FF",  # Naive Vector   - purple
    "#43AA8B",  # BM25            - teal
    "#F9844A",  # Hybrid          - orange
    "#E63946",  # Reranker        - red
    "#457B9D",  # Parent-Document - blue
]

CHART_TEMPLATE = "plotly_dark"
FONT_FAMILY = "Inter, system-ui, sans-serif"


def _base_layout(title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=18, family=FONT_FAMILY, color="#E0E0E0")),
        paper_bgcolor="#0F1117",
        plot_bgcolor="#0F1117",
        font=dict(family=FONT_FAMILY, color="#CCCCCC"),
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
        margin=dict(l=60, r=30, t=60, b=60),
    )


# ── Chart 1: Grouped bar - Hit Rate & MRR ────────────────────────────────────

def chart_quality(metrics: List[TechniqueMetrics]) -> go.Figure:
    names = [m.name for m in metrics]
    hit_rates = [m.hit_rate for m in metrics]
    mrrs = [m.mrr for m in metrics]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Hit Rate@k",
        x=names,
        y=hit_rates,
        marker_color=[PALETTE[i % len(PALETTE)] for i in range(len(names))],
        opacity=0.9,
        text=[f"{v:.2f}" for v in hit_rates],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="MRR",
        x=names,
        y=mrrs,
        marker_color=[PALETTE[i % len(PALETTE)] for i in range(len(names))],
        opacity=0.55,
        text=[f"{v:.2f}" for v in mrrs],
        textposition="outside",
    ))
    fig.update_layout(
        **_base_layout(f"Retrieval Quality (k={config.RETRIEVAL_K})"),
        barmode="group",
        yaxis=dict(range=[0, 1.15], title="Score", gridcolor="#2A2A2A"),
        xaxis=dict(gridcolor="#2A2A2A"),
    )
    return fig


# ── Chart 2: Latency bar ─────────────────────────────────────────────────────

def chart_latency(metrics: List[TechniqueMetrics]) -> go.Figure:
    names = [m.name for m in metrics]
    latencies = [m.avg_latency_ms for m in metrics]
    index_times = [m.index_time_ms for m in metrics]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Avg Query Latency (ms)",
        x=names,
        y=latencies,
        marker_color=PALETTE[:len(names)],
        opacity=0.9,
        text=[f"{v:.1f}ms" for v in latencies],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Index Time (ms)",
        x=names,
        y=index_times,
        marker_color=PALETTE[:len(names)],
        opacity=0.45,
        text=[f"{v:.0f}ms" for v in index_times],
        textposition="outside",
    ))
    fig.update_layout(
        **_base_layout("Latency Breakdown"),
        barmode="group",
        yaxis=dict(title="Time (ms)", gridcolor="#2A2A2A"),
        xaxis=dict(gridcolor="#2A2A2A"),
    )
    return fig


# ── Chart 3: Quality vs Speed scatter ────────────────────────────────────────

def chart_scatter(metrics: List[TechniqueMetrics]) -> go.Figure:
    fig = go.Figure()
    for i, m in enumerate(metrics):
        fig.add_trace(go.Scatter(
            x=[m.avg_latency_ms],
            y=[m.mrr],
            mode="markers+text",
            name=m.name,
            text=[m.name],
            textposition="top center",
            textfont=dict(size=11),
            marker=dict(size=18, color=PALETTE[i % len(PALETTE)], opacity=0.9,
                        line=dict(width=2, color="white")),
        ))
    fig.update_layout(
        **_base_layout("Quality vs Speed"),
        xaxis=dict(title="Avg Query Latency (ms)", gridcolor="#2A2A2A"),
        yaxis=dict(title="MRR", range=[0, 1.1], gridcolor="#2A2A2A"),
        showlegend=False,
    )
    return fig


# ── Table dataframe ───────────────────────────────────────────────────────────

def build_results_df(metrics: List[TechniqueMetrics]) -> pd.DataFrame:
    rows = []
    for m in metrics:
        rows.append({
            "Technique": m.name,
            f"Hit Rate@{config.RETRIEVAL_K}": round(m.hit_rate, 4),
            f"Recall@{config.RETRIEVAL_K}": round(m.recall, 4),
            "MRR": round(m.mrr, 4),
            "Avg Latency (ms)": round(m.avg_latency_ms, 1),
            "Index Time (ms)": round(m.index_time_ms, 0),
        })
    return pd.DataFrame(rows)


# ── Recommendation ────────────────────────────────────────────────────────────

CLOSE_CALL_THRESHOLD = 0.05   # MRR margin below which we warn "close call"

_TECHNIQUE_NOTES = {
    "Naive Vector":         "Dense semantic search - great for paraphrased or conceptual queries.",
    "BM25":                 "Keyword matching - best when exact terms matter (e.g. IDs, names).",
    "Hybrid (BM25 + Vector)": "Combines keyword and semantic signals via RRF - often a safe all-rounder.",
    "Vector + Reranker":    "Two-stage: dense recall then cross-encoder precision - high quality, higher latency.",
    "Parent-Document":      "Retrieves broader context - good for documents requiring surrounding paragraphs.",
}


def build_recommendation(metrics: List[TechniqueMetrics]) -> dict:
    """
    Pick the best technique: primary sort MRR, tie-break Hit Rate, then speed.
    Returns dict with keys: best_name, explanation, close_call (bool), runner_up.
    """
    sorted_m = sorted(
        metrics,
        key=lambda m: (m.mrr, m.hit_rate, -m.avg_latency_ms),
        reverse=True,
    )
    best = sorted_m[0]
    runner_up = sorted_m[1] if len(sorted_m) > 1 else None

    close_call = (
        runner_up is not None
        and abs(best.mrr - runner_up.mrr) < CLOSE_CALL_THRESHOLD
    )

    explanation = _TECHNIQUE_NOTES.get(best.name, "")

    return {
        "best_name": best.name,
        "best_mrr": best.mrr,
        "best_hit_rate": best.hit_rate,
        "explanation": explanation,
        "close_call": close_call,
        "runner_up": runner_up.name if runner_up else None,
        "runner_up_mrr": runner_up.mrr if runner_up else None,
    }