from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import SessionLocal
from ..models.db_models import Employee, Submission, SubmissionStatus
from ..models.schemas import SubmissionCreate, SubmissionDetail, SubmissionRead, SubmissionStatusUpdate

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[SubmissionRead])
def list_submissions(
    status: Optional[SubmissionStatus] = Query(None, description="Filter by status"),
    employee_id: Optional[str] = Query(None, description="Filter by NW-XXXXX employee ID"),
    db: Session = Depends(get_db),
):
    q = db.query(Submission).options(joinedload(Submission.employee))
    if status:
        q = q.filter(Submission.status == status)
    if employee_id:
        emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
        if not emp:
            raise HTTPException(status_code=404, detail=f"Employee {employee_id!r} not found")
        q = q.filter(Submission.employee_id == emp.id)
    return q.order_by(Submission.submitted_at.desc()).all()


@router.get("/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: int, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")
    return sub


@router.post("/", response_model=SubmissionRead, status_code=201)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee id={payload.employee_id} not found")
    sub = Submission(**payload.model_dump())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.patch("/{submission_id}/status", response_model=SubmissionRead)
def update_status(submission_id: int, payload: SubmissionStatusUpdate, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")
    sub.status = payload.status
    sub.reviewed_at = datetime.utcnow()
    if payload.notes is not None:
        sub.notes = payload.notes
    db.commit()
    db.refresh(sub)
    return sub
