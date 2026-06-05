from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import SubmissionStatus, Verdict


class EmployeeCreate(BaseModel):
    employee_id: str
    name: str
    grade: int
    title: str
    department: str
    manager_id: str
    home_base: str


class EmployeeOut(EmployeeCreate):
    id: int
    seeded: bool

    class Config:
        from_attributes = True


class SubmissionCreate(BaseModel):
    employee_id: int
    trip_purpose: str
    trip_dates: str
    notes: str | None = None


class PolicyCitation(BaseModel):
    document_id: str
    section: str | None = None
    quote: str


class LineItemOut(BaseModel):
    id: int
    receipt_id: int
    filename: str
    category: str
    vendor: str | None
    expense_date: str | None
    amount: float | None
    currency: str
    description: str | None
    verdict: Verdict
    effective_verdict: Verdict
    confidence: float
    reasoning: str
    policy_citations: list[PolicyCitation]
    has_override: bool
    overrides: list["OverrideOut"] = []

    class Config:
        from_attributes = True


class OverrideCreate(BaseModel):
    new_verdict: Verdict
    comment: str
    reviewer: str = "finance_reviewer"


class OverrideOut(BaseModel):
    id: int
    previous_verdict: Verdict
    new_verdict: Verdict
    comment: str
    reviewer: str
    created_at: datetime

    class Config:
        from_attributes = True


class SubmissionSummary(BaseModel):
    id: int
    employee_name: str
    employee_code: str
    trip_purpose: str
    trip_dates: str
    status: SubmissionStatus
    line_count: int
    flagged_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class SubmissionDetail(BaseModel):
    id: int
    employee: EmployeeOut
    trip_purpose: str
    trip_dates: str
    status: SubmissionStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    line_items: list[LineItemOut]


class PolicyChatRequest(BaseModel):
    question: str


class PolicyChatResponse(BaseModel):
    answer: str
    citations: list[PolicyCitation]
    refused: bool
    refusal_reason: str | None = None


class HealthResponse(BaseModel):
    status: str
    policies_indexed: int
    openai_configured: bool
