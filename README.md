# GenAI Agent Projects

A collection of GenAI / LLM agent applications — each subfolder is a self-contained project with its own README, dependencies, and history preserved from its original repo.

## Projects

- **[self_deciding_interprise_agent](self_deciding_interprise_agent/)** — A GenAI agent that takes a natural-language business question, decides whether it needs SQL, document retrieval, or both, executes the chosen tool(s), validates the answer against retrieved evidence, and retries once on failure. Built with LangGraph, Groq, FAISS/HuggingFace embeddings, FastAPI, and Streamlit.
- **[Yaseen_coding_task_01_medical_assistant](Yaseen_coding_task_01_medical_assistant/)** — A RAG app that answers medical questions strictly from a fixed set of clinical documents, with citations, refusing to answer outside that corpus. Built with Groq, a custom vector store, FastAPI, and Streamlit.
- **[refund-return-ai-agent](refund-return-ai-agent/)** — A multi-agent customer service system that verifies customers/orders, deterministically gates refund eligibility (not LLM-guessed), searches a policy knowledge base, and emails the decision — orchestrated via a LangGraph supervisor with a live-streaming Streamlit chat UI. Runs entirely on free-tier Groq + local embeddings.
