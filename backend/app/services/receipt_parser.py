"""Extract structured line-item data from receipts (PDF, image, text)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from openai import OpenAI
from pdfplumber import open as pdf_open
from pydantic import BaseModel, Field

from app.config import settings


class ExtractedReceipt(BaseModel):
    vendor: str | None = None
    expense_date: str | None = None
    amount: float | None = None
    currency: str = "USD"
    category: str = Field(
        description="One of: air_travel, lodging, ground_transport, meals, conference, other"
    )
    description: str | None = None
    raw_summary: str | None = None


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": ["string", "null"]},
        "expense_date": {"type": ["string", "null"]},
        "amount": {"type": ["number", "null"]},
        "currency": {"type": "string"},
        "category": {
            "type": "string",
            "enum": [
                "air_travel",
                "lodging",
                "ground_transport",
                "meals",
                "conference",
                "other",
            ],
        },
        "description": {"type": ["string", "null"]},
        "raw_summary": {"type": ["string", "null"]},
    },
    "required": [
        "vendor",
        "expense_date",
        "amount",
        "currency",
        "category",
        "description",
        "raw_summary",
    ],
    "additionalProperties": False,
}


def _read_pdf_text(path: Path) -> str:
    parts: list[str] = []
    with pdf_open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _read_plain(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def extract_text_from_file(path: Path, mime: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf" or "pdf" in mime:
        return _read_pdf_text(path)
    if suffix in {".txt"} or "text" in mime:
        return _read_plain(path)
    return ""


class ReceiptParser:
    def __init__(self):
        self._client = (
            OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    def parse(self, path: Path, mime: str) -> tuple[ExtractedReceipt, str]:
        text = extract_text_from_file(path, mime)
        if text and len(text) > 30:
            extracted = self._structure_from_text(text)
            return extracted, text

        if not self._client:
            return (
                ExtractedReceipt(category="other", description="Unable to parse"),
                text or "",
            )

        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} or "image" in mime:
            extracted, summary = self._parse_vision(path)
            return extracted, summary or text

        if path.suffix.lower() == ".pdf" and not text:
            extracted, summary = self._parse_vision(path, as_pdf=True)
            return extracted, summary or text

        return (
            ExtractedReceipt(
                category="other",
                description=text[:500] if text else "Empty receipt",
            ),
            text,
        )

    def _structure_from_text(self, text: str) -> ExtractedReceipt:
        if not self._client:
            return ExtractedReceipt(category="other", raw_summary=text[:500])
        resp = self._client.chat.completions.create(
            model=settings.openai_review_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract expense line-item fields from receipt text. "
                        "Use GRAND TOTAL or Total as amount when present."
                    ),
                },
                {"role": "user", "content": text[:12000]},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "receipt_extraction",
                    "schema": EXTRACTION_SCHEMA,
                    "strict": True,
                },
            },
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        return ExtractedReceipt(**data)

    def _parse_vision(self, path: Path, as_pdf: bool = False) -> tuple[ExtractedReceipt, str]:
        b64 = base64.standard_b64encode(path.read_bytes()).decode()
        suffix = path.suffix.lower().lstrip(".")
        media = "application/pdf" if as_pdf else f"image/{'jpeg' if suffix == 'jpg' else suffix}"
        content = [
            {
                "type": "text",
                "text": "Extract all expense fields from this receipt image/document.",
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:{media};base64,{b64}"},
            },
        ]
        resp = self._client.chat.completions.create(
            model=settings.openai_vision_model,
            messages=[{"role": "user", "content": content}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "receipt_extraction",
                    "schema": EXTRACTION_SCHEMA,
                    "strict": True,
                },
            },
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        extracted = ExtractedReceipt(**data)
        summary = extracted.raw_summary or extracted.description or ""
        return extracted, summary


receipt_parser = ReceiptParser()
