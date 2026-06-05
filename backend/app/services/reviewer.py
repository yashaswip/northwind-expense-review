"""LLM policy review with retrieval-grounded citations."""

from __future__ import annotations

import json

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.models import Verdict
from app.schemas import PolicyCitation
from app.services.policy_index import policy_index
from app.services.receipt_parser import ExtractedReceipt


class ReviewResult(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    policy_citations: list[PolicyCitation] = Field(default_factory=list)


REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["compliant", "flagged", "rejected", "needs_review"],
        },
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
        "policy_citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "section": {"type": ["string", "null"]},
                    "quote": {"type": "string"},
                },
                "required": ["document_id", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "confidence", "reasoning", "policy_citations"],
    "additionalProperties": False,
}


def _validate_citations(
    citations: list[PolicyCitation], chunks: list[dict]
) -> list[PolicyCitation]:
    """Drop citations whose quote does not appear in retrieved policy text."""
    corpus = " ".join(c["text"].lower() for c in chunks)
    valid: list[PolicyCitation] = []
    for c in citations:
        quote = c.quote.strip()
        if len(quote) < 12:
            continue
        needle = quote.lower()[:80]
        if needle in corpus or any(
            needle[:40] in chunk["text"].lower() for chunk in chunks
        ):
            valid.append(c)
    return valid


class ExpenseReviewer:
    def __init__(self):
        self._client = (
            OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    def review_line(
        self,
        receipt_text: str,
        extracted: ExtractedReceipt,
        employee_context: dict,
    ) -> ReviewResult:
        query = (
            f"{extracted.category} {extracted.vendor or ''} "
            f"${extracted.amount or 0} {extracted.description or ''} "
            f"{employee_context.get('trip_purpose', '')} "
            f"solo travel grade {employee_context.get('grade', '')}"
        )
        chunks = policy_index.retrieve(query)
        max_sim = max((c["similarity"] for c in chunks), default=0.0)

        if not self._client:
            return ReviewResult(
                verdict=Verdict.needs_review,
                confidence=0.0,
                reasoning="OpenAI API key not configured; manual review required.",
                policy_citations=[],
            )

        if not chunks or max_sim < settings.min_retrieval_score:
            return ReviewResult(
                verdict=Verdict.needs_review,
                confidence=min(0.4, max_sim),
                reasoning=(
                    "Insufficient policy context retrieved for a confident automated "
                    "verdict. A human reviewer should apply the relevant policy."
                ),
                policy_citations=[],
            )

        policy_block = "\n\n---\n\n".join(
            f"[{c['doc_id']} §{c['section']}] ({c['source_file']}, sim={c['similarity']:.2f})\n{c['text']}"
            for c in chunks
        )

        user_payload = {
            "employee": employee_context,
            "extracted_line_item": extracted.model_dump(),
            "receipt_text": receipt_text[:8000],
            "retrieved_policies": policy_block,
        }

        resp = self._client.chat.completions.create(
            model=settings.openai_review_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Northwind Logistics finance pre-reviewer. "
                        "Compare the expense line item against ONLY the retrieved policy excerpts. "
                        "Consider trip context (solo vs client entertainment, conference, etc.).\n"
                        "Verdicts:\n"
                        "- compliant: clearly allowed\n"
                        "- flagged: likely issue or needs documentation\n"
                        "- rejected: clear policy violation\n"
                        "- needs_review: ambiguous or weak policy match\n\n"
                        "Rules:\n"
                        "- Every policy_citations.quote MUST be copied verbatim from retrieved_policies\n"
                        "- Reference document IDs like TEP-002 §2.1\n"
                        "- Lower confidence when evidence is indirect\n"
                        "- Solo travel + alcohol on same receipt → typically reject alcohol portion per TEP-003\n"
                        "- Dinner over per-meal cap → flag or reject based on policy\n"
                    ),
                },
                {"role": "user", "content": json.dumps(user_payload, indent=2)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "expense_review",
                    "schema": REVIEW_SCHEMA,
                    "strict": True,
                },
            },
            temperature=0.1,
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
        citations = [
            PolicyCitation(
                document_id=c["document_id"],
                section=c.get("section"),
                quote=c["quote"],
            )
            for c in raw.get("policy_citations", [])
        ]
        validated = _validate_citations(citations, chunks)
        confidence = float(raw.get("confidence", 0.5))
        if len(validated) < len(citations):
            confidence = min(confidence, 0.55)
        if not validated and raw.get("verdict") in ("compliant", "rejected"):
            return ReviewResult(
                verdict=Verdict.needs_review,
                confidence=min(confidence, 0.45),
                reasoning=raw.get("reasoning", "")
                + " (Automated citations could not be verified against retrieved text.)",
                policy_citations=[],
            )

        return ReviewResult(
            verdict=Verdict(raw["verdict"]),
            confidence=confidence,
            reasoning=raw.get("reasoning", ""),
            policy_citations=validated,
        )


expense_reviewer = ExpenseReviewer()
