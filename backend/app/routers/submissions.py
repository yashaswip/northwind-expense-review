import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    AuditEvent,
    Employee,
    LineItem,
    Override,
    Receipt,
    Submission,
    SubmissionStatus,
    Verdict,
)
from app.schemas import (
    LineItemOut,
    OverrideCreate,
    OverrideOut,
    PolicyCitation,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionSummary,
)
from app.services.receipt_parser import receipt_parser
from app.services.reviewer import expense_reviewer

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def _upload_root() -> Path:
    p = settings.resolve_path(settings.upload_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _line_item_out(item: LineItem) -> LineItemOut:
    citations = json.loads(item.policy_citations or "[]")
    overrides = sorted(item.overrides, key=lambda o: o.created_at)
    effective = overrides[-1].new_verdict if overrides else item.verdict
    return LineItemOut(
        id=item.id,
        receipt_id=item.receipt_id,
        filename=item.receipt.filename,
        category=item.category,
        vendor=item.vendor,
        expense_date=item.expense_date,
        amount=item.amount,
        currency=item.currency,
        description=item.description,
        verdict=item.verdict,
        effective_verdict=effective,
        confidence=item.confidence,
        reasoning=item.reasoning,
        policy_citations=[PolicyCitation(**c) for c in citations],
        has_override=len(overrides) > 0,
        overrides=[OverrideOut.model_validate(o) for o in overrides],
    )


@router.get("", response_model=list[SubmissionSummary])
def list_submissions(
    db: Session = Depends(get_db),
    employee_id: int | None = None,
    status: SubmissionStatus | None = None,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
):
    q = db.query(Submission).options(
        joinedload(Submission.employee),
        joinedload(Submission.receipts).joinedload(Receipt.line_item),
    )
    if employee_id:
        q = q.filter(Submission.employee_id == employee_id)
    if status:
        q = q.filter(Submission.status == status)
    rows = q.order_by(Submission.created_at.desc()).all()
    out: list[SubmissionSummary] = []
    for s in rows:
        if from_date and s.created_at.isoformat()[:10] < from_date:
            continue
        if to_date and s.created_at.isoformat()[:10] > to_date:
            continue
        items = [r.line_item for r in s.receipts if r.line_item]
        flagged = sum(
            1
            for i in items
            if (i.overrides[-1].new_verdict if i.overrides else i.verdict)
            in (Verdict.flagged, Verdict.rejected, Verdict.needs_review)
        )
        out.append(
            SubmissionSummary(
                id=s.id,
                employee_name=s.employee.name,
                employee_code=s.employee.employee_id,
                trip_purpose=s.trip_purpose,
                trip_dates=s.trip_dates,
                status=s.status,
                line_count=len(items),
                flagged_count=flagged,
                created_at=s.created_at,
            )
        )
    return out


@router.post("", response_model=SubmissionDetail, status_code=201)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)):
    emp = db.get(Employee, payload.employee_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    sub = Submission(
        employee_id=payload.employee_id,
        trip_purpose=payload.trip_purpose,
        trip_dates=payload.trip_dates,
        notes=payload.notes,
        status=SubmissionStatus.draft,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return get_submission(sub.id, db)


@router.get("/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: int, db: Session = Depends(get_db)):
    sub = (
        db.query(Submission)
        .options(
            joinedload(Submission.employee),
            joinedload(Submission.receipts).joinedload(Receipt.line_item).joinedload(
                LineItem.overrides
            ),
        )
        .filter(Submission.id == submission_id)
        .first()
    )
    if not sub:
        raise HTTPException(404, "Submission not found")
    line_items = []
    for r in sorted(sub.receipts, key=lambda x: x.filename):
        if r.line_item:
            line_items.append(_line_item_out(r.line_item))
    from app.schemas import EmployeeOut

    return SubmissionDetail(
        id=sub.id,
        employee=EmployeeOut.model_validate(sub.employee),
        trip_purpose=sub.trip_purpose,
        trip_dates=sub.trip_dates,
        status=sub.status,
        notes=sub.notes,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        line_items=line_items,
    )


@router.post("/{submission_id}/receipts")
async def upload_receipts(
    submission_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(404, "Submission not found")
    dest_dir = _upload_root() / str(submission_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        ext = Path(f.filename or "receipt").suffix or ".bin"
        name = f"{uuid.uuid4().hex}{ext}"
        path = dest_dir / name
        with path.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        rec = Receipt(
            submission_id=submission_id,
            filename=f.filename or name,
            mime_type=f.content_type or "application/octet-stream",
            stored_path=str(path),
        )
        db.add(rec)
        saved.append(rec.filename)
    db.commit()
    return {"uploaded": saved, "count": len(saved)}


@router.post("/{submission_id}/load-sample")
def load_sample_receipts(
    submission_id: int,
    folder: str = Query(..., description="Sample folder name under data/submissions"),
    db: Session = Depends(get_db),
):
    sub = db.get(Submission, submission_id)
    if not sub:
        raise HTTPException(404, "Submission not found")
    seed_dir = settings.resolve_path(settings.submissions_seed_dir) / folder / "receipts"
    if not seed_dir.is_dir():
        raise HTTPException(404, f"Sample folder not found: {folder}")
    dest_dir = _upload_root() / str(submission_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(seed_dir.iterdir()):
        if not src.is_file():
            continue
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        mime = "application/pdf"
        if src.suffix.lower() in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        elif src.suffix.lower() == ".png":
            mime = "image/png"
        elif src.suffix.lower() == ".txt":
            mime = "text/plain"
        db.add(
            Receipt(
                submission_id=submission_id,
                filename=src.name,
                mime_type=mime,
                stored_path=str(dest),
            )
        )
        copied.append(src.name)
    db.commit()
    return {"copied": copied, "count": len(copied)}


@router.post("/{submission_id}/review", response_model=SubmissionDetail)
def run_review(submission_id: int, db: Session = Depends(get_db)):
    sub = (
        db.query(Submission)
        .options(joinedload(Submission.employee), joinedload(Submission.receipts))
        .filter(Submission.id == submission_id)
        .first()
    )
    if not sub:
        raise HTTPException(404, "Submission not found")
    if not sub.receipts:
        raise HTTPException(400, "Upload receipts before running review")

    sub.status = SubmissionStatus.processing
    db.commit()

    ctx = {
        "employee_id": sub.employee.employee_id,
        "name": sub.employee.name,
        "grade": sub.employee.grade,
        "department": sub.employee.department,
        "trip_purpose": sub.trip_purpose,
        "trip_dates": sub.trip_dates,
    }

    try:
        for rec in sub.receipts:
            path = Path(rec.stored_path)
            if not path.exists():
                raise HTTPException(400, f"Receipt file missing: {rec.filename}")
            extracted, text = receipt_parser.parse(path, rec.mime_type)
            rec.extracted_text = text

            review = expense_reviewer.review_line(text, extracted, ctx)
            if rec.line_item:
                db.delete(rec.line_item)
                db.flush()

            item = LineItem(
                receipt_id=rec.id,
                category=extracted.category,
                vendor=extracted.vendor,
                expense_date=extracted.expense_date,
                amount=extracted.amount,
                currency=extracted.currency or "USD",
                description=extracted.description or extracted.raw_summary,
                verdict=review.verdict,
                confidence=review.confidence,
                reasoning=review.reasoning,
                policy_citations=json.dumps(
                    [c.model_dump() for c in review.policy_citations]
                ),
            )
            db.add(item)
    except HTTPException:
        raise
    except Exception as e:
        sub.status = SubmissionStatus.error
        db.commit()
        raise HTTPException(500, f"Review failed: {e}") from e

    sub.status = SubmissionStatus.reviewed
    sub.updated_at = datetime.utcnow()
    db.add(
        AuditEvent(
            entity_type="submission",
            entity_id=submission_id,
            action="review_completed",
            payload=json.dumps({"receipt_count": len(sub.receipts)}),
        )
    )
    db.commit()
    return get_submission(submission_id, db)


@router.post("/line-items/{line_item_id}/override", response_model=LineItemOut)
def override_line_item(
    line_item_id: int,
    payload: OverrideCreate,
    db: Session = Depends(get_db),
):
    item = (
        db.query(LineItem)
        .options(
            joinedload(LineItem.receipt),
            joinedload(LineItem.overrides),
        )
        .filter(LineItem.id == line_item_id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Line item not found")

    previous = item.overrides[-1].new_verdict if item.overrides else item.verdict
    ov = Override(
        line_item_id=line_item_id,
        previous_verdict=previous,
        new_verdict=payload.new_verdict,
        comment=payload.comment,
        reviewer=payload.reviewer,
    )
    db.add(ov)
    db.add(
        AuditEvent(
            entity_type="line_item",
            entity_id=line_item_id,
            action="override",
            payload=json.dumps(
                {
                    "previous": previous.value,
                    "new": payload.new_verdict.value,
                    "comment": payload.comment,
                    "reviewer": payload.reviewer,
                }
            ),
        )
    )
    db.commit()
    db.refresh(item)
    return _line_item_out(item)
