import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..database import Base


class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    flagged = "flagged"


class VerdictStatus(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    flagged = "flagged"
    needs_review = "needs_review"


class FileType(str, enum.Enum):
    pdf = "pdf"
    image = "image"
    txt = "txt"


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, nullable=False, index=True)  # "NW-04821"
    name = Column(String, nullable=False)
    grade = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    department = Column(String, nullable=False)
    manager_id = Column(String, nullable=True)   # "NW-03012"
    home_base = Column(String, nullable=True)

    submissions = relationship("Submission", back_populates="employee")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    status = Column(SAEnum(SubmissionStatus), default=SubmissionStatus.pending, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    total_amount = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    trip_purpose = Column(Text, nullable=True)
    trip_dates = Column(String, nullable=True)
    source_folder = Column(String, nullable=True, unique=True)  # e.g. "01_clean_denver"

    employee = relationship("Employee", back_populates="submissions")
    receipts = relationship("Receipt", back_populates="submission", cascade="all, delete-orphan")
    overrides = relationship("Override", back_populates="submission", cascade="all, delete-orphan")

    @property
    def employee_name(self):
        return self.employee.name if self.employee else None

    @property
    def employee_nw_id(self):
        return self.employee.employee_id if self.employee else None


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(SAEnum(FileType), nullable=False)
    extracted_text = Column(Text, nullable=True)
    amount = Column(Float, nullable=True)
    vendor = Column(String, nullable=True)
    receipt_date = Column(String, nullable=True)
    category = Column(String, nullable=True)

    submission = relationship("Submission", back_populates="receipts")
    verdicts = relationship("LineItemVerdict", back_populates="receipt", cascade="all, delete-orphan")


class LineItemVerdict(Base):
    __tablename__ = "line_item_verdicts"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    verdict = Column(SAEnum(VerdictStatus), nullable=False)
    policy_citations = Column(Text, nullable=True)  # JSON-serialised list[str]
    reason = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)

    receipt = relationship("Receipt", back_populates="verdicts")


class Override(Base):
    __tablename__ = "overrides"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    overridden_by = Column(String, nullable=False)
    original_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    submission = relationship("Submission", back_populates="overrides")
