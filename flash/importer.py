"""File -> questions pipeline (no UI code here)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from .extract import extract_lines
from .model import Question
from .parser import looks_like_question_bank, parse_question_bank


@dataclass
class ImportResult:
    name: str
    source: str
    lines: list[str]
    questions: list[Question]  # parsed test bank questions (may be empty)
    is_bank: bool

    @property
    def has_text(self) -> bool:
        return sum(len(l) for l in self.lines) > 50


def analyse_file(path: str, progress=None) -> ImportResult:
    lines = extract_lines(path, progress)
    questions = parse_question_bank(lines)
    is_bank = looks_like_question_bank(lines, questions)
    name = os.path.splitext(os.path.basename(path))[0]
    return ImportResult(name=name, source=path, lines=lines, questions=questions if is_bank else [], is_bank=is_bank)
