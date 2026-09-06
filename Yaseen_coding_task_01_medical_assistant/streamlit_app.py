import streamlit as st

from src.search import RAGSearch

SAMPLE_QUESTIONS = [
    "How is the mental health of adults in the USA?",
    "What lifestyle changes are recommended to manage Type 2 diabetes?",
    "What blood pressure target is recommended for adults with hypertension?",
    "How can seasonal influenza be prevented?",
    "What is the recommended dosage of trastuzumab for HER2-positive breast cancer?",
]

st.set_page_config(page_title="Clinical Knowledge Assistant", page_icon="🩺", layout="centered")


@st.cache_resource(show_spinner="Loading vector store and LLM...")
def get_rag_search() -> RAGSearch:
    return RAGSearch()


if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("Settings")
    top_k = st.slider("Chunks to retrieve (top_k)", min_value=1, max_value=20, value=5)

    st.divider()
    if st.button("Clear conversation"):
        st.session_state.history = []
        st.rerun()

st.title("🩺 Clinical Knowledge Assistant")
st.caption(
    "Ask questions about the sample clinical corpus (mental health, hypertension, "
    "type 2 diabetes, seasonal influenza, cardiovascular risk factors). Answers are "
    "grounded strictly in retrieved context."
)

try:
    rag = get_rag_search()
except Exception as exc:
    st.error(f"Failed to initialize RAG pipeline: {exc}")
    st.stop()

with st.expander("Sample questions to try"):
    for sample in SAMPLE_QUESTIONS:
        if st.button(sample, key=sample):
            st.session_state.pending_question = sample

for turn in st.session_state.history:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.write(turn["answer"])
        if turn["sources"]:
            with st.expander(f"Sources ({len(turn['sources'])})"):
                for src in turn["sources"]:
                    page = f", page {src['page']}" if src.get("page") is not None else ""
                    st.markdown(f"**{src['source']}**{page} — distance `{src['distance']}`")
                    st.text(src["snippet"])
        st.caption(f"Latency: {turn['latency_seconds']}s")

typed_question = st.chat_input("Ask a question about the document corpus...")
question = typed_question or st.session_state.pop("pending_question", None)

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving and generating answer..."):
            try:
                result = rag.search_and_summarize(question, top_k=top_k)
            except Exception as exc:
                st.error(f"Failed to answer question: {exc}")
                st.stop()

        st.write(result["answer"])
        if result["sources"]:
            with st.expander(f"Sources ({len(result['sources'])})"):
                for src in result["sources"]:
                    page = f", page {src['page']}" if src.get("page") is not None else ""
                    st.markdown(f"**{src['source']}**{page} — distance `{src['distance']}`")
                    st.text(src["snippet"])
        st.caption(f"Latency: {result['latency_seconds']}s")

    st.session_state.history.append(
        {
            "question": question,
            "answer": result["answer"],
            "sources": result["sources"],
            "latency_seconds": result["latency_seconds"],
        }
    )
