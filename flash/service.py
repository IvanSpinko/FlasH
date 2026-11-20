"""Application service: the single entry point to FlasH's logic.

Every screen talks to FlasH through this class instead of reaching into the
parser, the quiz rules or the storage directly:

- the desktop app calls it in-process, so it keeps working offline;
- a web API can call the same methods, so both share one implementation.

There is no UI code here: no windows, no dialogs and no translated text.
Problems are reported as exceptions or short codes for the caller to show.
"""

from __future__ import annotations

import os
import random

from .core import ai, generator
from .core.importer import ImportResult, analyse_file
from .core.model import Deck, Question
from .core.quiz import Session, select_questions
from .storage import JsonStore, Repository


class FlashService:
    def __init__(self, store: Repository | None = None):
        # JSON files on this computer by default; any Repository can be passed in.
        self.store = store if store is not None else JsonStore()

    # ----------------------------------------------------------- settings
    @property
    def settings(self) -> dict:
        return self.store.settings

    def update_settings(self, **changes) -> None:
        self.store.settings.update(changes)
        self.store.save_settings()

    # ----------------------------------------------------------- library
    def list_decks(self) -> list[Deck]:
        return self.store.list_decks()

    def get_deck(self, deck_id: str) -> Deck | None:
        return self.store.load_deck(deck_id)

    def deck_summary(self, deck: Deck) -> dict:
        """Counts for a deck: total, seen, learned (2+ right in a row) and weak."""
        return self.store.summary(deck)

    def rename_deck(self, deck: Deck, name: str) -> None:
        deck.name = name
        self.store.save_deck(deck)

    def reset_progress(self, deck_id: str) -> None:
        self.store.reset_progress(deck_id)

    def delete_deck(self, deck_id: str) -> None:
        self.store.delete_deck(deck_id)

    # ----------------------------------------------------------- importing
    def analyse_file(self, path: str, progress=None) -> ImportResult:
        """Read a file; ``result.is_bank`` says whether it already holds questions.

        ``progress(done, total)`` is called after each PDF page.
        """
        return analyse_file(path, progress)

    def generate_offline(self, result: ImportResult) -> list[Question]:
        """Make questions from plain notes without internet."""
        return generator.generate_questions(result.lines)

    def ai_key(self) -> str:
        return self.settings.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")

    def ai_problem(self) -> str | None:
        """Why AI generation can't run right now: "unavailable", "no_key", or None."""
        if not ai.is_available():
            return "unavailable"
        if not self.ai_key():
            return "no_key"
        return None

    def generate_with_ai(self, result: ImportResult, progress=None, cancelled=lambda: False) -> list[Question]:
        """Make questions from plain notes with Claude (needs internet and a key).

        Raises ``ai.AIError`` on failure; ``progress(done, total)`` is called per chunk.
        """
        model = self.settings.get("ai_model", ai.DEFAULT_MODEL)
        return ai.generate_questions(result.lines, self.ai_key(), model, progress=progress, cancelled=cancelled)

    def save_deck(self, name: str, source: str, kind: str, questions: list[Question]) -> Deck:
        """Store new questions as a deck; ``kind`` is "bank", "generated" or "ai"."""
        return self.store.create_deck(name, source, kind, questions)

    # ----------------------------------------------------------- tests
    def start_test(
        self,
        deck: Deck,
        mode: str = "smart",
        count: int | None = None,
        start: int = 1,
        end: int | None = None,
        shuffle_options: bool = True,
    ) -> Session | None:
        """Pick questions for a test; returns None when the selection is empty."""
        questions = select_questions(deck, self.store.stats(deck.id), mode=mode, count=count, start=start, end=end)
        if not questions:
            return None
        return Session.create(deck.id, questions, shuffle_options=shuffle_options)

    def answer(self, session: Session, position: int) -> bool:
        """Answer the current question and remember the result for smart mode."""
        item = session.current
        correct = session.answer(position)
        self.store.record(session.deck_id, item.question.id, correct)
        return correct

    def retry_mistakes(self, session: Session) -> Session:
        """A new test with only the questions answered wrong, in random order."""
        questions = [i.question for i in session.mistakes]
        random.shuffle(questions)
        return Session.create(session.deck_id, questions, self.settings["shuffle_options"])

    def save_progress(self) -> None:
        self.store.save_progress()
