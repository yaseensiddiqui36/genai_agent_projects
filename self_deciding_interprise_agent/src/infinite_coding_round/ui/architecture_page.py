"""Architecture & Tech Stack showcase page for the Streamlit app.

Purely presentational -- no agent calls happen here. Kept in its own module so
streamlit_app.py (the actual product page) stays focused on the ask/answer flow.
"""

from __future__ import annotations

import streamlit as st

TECH_STACK = [
    (
        "Orchestration",
        [
            ("🕸️", "LangGraph", "State-machine agent orchestration: router → parallel tool fan-out → synthesize → validate → retry"),
            ("🦜", "LangChain", "Prompt templates, message plumbing, and the FAISS / HuggingFace / Groq integration layer"),
        ],
    ),
    (
        "Language & Embedding Models",
        [
            ("⚡", "Groq (Llama 3.3 70B)", "Low-latency inference for routing, SQL generation, synthesis, and grounding validation"),
            ("🤗", "HuggingFace sentence-transformers", "all-MiniLM-L6-v2 embeddings for semantic document retrieval"),
        ],
    ),
    (
        "Data & Retrieval",
        [
            ("🗄️", "SQLite", "Seeded relational store: customers, orders, products, support_tickets"),
            ("🔍", "FAISS", "In-memory vector index over chunked policy documents, with citation-preserving metadata"),
        ],
    ),
    (
        "Service Layer",
        [
            ("🚀", "FastAPI", "POST /ask (structured JSON contract) and GET /stats (runtime observability)"),
            ("🎛️", "Streamlit", "This UI — talks to the API, with an automatic standalone in-process fallback"),
            ("📐", "Pydantic", "Typed request/response schemas and environment-driven settings"),
        ],
    ),
    (
        "Engineering & Ops",
        [
            ("📦", "uv", "Fast, reproducible dependency management (pyproject.toml + uv.lock)"),
            ("🐳", "Docker / docker-compose", "Containerized backend + UI for one-command deployment anywhere"),
            ("✅", "pytest + GitHub Actions", "Guardrail tests and a deterministic mocked-LLM retry test, run in CI on every push"),
        ],
    ),
]

FEATURES = [
    ("🧭", "Dynamic routing", "An LLM classifies each question as sql / document / hybrid before any tool runs — no hardcoded keyword matching."),
    ("🔁", "Self-correcting retry", "If execution or grounding validation fails, the agent automatically retries once with the prior error injected as context, then stops within a bounded budget."),
    ("🛡️", "Guardrailed SQL", "Only single, read-only SELECT statements are ever executed — write/DDL keywords, multi-statement payloads, and unbounded row counts are all rejected before touching the database."),
    ("📚", "Cited retrieval", "Every document-derived claim is traceable back to a specific source file and excerpt, not just a vague reference."),
    ("⚖️", "Grounding validation", "A second LLM pass checks the drafted answer against the retrieved evidence and assigns a confidence score — low-confidence or ungrounded answers fail validation."),
    ("⏱️", "Built-in observability", "Per-node latency breakdown and a live /stats endpoint (avg latency, confidence, retry rate, route mix) ship with the agent, not bolted on after."),
    ("🔀", "Deploy-anywhere UI", "The same Streamlit file works against a live FastAPI backend or, with zero backend running, falls back to calling the agent in-process — what makes a single-service Streamlit Cloud deployment possible."),
    ("🧪", "Tested retry logic", "The hardest-to-trigger path (an invalid SQL generation forcing a retry) is covered by a deterministic test with a scripted fake LLM, not left to chance against a live model."),
]

