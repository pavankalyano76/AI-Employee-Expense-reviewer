"""
Receipt extraction supporting PDF, image (via Claude Vision), and plain-text files.

Vendor   — first non-separator line in the text.
Amount   — last line containing "total" + a dollar figure (covers GRAND TOTAL, Total Charged, etc.).
Date     — first recognisable date pattern found in the text.
Category — inferred from filename keywords.
"""

import base64
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

# ── Category map (filename keyword → category) ────────────────────────────────

_FILENAME_CATEGORY: list[tuple[list[str], str]] = [
    (["airlines", "flight", "delta", "united", "american", "southwest", "alaska", "jetblue"], "flight"),
    (["conference", "registration", "summit", "expo"], "conference"),
    (["uber", "lyft", "taxi", "transport", "cab", "shuttle"], "transport"),
    (["dinner", "lunch", "breakfast", "restaurant", "cafe", "bistro", "food", "bar", "grill"], "meal"),
    (["marriott", "hilton", "hyatt", "hotel", "sheraton", "westin", "courtyard"], "hotel"),
]

# ── Regex patterns ─────────────────────────────────────────────────────────────

_AMOUNT_RE      = re.compile(r'\$([\d,]+\.\d{2})')
_SEPARATOR_RE   = re.compile(r'^[=\-\s]+$')
_TOTAL_LINE_RE  = re.compile(r'(?:grand\s+)?total[\s\w]*\$[\d,]+\.\d{2}', re.IGNORECASE)

_DATE_PATTERNS: list[re.Pattern] = [
    re.compile(r'\d{4}-\d{2}-\d{2}'),
    re.compile(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+\d{1,2}\s+\w+\s+\d{4}'),
    re.compile(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+\w+\s+\d{1,2},?\s+\d{4}'),
    re.compile(r'\d{1,2}\s+\w+\s+\d{4}'),
    re.compile(r'\w+\s+\d{1,2},\s+\d{4}'),
    re.compile(r'\d{1,2}/\d{1,2}/\d{4}'),
]

_IMAGE_MEDIA_TYPES: dict[str, str] = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
}

_IMAGE_EXTENSIONS = set(_IMAGE_MEDIA_TYPES.keys())


# ── Field parsers ─────────────────────────────────────────────────────────────

def _infer_category(filename: str) -> str:
    name_lower = re.sub(r'[_.]', ' ', filename.lower())
    for keywords, category in _FILENAME_CATEGORY:
        if any(re.search(rf'\b{re.escape(kw)}\b', name_lower) for kw in keywords):
            return category
    return "other"


def _parse_vendor(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line and not _SEPARATOR_RE.match(line):
            return line[:120]
    return None


def _parse_amount(text: str) -> float | None:
    total_lines = [ln for ln in text.splitlines() if _TOTAL_LINE_RE.search(ln)]
    search_text = total_lines[-1] if total_lines else text
    matches = _AMOUNT_RE.findall(search_text)
    if not matches:
        all_amounts = _AMOUNT_RE.findall(text)
        if not all_amounts:
            return None
        return max(float(m.replace(",", "")) for m in all_amounts)
    return max(float(m.replace(",", "")) for m in matches)


def _parse_date(text: str) -> str | None:
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0).strip()
    return None


# ── Per-format extractors ─────────────────────────────────────────────────────

def _extract_pdf(file_path: Path) -> "ReceiptData":
    with pdfplumber.open(file_path) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]
    full_text = "\n".join(pages_text).strip()
    return ReceiptData(
        extracted_text=full_text,
        vendor=_parse_vendor(full_text),
        amount=_parse_amount(full_text),
        receipt_date=_parse_date(full_text),
        category=_infer_category(file_path.name),
    )


def _extract_text_file(file_path: Path) -> "ReceiptData":
    full_text = file_path.read_text(encoding="utf-8", errors="replace").strip()
    return ReceiptData(
        extracted_text=full_text,
        vendor=_parse_vendor(full_text),
        amount=_parse_amount(full_text),
        receipt_date=_parse_date(full_text),
        category=_infer_category(file_path.name),
    )


def _extract_image(file_path: Path, anthropic_client) -> "ReceiptData":
    media_type = _IMAGE_MEDIA_TYPES.get(file_path.suffix.lower(), "image/jpeg")
    image_data = base64.standard_b64encode(file_path.read_bytes()).decode("utf-8")

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        tools=[{
            "name": "extract_receipt_fields",
            "description": "Extract structured data from a receipt image",
            "input_schema": {
                "type": "object",
                "properties": {
                    "vendor":    {"type": "string",  "description": "Business / vendor name on the receipt"},
                    "amount":    {"type": "number",  "description": "Total amount charged in USD (numeric, no $ symbol)"},
                    "date":      {"type": "string",  "description": "Date of purchase; use YYYY-MM-DD format if possible"},
                    "full_text": {"type": "string",  "description": "All text visible in the receipt, verbatim"},
                },
                "required": ["full_text"],
            },
        }],
        tool_choice={"type": "tool", "name": "extract_receipt_fields"},
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": "Extract all text and key fields from this expense receipt.",
                },
            ],
        }],
    )

    fields: dict = {}
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_receipt_fields":
            fields = block.input
            break

    full_text = fields.get("full_text", "")
    raw_amount = fields.get("amount")
    try:
        amount = float(raw_amount) if raw_amount is not None else _parse_amount(full_text)
    except (ValueError, TypeError):
        amount = _parse_amount(full_text)

    return ReceiptData(
        extracted_text=full_text,
        vendor=fields.get("vendor") or _parse_vendor(full_text),
        amount=amount,
        receipt_date=fields.get("date") or _parse_date(full_text),
        category=_infer_category(file_path.name),
    )


# ── Public API ────────────────────────────────────────────────────────────────

@dataclass
class ReceiptData:
    extracted_text: str
    vendor: str | None
    amount: float | None
    receipt_date: str | None
    category: str


def extract_receipt(file_path: Path, anthropic_client=None) -> ReceiptData:
    """
    Extract structured data from a receipt file.

    Supported formats: .pdf, .txt, .jpg, .jpeg, .png, .gif, .webp
    Images require an Anthropic client (Claude Vision).
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_path)

    if suffix == ".txt":
        return _extract_text_file(file_path)

    if suffix in _IMAGE_EXTENSIONS:
        if anthropic_client is None:
            raise ValueError(
                "An Anthropic client must be provided to extract data from image receipts."
            )
        return _extract_image(file_path, anthropic_client)

    raise ValueError(
        f"Unsupported receipt file type: {suffix!r}. "
        "Accepted: .pdf, .txt, .jpg, .jpeg, .png, .gif, .webp"
    )
