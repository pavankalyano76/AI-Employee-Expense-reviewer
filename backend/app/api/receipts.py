import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models.db_models import FileType, Receipt, Submission
from ..models.schemas import ReceiptDetail, ReceiptRead
from ..services.receipt_extractor import extract_receipt

router = APIRouter()

_ACCEPTED_EXTENSIONS = {".pdf", ".txt", ".jpg", ".jpeg", ".png", ".gif", ".webp"}

_EXT_TO_FILE_TYPE: dict[str, FileType] = {
    ".pdf":  FileType.pdf,
    ".txt":  FileType.txt,
    ".jpg":  FileType.image,
    ".jpeg": FileType.image,
    ".png":  FileType.image,
    ".gif":  FileType.image,
    ".webp": FileType.image,
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/submissions/{submission_id}/receipts", response_model=list[ReceiptRead])
def list_receipts(submission_id: int, db: Session = Depends(get_db)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")
    return sub.receipts


@router.post("/submissions/{submission_id}/receipts", response_model=ReceiptRead, status_code=201)
async def upload_receipt(
    request: Request,
    submission_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} not found")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ACCEPTED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported file type '{suffix}'. "
                "Accepted: PDF, JPG, PNG, GIF, WEBP, TXT"
            ),
        )

    upload_dir: Path = settings.upload_dir / str(submission_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    anthropic_client = getattr(request.app.state, "anthropic_client", None)
    data = extract_receipt(dest, anthropic_client=anthropic_client)

    receipt = Receipt(
        submission_id=submission_id,
        filename=file.filename,
        file_path=str(dest),
        file_type=_EXT_TO_FILE_TYPE[suffix],
        extracted_text=data.extracted_text,
        amount=data.amount,
        vendor=data.vendor,
        receipt_date=data.receipt_date,
        category=data.category,
    )
    db.add(receipt)

    existing_total = sum(r.amount or 0.0 for r in sub.receipts)
    sub.total_amount = round(existing_total + (data.amount or 0.0), 2)

    db.commit()
    db.refresh(receipt)
    return receipt


@router.get("/receipts/{receipt_id}", response_model=ReceiptDetail)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail=f"Receipt {receipt_id} not found")
    return receipt