ARCHITECTURE_DOT = r"""
digraph architecture {
    rankdir=TB;
    bgcolor="transparent";
    fontname="Helvetica";
    node [fontname="Helvetica", fontsize=11, style="filled,rounded", shape=box, penwidth=1.2];
    edge [fontname="Helvetica", fontsize=9, color="#9CA3AF"];

    subgraph cluster_client {
        label="Client";
        style="rounded";
        color="#D1D5DB";
        fontsize=12;
        UI [label="Streamlit UI\n(this app)", fillcolor="#EEF2FF", color="#6366F1"];
    }

    subgraph cluster_service {
        label="Service layer";
        style="rounded";
        color="#D1D5DB";
        fontsize=12;
        API [label="FastAPI\nPOST /ask · GET /stats", fillcolor="#ECFDF5", color="#10B981"];
    }

    subgraph cluster_agent {
        label="LangGraph agent";
        style="rounded";
        color="#D1D5DB";
        fontsize=12;
        Router [label="router\n(LLM: classify + reason)", fillcolor="#FEF3C7", color="#F59E0B"];
        SQLNode [label="run_sql\n(LLM→SQL, read-only exec)", fillcolor="#FEF3C7", color="#F59E0B"];
        RetrievalNode [label="run_retrieval\n(FAISS top-k search)", fillcolor="#FEF3C7", color="#F59E0B"];
        Synthesize [label="synthesize\n(LLM: grounded answer)", fillcolor="#FEF3C7", color="#F59E0B"];
        Validate [label="validate\n(LLM-as-judge + confidence)", fillcolor="#FEF3C7", color="#F59E0B"];
        Retry [label="prepare_retry\n(retry_count += 1)", fillcolor="#FEE2E2", color="#EF4444"];
    }

    subgraph cluster_data {
        label="Data & models";
        style="rounded";
        color="#D1D5DB";
        fontsize=12;
        SQLite [label="SQLite\ncustomers/orders/\nproducts/tickets", fillcolor="#EFF6FF", color="#3B82F6"];
        FAISSDB [label="FAISS index\npolicy documents", fillcolor="#EFF6FF", color="#3B82F6"];
        Groq [label="Groq\nLlama 3.3 70B", fillcolor="#F5F3FF", color="#8B5CF6"];
        Embed [label="HuggingFace\nMiniLM embeddings", fillcolor="#F5F3FF", color="#8B5CF6"];
    }

    UI -> API [label="  question"];
    API -> Router;
    Router -> SQLNode [label="  sql / hybrid"];
    Router -> RetrievalNode [label="  document / hybrid"];
    SQLNode -> Synthesize;
    RetrievalNode -> Synthesize;
    Synthesize -> Validate;
    Validate -> Retry [label="  fail + retries left", color="#EF4444", fontcolor="#EF4444"];
    Retry -> SQLNode [style=dashed, color="#EF4444"];
    Retry -> RetrievalNode [style=dashed, color="#EF4444"];
    Validate -> API [label="  structured JSON"];
    API -> UI [label="  answer + evidence\n+ confidence + latency"];

    SQLNode -> SQLite [style=dotted, dir=both, color="#3B82F6"];
    RetrievalNode -> FAISSDB [style=dotted, dir=both, color="#3B82F6"];
    RetrievalNode -> Embed [style=dotted, color="#8B5CF6"];
    Router -> Groq [style=dotted, color="#8B5CF6"];
    SQLNode -> Groq [style=dotted, color="#8B5CF6"];
    Synthesize -> Groq [style=dotted, color="#8B5CF6"];
    Validate -> Groq [style=dotted, color="#8B5CF6"];
}
"""


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .tech-card, .feature-card {
            border: 1px solid rgba(127, 127, 127, 0.22);
            border-radius: 12px;
            padding: 0.85rem 1rem;
            margin-bottom: 0.6rem;
            background: rgba(99, 102, 241, 0.04);
            height: 100%;
        }
        .tech-card .name, .feature-card .name {
            font-weight: 700;
            font-size: 0.92rem;
            margin-bottom: 0.15rem;
        }
        .tech-card .desc, .feature-card .desc {
            font-size: 0.8rem;
            opacity: 0.8;
            line-height: 1.35;
        }
        .section-eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-size: 0.72rem;
            font-weight: 700;
            color: rgb(99, 102, 241);
            margin-bottom: 0.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_cards(items: list[tuple[str, str, str]], css_class: str, columns: int = 2) -> None:
    cols = st.columns(columns)
    for i, (icon, name, desc) in enumerate(items):
        with cols[i % columns]:
            st.markdown(
                f'<div class="{css_class}">'
                f'<div class="name">{icon} {name}</div>'
                f'<div class="desc">{desc}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )


def render() -> None:
    _inject_css()

    st.markdown(
        '<div class="app-header"><span class="icon">🏗️</span>'
        "<h1>Architecture &amp; Tech Stack</h1></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="app-subtitle">A self-correcting, tool-using GenAI agent: LangGraph orchestrates '
        "routing, retrieval, generation and self-validation across a read-only SQL database and a "
        "FAISS-indexed policy corpus.</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-eyebrow">System diagram</div>', unsafe_allow_html=True)
    st.graphviz_chart(ARCHITECTURE_DOT, width='stretch')
    st.caption(
        "Solid arrows = control/data flow. Dotted arrows = model/store dependencies. "
        "Dashed red arrows = the single automatic retry loop (execution or grounding failure)."
    )

    st.divider()

    st.markdown('<div class="section-eyebrow">Key features</div>', unsafe_allow_html=True)
    _render_cards(FEATURES, "feature-card", columns=2)

    st.divider()

    st.markdown('<div class="section-eyebrow">Tech stack</div>', unsafe_allow_html=True)
    for category, items in TECH_STACK:
        st.markdown(f"**{category}**")
        _render_cards(items, "tech-card", columns=2)

    st.divider()
    st.caption(
        "Source: github.com/yaseensiddiqui36/self_deciding_interprise_agent · "
        "See README.md and docs/TEST_CASES.md for the full write-up and mandatory test cases."
    )
