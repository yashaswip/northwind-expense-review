"""Grounded policy Q&A with out-of-scope refusal."""

from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.schemas import PolicyCitation, PolicyChatResponse
from app.services.policy_index import policy_index
from app.services.reviewer import _validate_citations

OUT_OF_SCOPE_HINTS = [
    "weather",
    "stock price",
    "recipe",
    "who won",
    "write me code",
    "personal advice",
]


class PolicyChatService:
    def __init__(self):
        self._client = (
            OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    def ask(self, question: str) -> PolicyChatResponse:
        q_lower = question.lower().strip()
        if any(h in q_lower for h in OUT_OF_SCOPE_HINTS):
            return PolicyChatResponse(
                answer="",
                citations=[],
                refused=True,
                refusal_reason=(
                    "This question appears outside the Northwind policy library. "
                    "I can only answer questions grounded in company policies."
                ),
            )

        chunks = policy_index.retrieve(question, top_k=10)
        if not chunks:
            return PolicyChatResponse(
                answer="",
                citations=[],
                refused=True,
                refusal_reason="Policy index is empty or unavailable.",
            )

        max_sim = max(c["similarity"] for c in chunks)
        if max_sim < settings.min_retrieval_score:
            return PolicyChatResponse(
                answer="",
                citations=[],
                refused=True,
                refusal_reason=(
                    "I could not find sufficiently relevant policy content to answer "
                    "confidently. Please rephrase or ask your manager."
                ),
            )

        if not self._client:
            return PolicyChatResponse(
                answer="Policy chat requires OPENAI_API_KEY.",
                citations=[],
                refused=True,
                refusal_reason="API not configured",
            )

        policy_block = "\n\n---\n\n".join(
            f"[{c['doc_id']} §{c['section']}]\n{c['text']}" for c in chunks
        )

        resp = self._client.chat.completions.create(
            model=settings.openai_review_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer ONLY using the provided policy excerpts. "
                        "If the question is not about company policies, set refused=true. "
                        "Quotes in citations must be verbatim from excerpts."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "policy_excerpts": policy_block}
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "policy_answer",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string"},
                            "refused": {"type": "boolean"},
                            "refusal_reason": {"type": ["string", "null"]},
                            "citations": {
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
                        "required": ["answer", "refused", "citations"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            temperature=0.1,
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
        if raw.get("refused"):
            return PolicyChatResponse(
                answer="",
                citations=[],
                refused=True,
                refusal_reason=raw.get("refusal_reason")
                or "Question outside policy scope.",
            )

        citations = [
            PolicyCitation(
                document_id=c["document_id"],
                section=c.get("section"),
                quote=c["quote"],
            )
            for c in raw.get("citations", [])
        ]
        validated = _validate_citations(citations, chunks)

        return PolicyChatResponse(
            answer=raw.get("answer", ""),
            citations=validated,
            refused=False,
        )


policy_chat = PolicyChatService()
