"""
Chunk verification script — run independently of the main app.

Usage (from backend/):
    source venv/bin/activate
    python -m scripts.verify_chunks

Output:
    data/chunk_verification.json   — full structured report (every chunk + metadata)
    data/chunk_summary.txt         — human-readable summary table
"""

import json
import sys
from pathlib import Path

import pdfplumber
from sentence_transformers import SentenceTransformer

# Allow running as   python -m scripts.verify_chunks   from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.policy_indexer import (
    _extract_doc_meta,
    _semantic_chunk,
    _split_into_sections,
    _split_sentences,
    _EMBED_MODEL,
)

POLICIES_DIR = Path("data/policies")
OUT_JSON     = Path("data/chunk_verification.json")
OUT_SUMMARY  = Path("data/chunk_summary.txt")


def build_report(model: SentenceTransformer) -> dict:
    pdf_files = sorted(
        p for p in POLICIES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )

    report: dict = {"documents": [], "totals": {}}
    grand_sections = 0
    grand_chunks   = 0

    for pdf_path in pdf_files:
        print(f"Processing {pdf_path.name} ...")

        with pdfplumber.open(pdf_path) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]

        full_text = "\n".join(pages)
        meta = _extract_doc_meta(pdf_path, pages[0])
        sections = _split_into_sections(full_text)

        doc_entry: dict = {
            "source":         meta.source,
            "doc_id":         meta.doc_id,
            "doc_title":      meta.doc_title,
            "category":       meta.category,
            "version":        meta.version,
            "effective_date": meta.effective_date,
            "owner":          meta.owner,
            "applies_to":     meta.applies_to,
            "section_count":  0,
            "chunk_count":    0,
            "sections":       [],
        }

        chunk_idx = 0
        for section in sections:
            sentences = _split_sentences(section.body)
            if not sentences:
                continue

            embeddings = model.encode(sentences, show_progress_bar=False)
            chunks     = _semantic_chunk(sentences, embeddings)

            section_entry: dict = {
                "section_number":  section.number,
                "section_heading": section.heading,
                "chunk_count":     len(chunks),
                "chunks":          [],
            }

            for chunk_text in chunks:
                section_entry["chunks"].append({
                    "chunk_index":    chunk_idx,
                    "char_count":     len(chunk_text),
                    "sentence_count": len(_split_sentences(chunk_text)),
                    "text":           chunk_text,
                })
                chunk_idx += 1

            doc_entry["sections"].append(section_entry)

        doc_entry["section_count"] = len(doc_entry["sections"])
        doc_entry["chunk_count"]   = chunk_idx
        grand_sections += doc_entry["section_count"]
        grand_chunks   += chunk_idx
        report["documents"].append(doc_entry)

    report["totals"] = {
        "documents": len(report["documents"]),
        "sections":  grand_sections,
        "chunks":    grand_chunks,
    }
    return report


def write_summary(report: dict) -> None:
    lines: list[str] = []
    lines.append("CHUNK VERIFICATION SUMMARY")
    lines.append("=" * 72)
    t = report["totals"]
    lines.append(
        f"  Total documents : {t['documents']}\n"
        f"  Total sections  : {t['sections']}\n"
        f"  Total chunks    : {t['chunks']}\n"
    )

    col = "{:<12}  {:<10}  {:<18}  {:>8}  {:>8}  {:>9}  {:>9}"
    lines.append(col.format("File", "Doc ID", "Category", "Sections", "Chunks", "Min chars", "Max chars"))
    lines.append("-" * 72)

    for doc in report["documents"]:
        all_chunks = [
            c for sec in doc["sections"] for c in sec["chunks"]
        ]
        min_c = min((c["char_count"] for c in all_chunks), default=0)
        max_c = max((c["char_count"] for c in all_chunks), default=0)
        lines.append(col.format(
            doc["source"], doc["doc_id"], doc["category"],
            doc["section_count"], doc["chunk_count"], min_c, max_c,
        ))

    lines.append("")
    lines.append("PER-DOCUMENT SECTION BREAKDOWN")
    lines.append("=" * 72)

    for doc in report["documents"]:
        lines.append(f"\n{doc['source']}  [{doc['doc_id']}]  \"{doc['doc_title']}\"")
        lines.append(f"  version={doc['version']}  date={doc['effective_date']}  owner={doc['owner']}")
        lines.append(f"  {'Section':<6}  {'Heading':<45}  {'Chunks':>6}  {'Sample text (60 chars)':}")
        lines.append("  " + "-" * 100)
        for sec in doc["sections"]:
            sample = sec["chunks"][0]["text"][:60].replace("\n", " ") if sec["chunks"] else ""
            lines.append(
                f"  {sec['section_number']:<6}  {sec['section_heading'][:44]:<45}"
                f"  {sec['chunk_count']:>6}  {sample!r}"
            )

    OUT_SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(f"Summary written → {OUT_SUMMARY}")


def main() -> None:
    if not POLICIES_DIR.exists():
        print(f"ERROR: {POLICIES_DIR} not found. Run from backend/", file=sys.stderr)
        sys.exit(1)

    print(f"Loading embedding model: {_EMBED_MODEL}")
    model = SentenceTransformer(_EMBED_MODEL)

    report = build_report(model)

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Full report written → {OUT_JSON}  ({OUT_JSON.stat().st_size // 1024} KB)")

    write_summary(report)

    t = report["totals"]
    print(f"\nDone — {t['documents']} docs  |  {t['sections']} sections  |  {t['chunks']} chunks")


if __name__ == "__main__":
    main()
