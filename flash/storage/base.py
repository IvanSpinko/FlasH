"""What FlasH needs from a storage backend.

FlashService only uses the methods below, so any class that has them can be
plugged in: JSON files for the desktop app today, a database for a web
server later, or an in-memory fake in tests.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..core.model import Deck, Question


@runtime_checkable
class Repository(Protocol):
    """The storage interface FlashService works with. Any class with these members fits."""

    settings: dict
    """User settings (language, theme, font size, AI key and model, ...)."""

    def save_settings(self) -> None:
        """Write :attr:`settings` to storage."""
        ...

    # decks
    def list_decks(self) -> list[Deck]:
        """All decks, newest first."""
        ...

    def load_deck(self, deck_id: str) -> Deck | None:
        """The deck with this id, or None if there is none."""
        ...

    def create_deck(self, name: str, source: str, kind: str, questions: list[Question]) -> Deck:
        """Store new questions as a deck; gives the deck and each question an id."""
        ...

    def save_deck(self, deck: Deck) -> None:
        """Store changes to an existing deck (e.g. a new name)."""
        ...

    def delete_deck(self, deck_id: str) -> None:
        """Remove the deck and its progress."""
        ...

    # progress
    def stats(self, deck_id: str) -> dict[str, dict]:
        """Per-question counters: ``{question_id: {"seen", "right", "wrong", "streak"}}``."""
        ...

    def record(self, deck_id: str, question_id: str, correct: bool) -> None:
        """Count one answer to a question: seen, right or wrong, and the streak of right answers."""
        ...

    def reset_progress(self, deck_id: str) -> None:
        """Forget all answers for a deck."""
        ...

    def save_progress(self) -> None:
        """Write the recorded answers to storage."""
        ...

    def summary(self, deck: Deck) -> dict:
        """Counts for a deck: ``{"total", "seen", "learned", "weak"}``."""
        ...
