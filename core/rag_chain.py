"""
core/rag_chain.py
─────────────────
LangChain RAG chain for the YouTube chatbot.

Uses query-aware retrieval:
  - Summary/overview → MMR retrieval (20 diverse chunks, chronological)
  - Specific Q&A     → Similarity retrieval (8 focused chunks)
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config.settings import get_settings
from core.retriever import retrieve_chunks, is_summary_query

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

_SUMMARY_SYSTEM = """\
You are an expert video analyst, educator, and subject matter expert. 
Your job is to produce a profound, highly detailed, and insightful summary of a YouTube video based on its transcript.
Do not just provide a surface-level overview. Extract the true meaning, nuances, and underlying principles.

RULES:
1. Use ONLY the transcript excerpts provided. Do not add outside knowledge.
2. Provide a DEEP and COMPREHENSIVE explanation. Break down complex ideas so anyone can understand them.
3. Structure your answer using markdown headers (##), bullet points, and bold text for emphasis.
4. Your summary MUST include:
   - **Executive Summary:** A profound paragraph explaining the core thesis or main purpose of the video.
   - **Deep Dive into Key Concepts:** Explain the *why* and *how* behind the main points, not just the *what*.
   - **Important Examples & Analogies:** Detail any specific stories, examples, or data used to prove points.
   - **Actionable Takeaways:** What should the viewer learn or do with this information?
5. If the transcript excerpts lack enough context, explicitly state what is missing.
6. Adopt an engaging, educational, and conversational tone.

Transcript excerpts (chronological order):
───────────────────────────────────────────
{context}
───────────────────────────────────────────
"""

_QA_SYSTEM = """\
You are an expert educator answering questions based on a YouTube video transcript.

RULES:
1. Answer ONLY using information found in the transcript excerpts below.
2. If the answer is not in the transcript, respond EXACTLY with:
   "I couldn't find this information in the uploaded video."
3. Do NOT hallucinate, speculate, or add outside knowledge.
4. Provide a THOROUGH, NUANCED, and DEEP answer. Do not just give one sentence if more detail is available.
5. Explain concepts clearly. If the user asks for a deep dive or explanation, break it down logically.
6. Quote or paraphrase directly from the transcript when relevant.

Transcript excerpts:
───────────────────────────────────────────
{context}
───────────────────────────────────────────
"""

_HUMAN = "{question}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_docs(docs: list[Document], include_timestamps: bool = True) -> str:
    """Format retrieved docs into a readable context block."""
    if not docs:
        return "No transcript content available."
    parts = []
    for doc in docs:
        if include_timestamps:
            ts = doc.metadata.get("start_formatted", "?")
            parts.append(f"[{ts}] {doc.page_content}")
        else:
            parts.append(doc.page_content)
    return "\n\n".join(parts)


def _make_llm(max_tokens: int = 1024):
    """Create a fresh ChatGroq instance from current settings."""
    from langchain_groq import ChatGroq

    settings = get_settings()
    logger.info("Creating Groq LLM: %s (max_tokens=%d)", settings.llm_model, max_tokens)

    return ChatGroq(
        model=settings.llm_model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        max_tokens=max_tokens,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def run_rag_query(
    question: str,
    video_id: str,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Run a query-aware RAG pipeline.

    Parameters
    ----------
    question : str
        User's natural language question.
    video_id : str
        YouTube video ID to scope retrieval.

    Returns
    -------
    dict with:
        "answer"           : str
        "source_documents" : list[Document]
        "is_summary"       : bool
    """
    settings = get_settings()
    summarizing = is_summary_query(question)

    logger.info(
        "RAG query | video=%s | summary=%s | question=%r",
        video_id, summarizing, question,
    )

    # ── Step 1: Retrieve chunks ───────────────────────────────────────────────
    source_docs = retrieve_chunks(question=question, video_id=video_id)

    if not source_docs:
        return {
            "answer": settings.fallback_message,
            "source_documents": [],
            "is_summary": summarizing,
        }

    # ── Step 2: Build context ─────────────────────────────────────────────────
    context = _format_docs(source_docs, include_timestamps=True)
    logger.info(
        "Context built: %d chunks, %d chars total.",
        len(source_docs), len(context),
    )

    # ── Step 3: Choose prompt and token budget ────────────────────────────────
    if summarizing:
        system_prompt = _SUMMARY_SYSTEM
        max_tokens = 2048  # Summaries need more room
    else:
        system_prompt = _QA_SYSTEM
        max_tokens = 1024

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", _HUMAN),
    ])

    # ── Step 4: Parse chat history ────────────────────────────────────────────
    formatted_history = []
    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                formatted_history.append(HumanMessage(content=content))
            elif role == "assistant":
                formatted_history.append(AIMessage(content=content))

    # ── Step 5: Generate answer ───────────────────────────────────────────────
    llm = _make_llm(max_tokens=max_tokens)
    chain = prompt | llm | StrOutputParser()

    answer: str = chain.invoke({
        "context": context,
        "chat_history": formatted_history,
        "question": question,
    })

    if not answer or not answer.strip():
        answer = settings.fallback_message

    logger.info(
        "Answer generated | summary=%s | chars=%d",
        summarizing, len(answer),
    )

    return {
        "answer": answer,
        "source_documents": source_docs,
        "is_summary": summarizing,
    }
