import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from .db_models import FileType, SubmissionStatus, VerdictStatus


# ── Employee ──────────────────────────────────────────────────────────────────

class EmployeeBase(BaseModel):
    employee_id: str
    name: str
    grade: int
    title: str
    department: str
    manager_id: Optional[str] = None
    home_base: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeRead(EmployeeBase):
    id: int

    model_config = {"from_attributes": True}


# ── Submission ────────────────────────────────────────────────────────────────

class SubmissionCreate(BaseModel):
    employee_id: int
    trip_purpose: Optional[str] = None
    trip_dates: Optional[str] = None


class SubmissionStatusUpdate(BaseModel):
    status: SubmissionStatus
    notes: Optional[str] = None


class SubmissionRead(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    employee_nw_id: Optional[str] = None
    status: SubmissionStatus
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    total_amount: float
    notes: Optional[str] = None
    trip_purpose: Optional[str] = None
    trip_dates: Optional[str] = None
    source_folder: Optional[str] = None

    model_config = {"from_attributes": True}


class SubmissionDetail(SubmissionRead):
    employee: EmployeeRead
    receipts: list["ReceiptDetail"] = []
    overrides: list["OverrideRead"] = []


# ── Receipt ───────────────────────────────────────────────────────────────────

class ReceiptRead(BaseModel):
    id: int
    submission_id: int
    filename: str
    file_type: FileType
    extracted_text: Optional[str] = None
    amount: Optional[float] = None
    vendor: Optional[str] = None
    receipt_date: Optional[str] = None
    category: Optional[str] = None

    model_config = {"from_attributes": True}


class ReceiptDetail(ReceiptRead):
    verdicts: list["LineItemVerdictRead"] = []


# ── LineItemVerdict ───────────────────────────────────────────────────────────

class LineItemVerdictRead(BaseModel):
    id: int
    receipt_id: int
    description: str
    amount: float
    verdict: VerdictStatus
    policy_citations: list[str] = []
    reason: str
    confidence: Optional[float] = None

    model_config = {"from_attributes": True}

    @field_validator("policy_citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []


# ── Override ──────────────────────────────────────────────────────────────────

class OverrideCreate(BaseModel):
    submission_id: int
    overridden_by: str
    new_status: SubmissionStatus
    reason: str


class OverrideRead(BaseModel):
    id: int
    submission_id: int
    overridden_by: str
    original_status: str
    new_status: str
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Policy Q&A ────────────────────────────────────────────────────────────────

class PolicyQARequest(BaseModel):
    question: str


class PolicyQAResponse(BaseModel):
    answer: str
    citations: list[str]
    is_in_scope: bool


# Resolve forward references
SubmissionDetail.model_rebuild()
ReceiptDetail.model_rebuild()
