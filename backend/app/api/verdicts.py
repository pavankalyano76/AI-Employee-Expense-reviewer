from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models.db_models import Submission
from ..models.schemas import SubmissionDetail
from ..services.verdict_engine import review_submission

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/submissions/{submission_id}/review", response_model=SubmissionDetail)
def trigger_review(submission_id: int, request: Request, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")
    if not sub.receipts:
        raise HTTPException(status_code=422, detail="Submission has no receipts to review")

    review_submission(
        sub,
        db,
        pinecone_index=request.app.state.pinecone_index,
        anthropic_client=request.app.state.anthropic_client,
    )
    db.refresh(sub)
    return sub
