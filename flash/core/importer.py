"""File -> questions pipeline (no UI code here)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .extract import extract_lines
from .model import Question
from .parser import looks_like_question_bank, parse_question_bank


@dataclass
class ImportResult:
    """What :func:`analyse_file` found in a file."""

    name: str
    source: str
    lines: list[str]
    questions: list[Question]  # parsed test bank questions (may be empty)
    is_bank: bool

    @property
    def has_text(self) -> bool:
        """True if the file had real text (a scanned PDF has none)."""
        return sum(len(l) for l in self.lines) > 50


def analyse_file(path: str, progress=None) -> ImportResult:
    """Read a file and decide whether it is a test collection.

    ``result.is_bank`` is True when ready-made questions were found (they are in ``result.questions``);
    otherwise ``result.lines`` holds the text for a question generator.
    Raises :class:`~flash.core.extract.ExtractionError` when the file can't be read.
    """
    lines = extract_lines(path, progress)
    questions = parse_question_bank(lines)
    is_bank = looks_like_question_bank(lines, questions)
    name = os.path.splitext(os.path.basename(path))[0]
    return ImportResult(name=name, source=path, lines=lines, questions=questions if is_bank else [], is_bank=is_bank)
