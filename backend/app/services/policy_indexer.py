"""
Policy indexer — Phase 2.

Chunking: hierarchical (doc → numbered sections) + semantic (sentence-similarity breakpoints).
Metadata: doc-level fields extracted from each PDF header + section-level fields per chunk.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pdfplumber
from pinecone import Index
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_EMBED_MODEL = "all-MiniLM-L6-v2"  # 384-dim; must match Pinecone index dimension
_UPSERT_BATCH = 100
_BREAKPOINT_PERCENTILE = 85  # similarity below (100 - this) percentile → new chunk
_MIN_CHUNK_CHARS = 80        # chunks shorter than this are merged into their neighbour

# doc_id prefix → retrieval category
_CATEGORY_MAP: dict[str, str] = {
    "TEP": "travel_expense",
    "COC": "code_of_conduct",
    "REC": "records_retention",
    "SEC": "security",
    "SUS": "sustainability",
}


# ── Document-level metadata ────────────────────────────────────────────────────

@dataclass
class DocMeta:
    source: str
    doc_id: str
    doc_title: str
    category: str
    version: str
    effective_date: str
    owner: str
    applies_to: str


_HEADER_RE = re.compile(
    r"Document:\s*(?P<doc_id>\S+)\s+"
    r"Version:\s*(?P<version>[\d.]+)\s+"
    r"Effective Date:\s*(?P<effective_date>[A-Za-z0-9 ,]+?)\s+"
    r"Owner:\s*(?P<owner>.+?)(?=\s+Applies To:|\n\d+\.|\Z)",
    re.DOTALL,
)
# "Applies To:" may appear on its own line OR inline after Owner on same line
_APPLIES_TO_RE = re.compile(r"Applies To:\s*(.+?)(?=\n\d+\.|\Z)", re.DOTALL)
_DATE_CLEAN_RE = re.compile(
    r"(?P<month>January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})"
)
_MONTH_MAP = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}


def _iso_date(raw: str) -> str:
    m = _DATE_CLEAN_RE.search(raw.strip())
    if not m:
        return raw.strip()
    return f"{m.group('year')}-{_MONTH_MAP[m.group('month')]}-{int(m.group('day')):02d}"


def _extract_doc_meta(pdf_path: Path, first_page_text: str) -> DocMeta:
    # Normalise line-broken "Applies\nTo:" that some PDFs produce
    first_page_text = re.sub(r"Applies\s*\n\s*To:", "Applies To:", first_page_text)

    lines = [ln.strip() for ln in first_page_text.splitlines() if ln.strip()]
    doc_title = lines[0] if lines else pdf_path.stem

    header_m = _HEADER_RE.search(first_page_text)
    if not header_m:
        return DocMeta(
            source=pdf_path.name, doc_id="UNKNOWN", doc_title=doc_title,
            category="general", version="", effective_date="", owner="", applies_to="",
        )

    doc_id = header_m.group("doc_id")
    version = header_m.group("version")
    effective_date = _iso_date(header_m.group("effective_date"))
    owner = " ".join(header_m.group("owner").split())  # collapse newlines

    applies_to_m = _APPLIES_TO_RE.search(first_page_text)
    applies_to = " ".join(applies_to_m.group(1).split()) if applies_to_m else ""

    prefix = re.match(r"[A-Z]+", doc_id)
    category = _CATEGORY_MAP.get(prefix.group() if prefix else "", "general")

    return DocMeta(
        source=pdf_path.name,
        doc_id=doc_id,
        doc_title=doc_title,
        category=category,
        version=version,
        effective_date=effective_date,
        owner=owner,
        applies_to=applies_to,
    )


# ── Hierarchical splitting: full text → sections ───────────────────────────────

@dataclass
class Section:
    number: str          # "2.1"
    heading: str         # "Class of service"
    body: str            # paragraph / body text


# Matches numbered items: "1.", "2.1.", "3.2.4" etc. at the start of a line
_SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*\.?)\s+(.+)", re.MULTILINE)


def _split_into_sections(text: str) -> list[Section]:
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return [Section(number="", heading="", body=text.strip())]

    sections: list[Section] = []

    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(Section(number="", heading="", body=preamble))

    for i, m in enumerate(matches):
        sec_num = m.group(1).rstrip(".")
        first_line = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        continuation = text[body_start:body_end].strip()

        # Standalone heading: short line with no mid-sentence period → heading only, body follows
        # Inline paragraph: content starts immediately on the same line
        if len(first_line) <= 60 and not re.search(r"\.\s+[A-Za-z]", first_line):
            heading = first_line
            body = continuation
        else:
            # Inline: first phrase (up to first period) is the heading; rest is body
            phrase = re.match(r"^(.{5,60}?[.!?])\s", first_line)
            heading = phrase.group(1).rstrip(".") if phrase else first_line[:60]
            body = first_line + (" " + continuation if continuation else "")

        if body.strip():
            sections.append(Section(number=sec_num, heading=heading, body=body.strip()))

    return sections


# ── Sentence splitting ─────────────────────────────────────────────────────────

_SENT_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\d])")


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in _SENT_END_RE.split(text) if s.strip()]


# ── Semantic chunking within a section ────────────────────────────────────────

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def _semantic_chunk(
    sentences: list[str],
    embeddings: np.ndarray,
    percentile: int = _BREAKPOINT_PERCENTILE,
    min_chars: int = _MIN_CHUNK_CHARS,
) -> list[str]:
    if len(sentences) == 1:
        return sentences

    sims = [
        _cosine_sim(embeddings[i], embeddings[i + 1])
        for i in range(len(embeddings) - 1)
    ]
    threshold = float(np.percentile(sims, 100 - percentile))
    breakpoints = {i + 1 for i, s in enumerate(sims) if s < threshold}

    raw: list[str] = []
    current: list[str] = []
    for i, sent in enumerate(sentences):
        if i in breakpoints and current:
            raw.append(" ".join(current))
            current = []
        current.append(sent)
    if current:
        raw.append(" ".join(current))

    # Merge chunks that are too short
    merged: list[str] = []
    for chunk in raw:
        if merged and len(chunk) < min_chars:
            merged[-1] = merged[-1] + " " + chunk
        else:
            merged.append(chunk)

    return merged


# ── Main entry point ──────────────────────────────────────────────────────────

def _split_into_sub_documents(pdf_path: Path, full_text: str) -> list[tuple["DocMeta", str]]:
    """Split a multi-TEP PDF into (DocMeta, text) pairs, one per Document: header.

    Each sub-document begins at the title line immediately preceding 'Document: XXX'.
    """
    lines = full_text.splitlines()
    boundary_indices: list[int] = []

    for i, line in enumerate(lines):
        if re.match(r"Document:\s*\S+\s+Version:", line.strip()):
            # Include the title line just before the Document: header
            start = max(0, i - 1)
            boundary_indices.append(start)

    if not boundary_indices:
        return [(_extract_doc_meta(pdf_path, full_text), full_text)]

    segments: list[str] = []
    for j, start in enumerate(boundary_indices):
        end = boundary_indices[j + 1] if j + 1 < len(boundary_indices) else len(lines)
        seg = "\n".join(lines[start:end]).strip()
        if seg:
            segments.append(seg)

    result = []
    for seg in segments:
        meta = _extract_doc_meta(pdf_path, seg)
        result.append((meta, seg))

    return result if result else [(_extract_doc_meta(pdf_path, full_text), full_text)]


def index_policies(pinecone_index: Index, policies_dir: Path, force: bool = False) -> int:
    pdf_files = sorted(
        p for p in policies_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )
    if not pdf_files:
        logger.warning("No PDF files found in %s", policies_dir)
        return 0

    if force:
        logger.info("Force re-index: deleting all existing vectors")
        pinecone_index.delete(delete_all=True)

    logger.info("Loading embedding model: %s", _EMBED_MODEL)
    model = SentenceTransformer(_EMBED_MODEL)

    all_vectors: list[dict] = []
    global_chunk_idx = 0

    for pdf_path in pdf_files:
        logger.info("Indexing: %s", pdf_path.name)

        with pdfplumber.open(pdf_path) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]

        full_text = "\n".join(pages)
        sub_docs = _split_into_sub_documents(pdf_path, full_text)
        logger.info("  %d sub-document(s) found in %s", len(sub_docs), pdf_path.name)

        for doc_meta, doc_text in sub_docs:
            logger.info(
                "  doc_id=%s  title=%r  category=%s  version=%s",
                doc_meta.doc_id, doc_meta.doc_title, doc_meta.category, doc_meta.version,
            )

            sections = _split_into_sections(doc_text)
            logger.info("    %d sections detected", len(sections))

            chunk_idx = 0
            for section in sections:
                sentences = _split_sentences(section.body)
                if not sentences:
                    continue

                embeddings = model.encode(sentences, show_progress_bar=False)
                chunks = _semantic_chunk(sentences, embeddings)

                for chunk_text in chunks:
                    all_vectors.append({
                        "id": f"{pdf_path.stem}__{doc_meta.doc_id}__chunk_{global_chunk_idx}",
                        "values": model.encode(chunk_text).tolist(),
                        "metadata": {
                            # ── document-level (filter axes) ──
                            "source":         doc_meta.source,
                            "doc_id":         doc_meta.doc_id,
                            "doc_title":      doc_meta.doc_title,
                            "category":       doc_meta.category,
                            "version":        doc_meta.version,
                            "effective_date": doc_meta.effective_date,
                            "owner":          doc_meta.owner,
                            "applies_to":     doc_meta.applies_to,
                            # ── section-level (citation granularity) ──
                            "section_number":  section.number,
                            "section_heading": section.heading,
                            # ── chunk-level ──
                            "chunk_index": global_chunk_idx,
                            "text":        chunk_text,
                        },
                    })
                    chunk_idx += 1
                    global_chunk_idx += 1

            logger.info("    %d chunks from %s", chunk_idx, doc_meta.doc_id)

    total = len(all_vectors)
    logger.info("Upserting %d vectors to Pinecone (batch=%d)", total, _UPSERT_BATCH)
    for start in range(0, total, _UPSERT_BATCH):
        batch = all_vectors[start : start + _UPSERT_BATCH]
        pinecone_index.upsert(vectors=batch)
        logger.info("  Upserted %d–%d", start, start + len(batch) - 1)

    logger.info("Policy indexing complete — %d vectors total", total)
    return total
