"""Sample data and small helpers shared by the tests."""

from __future__ import annotations

import importlib.util
import os
import textwrap

from flash.core.model import Question

HAS_API = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "multipart"))
"""The web API's packages are installed (requirements-api.txt plus httpx)."""

BANK = """1. Which organ pumps blood?
Heart
Liver
Lungs
Kidneys

2. Which gas do plants absorb?
Carbon dioxide
Oxygen
Nitrogen
Helium

3. What is the chemical symbol of sodium?
Na
K
Ca
S
"""
"""A tiny test collection: three questions, the right answer first (as in Krok booklets)."""

BANK_ANSWERS = ["Heart", "Carbon dioxide", "Na"]

NOTES = "\n\n".join(
    f"{term} is a {desc} that is studied in the introductory biology course every year."
    for term, desc in [
        ("Mitochondrion", "membrane organelle producing most of the energy of the cell"),
        ("Ribosome", "molecular machine building proteins from amino acids"),
        ("Lysosome", "small vesicle containing digestive enzymes for waste"),
        ("Chloroplast", "plant organelle where photosynthesis takes place"),
        ("Nucleus", "membrane organelle storing the genetic material"),
    ]
)
"""Plain study notes: not a test collection, but enough definitions for the offline generator."""


def make_questions(n: int, options: int = 4) -> list[Question]:
    """``n`` questions where the first option, ``right<i>``, is always correct."""
    return [
        Question(text=f"Q{i}?", options=[f"right{i}"] + [f"wrong{i}.{k}" for k in range(1, options)])
        for i in range(1, n + 1)
    ]


def write_text(folder: str, name: str, text: str, encoding: str = "utf-8") -> str:
    """Write ``text`` to ``folder/name`` and return the path."""
    path = os.path.join(folder, name)
    with open(path, "w", encoding=encoding) as f:
        f.write(text)
    return path


def write_pdf(folder: str, name: str, text: str, lines_per_page: int = 40) -> str:
    """Write ``text`` as a real PDF and return the path.

    Long lines are wrapped to fit the page, as they would be in a real document.
    """
    import pymupdf

    path = os.path.join(folder, name)
    doc = pymupdf.open()
    lines = [part for line in text.splitlines() for part in (textwrap.wrap(line, 80) or [""])]
    for start in range(0, max(len(lines), 1), lines_per_page):
        page = doc.new_page()
        y = 50
        for line in lines[start : start + lines_per_page]:
            if line:
                page.insert_text((50, y), line, fontsize=11)
            y += 16
    doc.save(path)
    doc.close()
    return path
