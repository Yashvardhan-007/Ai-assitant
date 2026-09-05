"""
document_parser.py — Extracts plain text (with light structural hints such as
slide/page boundaries and heading-like lines) from uploaded learning material.

Supported formats: .pdf .docx .pptx .txt .md
"""
import os
from pypdf import PdfReader
from docx import Document
from pptx import Presentation


def parse_file(filepath: str) -> dict:
    """Returns {"filename":..., "pages": [ {"index":int, "text":str}, ... ], "full_text": str}"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        pages = _parse_pdf(filepath)
    elif ext == ".docx":
        pages = _parse_docx(filepath)
    elif ext == ".pptx":
        pages = _parse_pptx(filepath)
    elif ext in (".txt", ".md"):
        pages = _parse_txt(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    full_text = "\n\n".join(p["text"] for p in pages if p["text"].strip())
    return {
        "filename": os.path.basename(filepath),
        "pages": pages,
        "full_text": full_text,
    }


def _parse_pdf(filepath):
    reader = PdfReader(filepath)
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append({"index": i + 1, "text": text})
    return pages


def _parse_docx(filepath):
    doc = Document(filepath)
    # Group into pseudo-pages of ~40 paragraphs so downstream chunking works
    # the same way regardless of source format.
    pages, buf, idx = [], [], 1
    for para in doc.paragraphs:
        if para.text.strip():
            buf.append(para.text)
        if len(buf) >= 40:
            pages.append({"index": idx, "text": "\n".join(buf)})
            buf, idx = [], idx + 1
    if buf:
        pages.append({"index": idx, "text": "\n".join(buf)})
    if not pages:
        pages = [{"index": 1, "text": ""}]
    return pages


def _parse_pptx(filepath):
    prs = Presentation(filepath)
    pages = []
    for i, slide in enumerate(prs.slides):
        lines = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in para.runs)
                    if line.strip():
                        lines.append(line)
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text for c in row.cells]
                    lines.append(" | ".join(cells))
        # speaker notes are often rich with explanation text
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text
            if notes.strip():
                lines.append(f"[Notes] {notes}")
        pages.append({"index": i + 1, "text": "\n".join(lines)})
    return pages


def _parse_txt(filepath):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    # split on blank-line-separated blocks into pseudo pages of ~2000 chars
    chunks = []
    cur = ""
    for block in text.split("\n\n"):
        if len(cur) + len(block) > 2000 and cur:
            chunks.append(cur)
            cur = ""
        cur += block + "\n\n"
    if cur.strip():
        chunks.append(cur)
    return [{"index": i + 1, "text": c} for i, c in enumerate(chunks)] or [{"index": 1, "text": text}]
