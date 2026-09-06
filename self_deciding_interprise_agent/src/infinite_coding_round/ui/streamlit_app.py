"""Streamlit UI for the self-correcting enterprise data agent.

Run standalone (no separate backend needed):
    streamlit run src/infinite_coding_round/ui/streamlit_app.py

Or point it at a running FastAPI backend:
    AGENT_MODE=api AGENT_API_URL=http://127.0.0.1:8000 streamlit run ...

By default (AGENT_MODE=auto) it tries the FastAPI backend first and transparently
falls back to calling the agent in-process if no backend is reachable -- this is what
lets the same file work both in local dev (decoupled API) and on a single-service
deployment (e.g. Streamlit Community Cloud, where no separate backend is running).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `infinite_coding_round` importable even when this file is run directly by
# Streamlit Cloud without the project having been pip-installed first.
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import streamlit as st

from infinite_coding_round.ui.architecture_page import render as render_architecture_page

# Secrets configured in Streamlit Cloud (Settings -> Secrets) are only exposed via
# st.secrets, not as real environment variables. Promote them to env vars *before*
# importing anything from infinite_coding_round, since Settings() reads env at import time.
for _key in ("GROQ_API_KEY", "GROQ_MODEL", "EMBEDDING_MODEL"):
    if _key not in os.environ:
        try:
            if _key in st.secrets:
                os.environ[_key] = str(st.secrets[_key])
        except Exception:
            pass

import requests  # noqa: E402

API_BASE_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8000")
AGENT_MODE = os.getenv("AGENT_MODE", "auto")  # "api" | "direct" | "auto"

EXAMPLE_QUESTIONS = [
    ("📦", "How many orders does customer Alice Chen have?"),
    ("💰", "What is the refund window for furniture items?"),
    ("⚠️", "Hassan Ali reported a noisy standing desk motor after 40 days. Is he eligible for a refund, and should this be escalated?"),
    ("❓", "What is the CEO's stance on remote work?"),
]


# --------------------------------------------------------------------------- #
# Agent access: HTTP (decoupled FastAPI backend) with in-process fallback
# --------------------------------------------------------------------------- #


@st.cache_resource(show_spinner=False)
def _get_direct_agent():
    """Lazily builds the LangGraph agent in-process (used for standalone deployment)."""
    from infinite_coding_round.agent.graph import run_agent
    from infinite_coding_round.db.seed import seed_database
    from infinite_coding_round.config import DB_PATH
    from infinite_coding_round.rag.vectorstore import load_or_build_index

    if not DB_PATH.exists():
        seed_database()
    load_or_build_index()  # builds the FAISS index on first run if missing
    return run_agent


def _call_via_api(question: str) -> dict:
    response = requests.post(f"{API_BASE_URL}/ask", json={"question": question}, timeout=120)
    response.raise_for_status()
    return response.json()


def _call_direct(question: str) -> dict:
    run_agent = _get_direct_agent()
    state = run_agent(question)
    return {
        "answer": state.get("answer", ""),
        "reasoning": state.get("reasoning", ""),
        "tools_used": state.get("tools_used", []),
        "generated_sql": state.get("sql_query"),
        "retrieved_sources": state.get("retrieved_sources", []),
        "confidence": state.get("confidence", 0.0),
        "validation_result": state.get("validation_reason", ""),
        "validation_passed": state.get("validation_passed", False),
        "retry_count": state.get("retry_count", 0),
        "latency_ms": state.get("latency_ms", 0.0),
        "node_latencies_ms": state.get("node_latencies_ms", {}),
    }


def ask_agent(question: str) -> tuple[dict, str]:
    """Returns (result, mode_used)."""
    if AGENT_MODE == "direct":
        return _call_direct(question), "direct"
    if AGENT_MODE == "api":
        return _call_via_api(question), "api"

    # auto: prefer API, remember the fallback for the rest of the session
    if not st.session_state.get("force_direct_mode"):
        try:
            return _call_via_api(question), "api"
        except requests.RequestException:
            st.session_state["force_direct_mode"] = True
    return _call_direct(question), "direct"


# --------------------------------------------------------------------------- #
# Page setup + styling (shared across every page in the app)
# --------------------------------------------------------------------------- #

st.set_page_config(page_title="Enterprise Data Agent", page_icon="📊", layout="centered")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2.5rem; max-width: 880px; }

    .app-header { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.15rem; }
    .app-header .icon { font-size: 2rem; line-height: 1; }
    .app-header h1 { margin: 0; font-size: 1.7rem; font-weight: 700; }
    .app-subtitle { color: var(--text-color, #6b7280); opacity: 0.85; margin-bottom: 1.6rem; font-size: 0.95rem; }

    div[data-testid="stMetric"] {
        background: rgba(99, 102, 241, 0.06);
        border: 1px solid rgba(99, 102, 241, 0.15);
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
    }

    .agent-badge {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.35rem;
        background: rgba(99, 102, 241, 0.14);
        color: rgb(99, 102, 241);
    }
    .source-chip {
        display: inline-block;
        padding: 0.12rem 0.55rem;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 600;
        background: rgba(16, 185, 129, 0.12);
        color: rgb(5, 150, 105);
        margin-bottom: 0.35rem;
    }

    /* Sidebar example-question chips */
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
        text-align: left;
        justify-content: flex-start;
        white-space: normal;
        line-height: 1.35;
        font-size: 0.85rem;
        padding: 0.55rem 0.7rem;
        border-radius: 10px;
        border: 1px solid rgba(127, 127, 127, 0.25);
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        border-color: rgb(99, 102, 241);
        color: rgb(99, 102, 241);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def _render_result(result: dict) -> None:
    st.write(result["answer"])

    badges = " ".join(f'<span class="agent-badge">{t}</span>' for t in result["tools_used"])
    if badges:
        st.markdown(badges, unsafe_allow_html=True)

    cols = st.columns(4)
    cols[0].metric("Confidence", f"{result['confidence']:.2f}")
    cols[1].metric("Retries", result["retry_count"])
    cols[2].metric("Validation", "✅ Passed" if result["validation_passed"] else "❌ Failed")
    cols[3].metric("Latency", f"{result.get('latency_ms', 0):.0f} ms")

    if result.get("reasoning"):
        with st.expander("🧭 Routing reasoning", expanded=False):
            st.write(result["reasoning"])

    if result.get("generated_sql"):
        with st.expander("🗄️ Generated SQL"):
            st.code(result["generated_sql"], language="sql")

    if result.get("retrieved_sources"):
        with st.expander(f"📄 Retrieved sources ({len(result['retrieved_sources'])})"):
            for src in result["retrieved_sources"]:
                st.markdown(f'<span class="source-chip">{src["source"]}</span>', unsafe_allow_html=True)
                st.caption(src["excerpt"])
                st.divider()

    with st.expander("✅ Validation result"):
        st.write(result["validation_result"])

    if result.get("node_latencies_ms"):
        with st.expander("⏱️ Latency breakdown"):
            st.bar_chart(result["node_latencies_ms"])

    with st.expander("Raw JSON response"):
        st.json(result)


def _ask_and_store(question: str) -> bool:
    """Runs the agent for `question` and appends the turn to session history.

    Returns True on success. Renders its own error and returns False on failure,
    rather than raising, so callers (form submit vs. example-question buttons) don't
    need to duplicate error handling.
    """
    with st.spinner("Thinking..."):
        try:
            result, _mode_used = ask_agent(question)
        except requests.RequestException as exc:
            st.error(f"Failed to reach the agent API: {exc}")
            return False
        except Exception as exc:  # noqa: BLE001
            st.error(f"The agent failed to answer: {exc}")
            return False

    st.session_state["history"].append({"question": question, "result": result})
    return True


def render_ask_page() -> None:
    st.session_state.setdefault("history", [])

    st.markdown(
        '<div class="app-header"><span class="icon">📊</span>'
        "<h1>Self-Correcting Enterprise Data Agent</h1></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="app-subtitle">Ask a business question — the agent decides whether to query the '
        "database, retrieve policy documents, or both, then validates its own answer and retries "
        "once automatically if needed.</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("#### 💡 Try an example")
        st.caption("Click a question to ask it directly.")
        for icon, q in EXAMPLE_QUESTIONS:
            # Runs the question immediately on click rather than pre-filling the text
            # box: writing into a `st.text_input`'s session_state from a *different*
            # widget's callback, on a form that also uses clear_on_submit, is a known
            # source of stale/ignored values in Streamlit once the form has already
            # been submitted once. Running directly here sidesteps that entirely.
            if st.button(f"{icon}  {q}", key=f"ex_{hash(q)}", width='stretch'):
                _ask_and_store(q)
                st.rerun()

        st.divider()
        st.markdown("#### 🧠 Session memory")
        st.caption(f"{len(st.session_state['history'])} question(s) this session.")
        if st.button("🗑️ Clear session memory", width='stretch', disabled=not st.session_state["history"]):
            st.session_state["history"] = []
            st.rerun()

        st.divider()
        st.markdown("#### ⚙️ Backend")
        mode_label = {
            "api": f"FastAPI backend\n{API_BASE_URL}",
            "direct": "In-process (standalone)",
            "auto": "Auto (API → standalone fallback)",
        }[AGENT_MODE]
        st.code(mode_label, language="text")
        if st.session_state.get("force_direct_mode"):
            st.caption("⚠️ Backend unreachable — running standalone this session.")

    # Replay this session's conversation so far.
    for turn in st.session_state["history"]:
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            _render_result(turn["result"])

    # A form so Enter submits directly (no Ctrl+Enter, no separate "click to enable
    # the button" step). clear_on_submit resets the input for the next question,
    # since answered questions now persist above as session memory.
    with st.form("ask_form", clear_on_submit=True):
        question = st.text_input(
            "Your question",
            key="question_input",
            placeholder="Ask about orders, customers, refunds, escalation... (press Enter to ask)",
        )
        ask_clicked = st.form_submit_button("Ask", type="primary", width='stretch')

    if ask_clicked and not question.strip():
        st.warning("Type a question first.")

    if ask_clicked and question.strip():
        if _ask_and_store(question):
            st.rerun()


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #

pg = st.navigation(
    [
        st.Page(render_ask_page, title="Ask", icon="💬", default=True),
        st.Page(render_architecture_page, title="Architecture & Tech Stack", icon="🏗️"),
    ]
)
pg.run()
