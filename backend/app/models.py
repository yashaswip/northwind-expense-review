import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SubmissionStatus(str, enum.Enum):
    draft = "draft"
    processing = "processing"
    reviewed = "reviewed"
    error = "error"


class Verdict(str, enum.Enum):
    compliant = "compliant"
    flagged = "flagged"
    rejected = "rejected"
    needs_review = "needs_review"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    grade: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    department: Mapped[str] = mapped_column(String(128))
    manager_id: Mapped[str] = mapped_column(String(32))
    home_base: Mapped[str] = mapped_column(String(128))
    seeded: Mapped[bool] = mapped_column(default=False)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="employee")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    trip_purpose: Mapped[str] = mapped_column(Text)
    trip_dates: Mapped[str] = mapped_column(String(64))
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus), default=SubmissionStatus.draft
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    employee: Mapped["Employee"] = relationship(back_populates="submissions")
    receipts: Mapped[list["Receipt"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    filename: Mapped[str] = mapped_column(String(256))
    mime_type: Mapped[str] = mapped_column(String(128))
    stored_path: Mapped[str] = mapped_column(String(512))
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    submission: Mapped["Submission"] = relationship(back_populates="receipts")
    line_item: Mapped["LineItem | None"] = relationship(
        back_populates="receipt", uselist=False, cascade="all, delete-orphan"
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), unique=True)
    category: Mapped[str] = mapped_column(String(64))
    vendor: Mapped[str | None] = mapped_column(String(256), nullable=True)
    expense_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    reasoning: Mapped[str] = mapped_column(Text)
    policy_citations: Mapped[str] = mapped_column(Text)  # JSON array
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    receipt: Mapped["Receipt"] = relationship(back_populates="line_item")
    overrides: Mapped[list["Override"]] = relationship(
        back_populates="line_item", cascade="all, delete-orphan"
    )


class Override(Base):
    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    line_item_id: Mapped[int] = mapped_column(ForeignKey("line_items.id"))
    previous_verdict: Mapped[Verdict] = mapped_column(Enum(Verdict))
    new_verdict: Mapped[Verdict] = mapped_column(Enum(Verdict))
    comment: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(128), default="finance_reviewer")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    line_item: Mapped["LineItem"] = relationship(back_populates="overrides")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
