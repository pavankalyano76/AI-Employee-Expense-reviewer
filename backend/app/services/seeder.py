"""
Startup seeder — populates the employees table from the on-disk submission JSONs.

Each submission folder contains an employee_info.json with per-trip employee data.
We deduplicate by employee_id so re-running is idempotent.
"""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from ..models.db_models import Employee, FileType, Receipt, Submission
from .receipt_extractor import extract_receipt

logger = logging.getLogger(__name__)


def seed_employees(db: Session, submissions_dir: Path) -> int:
    """
    Read every employee_info.json under submissions_dir, insert unique employees.
    Returns the count of newly inserted rows (0 if already seeded).
    """
    json_files = sorted(submissions_dir.glob("*/employee_info.json"))
    if not json_files:
        logger.warning("No employee_info.json files found under %s", submissions_dir)
        return 0

    seen: set[str] = set()
    inserted = 0

    for json_path in json_files:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        emp_id: str = data["employee_id"]

        if emp_id in seen:
            continue
        seen.add(emp_id)

        exists = db.query(Employee).filter_by(employee_id=emp_id).first()
        if exists:
            logger.debug("Employee %s already in DB — skipping", emp_id)
            continue

        employee = Employee(
            employee_id=emp_id,
            name=data["name"],
            grade=data["grade"],
            title=data["title"],
            department=data["department"],
            manager_id=data.get("manager_id"),
            home_base=data.get("home_base"),
        )
        db.add(employee)
        inserted += 1
        logger.info("Seeded employee %s (%s)", emp_id, data["name"])

    if inserted:
        db.commit()

    return inserted


def seed_submissions(db: Session, submissions_dir: Path) -> int:
    """
    Create one Submission row per folder under submissions_dir.
    Links each submission to the correct Employee via employee_id from employee_info.json.
    Deduplicates by source_folder so re-running is idempotent.
    Returns the count of newly inserted rows.
    """
    folders = sorted(p for p in submissions_dir.iterdir() if p.is_dir())
    if not folders:
        logger.warning("No submission folders found under %s", submissions_dir)
        return 0

    inserted = 0

    for folder in folders:
        json_path = folder / "employee_info.json"
        if not json_path.exists():
            logger.warning("No employee_info.json in %s — skipping", folder.name)
            continue

        source_folder = folder.name
        exists = db.query(Submission).filter_by(source_folder=source_folder).first()
        if exists:
            logger.debug("Submission for %s already in DB — skipping", source_folder)
            continue

        data = json.loads(json_path.read_text(encoding="utf-8"))
        emp_id: str = data["employee_id"]

        employee = db.query(Employee).filter_by(employee_id=emp_id).first()
        if not employee:
            logger.warning("Employee %s not found — skipping submission %s", emp_id, source_folder)
            continue

        submission = Submission(
            employee_id=employee.id,
            trip_purpose=data.get("trip_purpose"),
            trip_dates=data.get("trip_dates"),
            source_folder=source_folder,
        )
        db.add(submission)
        inserted += 1
        logger.info("Seeded submission %s for %s (%s)", source_folder, emp_id, data["name"])

    if inserted:
        db.commit()

    return inserted


def seed_receipts(db: Session, submissions_dir: Path) -> int:
    """
    For every submission already in the DB, find its folder, extract each receipt PDF,
    and insert a Receipt row. Idempotent — skips PDFs that are already recorded.
    Also updates submission.total_amount with the sum of receipt amounts.
    Returns the count of newly inserted rows.
    """
    submissions = db.query(Submission).all()
    inserted = 0

    for sub in submissions:
        if not sub.source_folder:
            continue

        receipts_dir = submissions_dir / sub.source_folder / "receipts"
        if not receipts_dir.exists():
            logger.warning("Receipts dir not found: %s", receipts_dir)
            continue

        pdf_files = sorted(receipts_dir.glob("*.pdf"))
        sub_total = 0.0

        for pdf_path in pdf_files:
            already = db.query(Receipt).filter_by(
                submission_id=sub.id,
                filename=pdf_path.name,
            ).first()
            if already:
                sub_total += already.amount or 0.0
                continue

            data = extract_receipt(pdf_path)

            receipt = Receipt(
                submission_id=sub.id,
                filename=pdf_path.name,
                file_path=str(pdf_path),
                file_type=FileType.pdf,
                extracted_text=data.extracted_text,
                amount=data.amount,
                vendor=data.vendor,
                receipt_date=data.receipt_date,
                category=data.category,
            )
            db.add(receipt)
            sub_total += data.amount or 0.0
            inserted += 1
            logger.info("  Seeded receipt %s (%.2f)", pdf_path.name, data.amount or 0.0)

        sub.total_amount = round(sub_total, 2)

    if inserted:
        db.commit()

    return inserted
