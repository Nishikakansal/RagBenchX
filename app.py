"""
app.py - RAG BenchX: Streamlit UI
"""
from __future__ import annotations

import time
import sys
import os

import numpy as np
import streamlit as st
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, CrossEncoder

load_dotenv()

import config
from ingestion import parse_document, ParsedDoc
from techniques.naive_vector import NaiveVectorRetriever
from techniques.bm25_retriever import BM25Retriever
from techniques.hybrid import HybridRetriever
from techniques.reranker import RerankerRetriever
from techniques.parent_document import ParentDocumentRetriever
from question_generator import generate_questions
from evaluation import evaluate_technique, TechniqueMetrics
import viz

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG BenchX",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', system-ui, sans-serif;
}

/* Dark gradient background */
.stApp {
    background: linear-gradient(135deg, #0a0a0f 0%, #0f1117 50%, #0d1020 100%);
}

/* Hero header */
.hero-title {
    font-size: 3.2rem;
    font-weight: 700;
    background: linear-gradient(90deg, #6C63FF, #a78bfa, #F9844A);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.2rem;
}
.hero-sub {
    font-size: 1.1rem;
    color: #9CA3AF;
    margin-bottom: 2rem;
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, rgba(108,99,255,0.12), rgba(108,99,255,0.04));
    border: 1px solid rgba(108,99,255,0.25);
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #a78bfa;
}
.metric-label {
    font-size: 0.82rem;
    color: #9CA3AF;
    margin-top: 0.1rem;
}

/* Recommendation card */
.rec-card {
    background: linear-gradient(135deg, rgba(67,170,139,0.15), rgba(67,170,139,0.05));
    border: 1px solid rgba(67,170,139,0.4);
    border-radius: 16px;
    padding: 1.8rem 2rem;
    margin: 1rem 0;
}
.rec-title {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #43AA8B;
    margin-bottom: 0.4rem;
}
.rec-name {
    font-size: 2rem;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 0.6rem;
}
.rec-explain {
    font-size: 1rem;
    color: #D1D5DB;
    line-height: 1.6;
}

/* Close-call warning */
.close-call {
    background: rgba(249,132,74,0.12);
    border: 1px solid rgba(249,132,74,0.4);
    border-radius: 10px;
    padding: 0.8rem 1.2rem;
    color: #F9844A;
    font-size: 0.9rem;
    margin-top: 0.8rem;
}

/* Doc type badge */
.doc-badge {
    display: inline-block;
    padding: 0.25rem 0.85rem;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}
.badge-technical      { background: rgba(230,57,70,0.18);  color: #E63946; border: 1px solid rgba(230,57,70,0.35); }
.badge-plain-text     { background: rgba(69,123,157,0.18); color: #457B9D; border: 1px solid rgba(69,123,157,0.35); }
.badge-long-hierarchical { background: rgba(108,99,255,0.18); color: #6C63FF; border: 1px solid rgba(108,99,255,0.35); }

/* Limitations note */
.limitations {
    background: rgba(255,255,255,0.03);
    border-left: 3px solid #4B5563;
    padding: 0.8rem 1.2rem;
    border-radius: 0 8px 8px 0;
    color: #6B7280;
    font-size: 0.85rem;
    margin-top: 2rem;
}

/* Step pills */
.step-pill {
    background: rgba(108,99,255,0.15);
    border: 1px solid rgba(108,99,255,0.3);
    border-radius: 999px;
    padding: 0.15rem 0.7rem;
    font-size: 0.75rem;
    color: #a78bfa;
    font-weight: 600;
    margin-right: 0.4rem;
}
</style>
""", unsafe_allow_html=True)


# ── Cached model loaders ──────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_embed_model():
    return SentenceTransformer(config.EMBED_MODEL)


@st.cache_resource(show_spinner=False)
def load_cross_encoder():
    return CrossEncoder(config.CROSS_ENCODER_MODEL)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _badge(doc_type: str) -> str:
    cls = f"badge-{doc_type.replace(' ', '-').replace('/', '-')}"
    return f'<span class="doc-badge {cls}">{doc_type}</span>'


def _run_pipeline(parsed: ParsedDoc, progress, status_text) -> list[TechniqueMetrics]:
    """Full pipeline: embed -> index 5 techniques -> generate questions -> evaluate."""
    chunks = parsed.chunks

    # 1. Load models
    status_text.markdown("**Loading models...**")
    embed_model = load_embed_model()
    cross_encoder = load_cross_encoder()
    progress.progress(0.05)

    # 2. Encode chunks ONCE
    status_text.markdown("**Encoding chunks (shared across techniques)...**")
    texts = [c.text for c in chunks]
    embeddings = embed_model.encode(
        texts, batch_size=64, show_progress_bar=False, convert_to_numpy=True
    ).astype(np.float32)
    progress.progress(0.20)

    # 3. Index all 5 techniques
    retrievers_config = [
        ("Naive Vector",         NaiveVectorRetriever(embed_model=embed_model),       True),
        ("BM25",                 BM25Retriever(),                                      False),
        ("Hybrid (BM25+Vector)", HybridRetriever(embed_model=embed_model),             True),
        ("Vector + Reranker",    RerankerRetriever(embed_model=embed_model, cross_encoder=cross_encoder), True),
        ("Parent-Document",      ParentDocumentRetriever(embed_model=embed_model),    False),
    ]

    indexed_retrievers = []
    for i, (label, retriever, uses_emb) in enumerate(retrievers_config):
        status_text.markdown(f"**Indexing: {label}...**")
        t0 = time.perf_counter()
        if uses_emb:
            retriever.index(chunks, precomputed_embeddings=embeddings)
        else:
            retriever.index(chunks)
        idx_time = (time.perf_counter() - t0) * 1000
        indexed_retrievers.append((retriever, idx_time))
        progress.progress(0.20 + (i + 1) * 0.08)

    # 4. Generate questions
    status_text.markdown("**Generating evaluation questions via Groq...**")
    questions = generate_questions(chunks, n=config.NUM_QUESTIONS)
    progress.progress(0.65)

    # 5. Evaluate each technique
    all_metrics: list[TechniqueMetrics] = []
    for i, (retriever, idx_time) in enumerate(indexed_retrievers):
        status_text.markdown(f"**Evaluating: {retriever.name}...**")
        metrics = evaluate_technique(retriever, questions, chunks, index_time_ms=idx_time)
        all_metrics.append(metrics)
        progress.progress(0.65 + (i + 1) * 0.07)

    progress.progress(1.0)
    status_text.markdown("**Done!**")
    return all_metrics


# ── Main UI ───────────────────────────────────────────────────────────────────

def main():
    # Hero
    st.markdown('<div class="hero-title">⚡ RAG BenchX</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-sub">Upload any document and benchmark 5 RAG retrieval techniques '
        'on YOUR content — with real metrics, charts, and a recommendation.</div>',
        unsafe_allow_html=True,
    )

    # Upload
    col_up, col_info = st.columns([3, 2])
    with col_up:
        uploaded = st.file_uploader(
            "Upload document (PDF, TXT, or MD)",
            type=["pdf", "txt", "md"],
            help="Capped at 50k words, spread across the document.",
        )
    with col_info:
        st.markdown("#### How it works")
        st.markdown(
            "1. **Parse** your document and detect its type  \n"
            "2. **Generate** ~15 questions via Groq (1 LLM call)  \n"
            "3. **Run** 5 RAG techniques on identical chunks  \n"
            "4. **Compare** Hit Rate, MRR, Recall & latency  \n"
            "5. **Recommend** the best technique for your doc  \n"
            "\n*Estimated runtime: ~60 seconds*"
        )

    if not uploaded:
        st.info("👆 Upload a document to get started.")
        return

    # Parse
    with st.spinner("Parsing document..."):
        parsed = parse_document(uploaded.name, uploaded.read())

    # Doc summary
    st.markdown("---")
    st.markdown("### 📄 Document Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{parsed.word_count:,}</div>'
            f'<div class="metric-label">Total Words</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{len(parsed.chunks)}</div>'
            f'<div class="metric-label">Chunks (k={config.CHUNK_SIZE}w)</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{parsed.heading_depth}</div>'
            f'<div class="metric-label">Max Heading Depth</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{parsed.code_table_density:.0%}</div>'
            f'<div class="metric-label">Code/Table Density</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f"**Document type detected:** {_badge(parsed.doc_type)}", unsafe_allow_html=True
    )

    # Run button
    st.markdown("---")
    if st.button("🚀 Run Benchmark", type="primary", use_container_width=True):
        progress = st.progress(0.0)
        status_text = st.empty()

        try:
            all_metrics = _run_pipeline(parsed, progress, status_text)
        except EnvironmentError as e:
            st.error(f"**Environment error:** {e}")
            st.stop()
        except RuntimeError as e:
            st.error(f"**Pipeline error:** {e}")
            st.stop()

        status_text.empty()
        progress.empty()

        # ── Results ───────────────────────────────────────────────────────────
        st.markdown("## 📊 Benchmark Results")

        # Charts row 1
        c_left, c_right = st.columns(2)
        with c_left:
            st.plotly_chart(viz.chart_quality(all_metrics), use_container_width=True)
        with c_right:
            st.plotly_chart(viz.chart_latency(all_metrics), use_container_width=True)

        # Charts row 2
        st.plotly_chart(viz.chart_scatter(all_metrics), use_container_width=True)

        # Table
        st.markdown("### 📋 Full Metrics Table")
        df = viz.build_results_df(all_metrics)
        try:
            styled_df = df.style.background_gradient(
                subset=[f"Hit Rate@{config.RETRIEVAL_K}", "MRR"],
                cmap="Purples",
            ).format(precision=4)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        except Exception:
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Recommendation
        st.markdown("### 🏆 Recommendation")
        rec = viz.build_recommendation(all_metrics)

        st.markdown(f"""
<div class="rec-card">
  <div class="rec-title">Best Technique for This Document</div>
  <div class="rec-name">{rec['best_name']}</div>
  <div class="rec-explain">{rec['explanation']}</div>
  <br/>
  <div style="color:#9CA3AF; font-size:0.88rem;">
    MRR: <strong style="color:#a78bfa">{rec['best_mrr']:.3f}</strong> &nbsp;|&nbsp;
    Hit Rate@{config.RETRIEVAL_K}: <strong style="color:#a78bfa">{rec['best_hit_rate']:.3f}</strong>
  </div>
</div>
""", unsafe_allow_html=True)

        if rec["close_call"]:
            st.markdown(f"""
<div class="close-call">
  ⚠️ <strong>Close call!</strong> {rec['runner_up']} scores within {viz.CLOSE_CALL_THRESHOLD:.0%} MRR
  of the winner ({rec['runner_up_mrr']:.3f} vs {rec['best_mrr']:.3f}).
  Consider your latency tolerance when choosing.
</div>
""", unsafe_allow_html=True)

        # Limitations
        st.markdown(f"""
<div class="limitations">
  <strong>Limitations:</strong> Questions are synthetically generated by an LLM and may not represent
  real user queries. Sample is capped at {config.MAX_WORDS:,} words. Results are approximate and can
  vary between runs due to question sampling. Not a substitute for domain-specific human evaluation.
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()