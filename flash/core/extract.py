"""Text extraction from source documents.

Returns a flat list of lines. Empty strings mark paragraph breaks (blank lines
in the document). Page numbers are dropped.
"""

from __future__ import annotations

import os
import re

SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")

_PAGE_NUMBER = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")


class ExtractionError(Exception):
    """The file could not be read (unsupported type, damaged or password-protected PDF, unknown encoding)."""

    pass


def extract_lines(path: str, progress=None) -> list[str]:
    """Read a PDF, TXT or MD file into a list of cleaned-up lines.

    Empty strings mark paragraph breaks. ``progress(done, total)`` is called after each PDF page.
    Raises :class:`ExtractionError` when the file can't be read.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(path, progress)
    if ext in (".txt", ".md"):
        return _extract_text_file(path)
    raise ExtractionError(f"Unsupported file type: {ext}")


def _clean(line: str) -> str:
    # Normalise whitespace (PDFs often contain NBSP and doubled spaces).
    line = line.replace(" ", " ").replace("­", "")
    return re.sub(r"\s+", " ", line).strip()


def _extract_text_file(path: str) -> list[str]:
    for enc in ("utf-8-sig", "cp1251", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return [_clean(l) for l in f.read().splitlines()]
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Cannot decode text file")


def _extract_pdf(path: str, progress=None) -> list[str]:
    try:
        import pymupdf  # PyMuPDF: fast and keeps line structure
    except ImportError:  # pragma: no cover - fallback for minimal installs
        pymupdf = None

    lines: list[str] = []
    if pymupdf is not None:
        try:
            doc = pymupdf.open(path)
        except Exception as e:
            raise ExtractionError(str(e)) from e
        with doc:
            total = doc.page_count
            for i, page in enumerate(doc):
                page_lines = []
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        page_lines.append(_clean("".join(s["text"] for s in line["spans"])))
                _append_page(lines, page_lines)
                if progress:
                    progress(i + 1, total)
        return lines

    from pypdf import PdfReader  # pragma: no cover

    reader = PdfReader(path)
    total = len(reader.pages)
    for i, page in enumerate(reader.pages):
        _append_page(lines, [_clean(l) for l in (page.extract_text() or "").splitlines()])
        if progress:
            progress(i + 1, total)
    return lines


def _append_page(lines: list[str], page_lines: list[str]) -> None:
    page_lines = [l for l in page_lines if not _PAGE_NUMBER.match(l) or not l]
    # Drop blank lines at the top of a page: they are layout, not paragraph breaks.
    while page_lines and not page_lines[0]:
        page_lines.pop(0)
    # A page break is a soft paragraph break; the parser merges blocks that
    # turn out to be split questions.
    if lines and lines[-1] != "":
        lines.append("")
    lines.extend(page_lines)
