"""
Verdict engine — Phase 6.

For each receipt: query Pinecone for relevant policy chunks → call Claude via tool use
→ store LineItemVerdict.  One verdict per receipt.
"""

import json
import logging
from datetime import datetime

import anthropic
from pinecone import Index
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from ..models.db_models import (
    LineItemVerdict,
    Receipt,
    Submission,
    SubmissionStatus,
    VerdictStatus,
)

logger = logging.getLogger(__name__)

# ── Embedding model (lazy singleton) ─────────────────────────────────────────

_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
_embed_model: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info("Loading embedding model for verdict engine")
        _embed_model = SentenceTransformer(_EMBED_MODEL_NAME)
    return _embed_model


# ── Pinecone retrieval ────────────────────────────────────────────────────────

_CATEGORY_QUERY: dict[str, str] = {
    "flight":     "air travel flight booking economy business class approval reimbursement",
    "hotel":      "hotel accommodation lodging per night rate limit reimbursement",
    "meal":       "meal dining per diem food beverage alcohol entertainment limit",
    "transport":  "ground transportation rideshare taxi cab reimbursement",
    "conference": "conference registration training external event professional development",
    "other":      "expense reimbursement approval policy",
}


def _query_policy_context(category: str, employee_grade: int, pinecone_index: Index) -> list:
    base_query = _CATEGORY_QUERY.get(category, _CATEGORY_QUERY["other"])
    query = f"{base_query} employee grade {employee_grade}"

    model = _get_embed_model()
    vector = model.encode(query).tolist()

    results = pinecone_index.query(
        vector=vector,
        top_k=6,
        include_metadata=True,
        filter={"category": "travel_expense"},
    )
    return results.matches


def _format_policy_context(matches: list) -> str:
    if not matches:
        return "No specific policy excerpts found."
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


# ── Claude tool definition ────────────────────────────────────────────────────

_VERDICT_TOOL: dict = {
    "name": "submit_verdict",
    "description": "Submit the policy compliance verdict for this expense receipt.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["approved", "flagged", "needs_review"],
                "description": (
                    "approved = clearly within policy; "
                    "flagged = non-compliant or likely violation — requires human review, do NOT outright reject; "
                    "needs_review = insufficient information to make a determination"
                ),
            },
            "description": {
                "type": "string",
                "description": "One-line description of the expense (e.g. 'Economy flight LAX→DEN, $324.20').",
            },
            "reason": {
                "type": "string",
                "description": "Explanation citing specific policy rules and amounts.",
            },
            "policy_citations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Policy references, e.g. ['TEP-001 §4.1: Economy class default'].",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence in this verdict (0 = very uncertain, 1 = certain).",
            },
        },
        "required": ["verdict", "description", "reason", "policy_citations", "confidence"],
    },
}

_SYSTEM_PROMPT = (
    "You are a corporate expense policy compliance reviewer for Northwind Logistics. "
    "Your role is to review expense receipts against company policy and provide a recommendation — "
    "you do NOT have the authority to reject claims. Final decisions rest with the employee's manager. "
    "Use 'approved' when an expense is clearly within policy. "
    "Use 'flagged' when an expense appears non-compliant or questionable — explain exactly why and cite "
    "the specific policy sections violated so the manager can make an informed decision. "
    "Use 'needs_review' when there is insufficient information to assess compliance. "
    "Always be precise: cite specific policy sections, note exact dollar limits, and consider the "
    "employee's grade level when evaluating per-meal caps, hotel rates, and travel class entitlements."
)


def _build_user_prompt(
    receipt: Receipt,
    employee,
    submission: Submission,
    policy_context: str,
) -> str:
    return (
        f"## Employee\n"
        f"- Name: {employee.name}\n"
        f"- Employee ID: {employee.employee_id}\n"
        f"- Grade: {employee.grade}\n"
        f"- Title: {employee.title}\n"
        f"- Department: {employee.department}\n"
        f"- Trip Purpose: {submission.trip_purpose or 'Not specified'}\n"
        f"- Trip Dates: {submission.trip_dates or 'Not specified'}\n\n"
        f"## Receipt\n"
        f"- Vendor: {receipt.vendor or 'Unknown'}\n"
        f"- Category: {receipt.category}\n"
        f"- Amount: ${receipt.amount or 0:.2f}\n"
        f"- Date: {receipt.receipt_date or 'Unknown'}\n"
        f"- File: {receipt.filename}\n\n"
        f"## Full Receipt Text\n"
        f"{receipt.extracted_text or 'No text extracted.'}\n\n"
        f"## Relevant Policy Excerpts\n"
        f"{policy_context}"
    )


# ── Core review functions ─────────────────────────────────────────────────────

def review_receipt(
    receipt: Receipt,
    employee,
    submission: Submission,
    pinecone_index: Index,
    anthropic_client: anthropic.Anthropic,
) -> LineItemVerdict:
    """
    Review a single receipt. Returns an unsaved LineItemVerdict — caller commits.
    """
    matches = _query_policy_context(receipt.category, employee.grade, pinecone_index)
    policy_context = _format_policy_context(matches)
    prompt = _build_user_prompt(receipt, employee, submission, policy_context)

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[_VERDICT_TOOL],
        tool_choice={"type": "tool", "name": "submit_verdict"},
    )

    tool_input: dict = {}
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_verdict":
            tool_input = block.input
            break

    return LineItemVerdict(
        receipt_id=receipt.id,
        description=tool_input.get("description", receipt.vendor or receipt.filename),
        amount=receipt.amount or 0.0,
        verdict=VerdictStatus(tool_input.get("verdict", "needs_review")),
        policy_citations=json.dumps(tool_input.get("policy_citations", [])),
        reason=tool_input.get("reason", ""),
        confidence=float(tool_input.get("confidence", 0.0)),
    )


def _aggregate_status(verdicts: list[LineItemVerdict]) -> SubmissionStatus:
    statuses = {v.verdict for v in verdicts}
    if VerdictStatus.flagged in statuses or VerdictStatus.needs_review in statuses:
        return SubmissionStatus.flagged
    return SubmissionStatus.approved


def review_submission(
    submission: Submission,
    db: Session,
    pinecone_index: Index,
    anthropic_client: anthropic.Anthropic,
) -> list[LineItemVerdict]:
    """
    Review all receipts in a submission.
    Replaces any existing verdicts, then updates submission.status and reviewed_at.
    """
    employee = submission.employee
    new_verdicts: list[LineItemVerdict] = []

    for receipt in submission.receipts:
        # Replace existing verdicts for this receipt
        db.query(LineItemVerdict).filter_by(receipt_id=receipt.id).delete()

        logger.info(
            "Reviewing receipt %d: %s ($%.2f)",
            receipt.id, receipt.filename, receipt.amount or 0,
        )
        verdict = review_receipt(receipt, employee, submission, pinecone_index, anthropic_client)
        db.add(verdict)
        new_verdicts.append(verdict)
        logger.info("  → %s (confidence=%.2f)", verdict.verdict, verdict.confidence or 0)

    db.flush()

    submission.status = _aggregate_status(new_verdicts)
    submission.reviewed_at = datetime.utcnow()
    db.commit()

    logger.info(
        "Submission %d review complete — status=%s  (%d receipts)",
        submission.id, submission.status, len(new_verdicts),
    )
    return new_verdicts
