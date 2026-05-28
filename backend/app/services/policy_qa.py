"""
Policy Q&A service — RAG-based chatbot over the indexed policy documents.

Flow:
  1. Embed the question with the same model used at index time
  2. Query Pinecone (no category filter — question may span multiple policy areas)
  3. Send question + retrieved chunks to Claude
  4. Claude answers using only the provided excerpts, with citations
"""

import logging

import anthropic
from pinecone import Index
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
_embed_model: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info("Loading embedding model for policy Q&A")
        _embed_model = SentenceTransformer(_EMBED_MODEL_NAME)
    return _embed_model


# ── Pinecone retrieval ────────────────────────────────────────────────────────

def _retrieve_chunks(question: str, pinecone_index: Index, top_k: int = 8) -> list:
    vector = _get_embed_model().encode(question).tolist()
    results = pinecone_index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
    )
    return results.matches


def _format_chunks(matches: list) -> str:
    if not matches:
        return "No policy excerpts found."
    lines: list[str] = []
    for m in matches:
        meta = m.metadata
        citation = (
            f"{meta.get('doc_id', '?')} §{meta.get('section_number', '?')}: "
            f"{meta.get('section_heading', '')}"
        )
        lines.append(f"[{citation}  relevance={m.score:.3f}]")
        lines.append(meta.get("text", ""))
        lines.append("")
    return "\n".join(lines)


# ── Claude tool ───────────────────────────────────────────────────────────────

_QA_TOOL: dict = {
    "name": "submit_answer",
    "description": "Submit the answer to the policy question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_in_scope": {
                "type": "boolean",
                "description": (
                    "True if the question is about Northwind expense, travel, conduct, "
                    "records, security, or sustainability policies. "
                    "False if the question is off-topic or unrelated to company policy."
                ),
            },
            "answer": {
                "type": "string",
                "description": (
                    "A clear, direct answer grounded in the policy excerpts provided. "
                    "If not in scope, politely say so without guessing. "
                    "If in scope but the excerpts don't contain enough detail, say what "
                    "you found and note what's unclear."
                ),
            },
            "citations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Policy references used in the answer, e.g. ['TEP-002 §4.2: Meal caps by grade and city tier'].",
            },
        },
        "required": ["is_in_scope", "answer", "citations"],
    },
}

_SYSTEM_PROMPT = (
    "You are a policy assistant for Northwind Logistics. "
    "You answer questions about the company's expense, travel, code of conduct, "
    "records retention, security, and sustainability policies. "
    "Answer only from the policy excerpts provided — do not make up rules or dollar amounts. "
    "If the excerpts don't contain enough detail to answer fully, say what you found and "
    "flag what's unclear. If the question is unrelated to company policy, say so politely. "
    "Always cite the specific policy section your answer comes from."
)


# ── Public API ────────────────────────────────────────────────────────────────

def answer_question(
    question: str,
    pinecone_index: Index,
    anthropic_client: anthropic.Anthropic,
) -> dict:
    """
    Returns {"answer": str, "citations": list[str], "is_in_scope": bool}.
    """
    matches = _retrieve_chunks(question, pinecone_index)
    context = _format_chunks(matches)

    prompt = (
        f"## Question\n{question}\n\n"
        f"## Policy Excerpts\n{context}\n\n"
        "Answer the question using only the excerpts above. "
        "Use the submit_answer tool to record your response."
    )

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[_QA_TOOL],
        tool_choice={"type": "tool", "name": "submit_answer"},
    )

    tool_input: dict = {}
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_answer":
            tool_input = block.input
            break

    return {
        "answer": tool_input.get("answer", "Unable to generate an answer."),
        "citations": tool_input.get("citations", []),
        "is_in_scope": tool_input.get("is_in_scope", False),
    }
