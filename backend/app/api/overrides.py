from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models.db_models import Override, Submission
from ..models.schemas import OverrideCreate, OverrideRead

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/submissions/{submission_id}/override", response_model=OverrideRead, status_code=201)
def create_override(submission_id: int, payload: OverrideCreate, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

    override = Override(
        submission_id=submission_id,
        overridden_by=payload.overridden_by,
        original_status=sub.status.value,
        new_status=payload.new_status.value,
        reason=payload.reason,
    )
    sub.status = payload.new_status
    sub.reviewed_at = datetime.utcnow()

    db.add(override)
    db.commit()
    db.refresh(override)
    return override


@router.get("/submissions/{submission_id}/overrides", response_model=list[OverrideRead])
def list_overrides(submission_id: int, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")
    return sub.overrides
