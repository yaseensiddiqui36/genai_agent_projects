"""Shared Groq LLM client."""

from __future__ import annotations

from functools import lru_cache

from langchain_groq import ChatGroq

from infinite_coding_round.config import settings


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.0) -> ChatGroq:
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=temperature,
    )
