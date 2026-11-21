"""Test doubles: simple stand-ins for storage, time and the Anthropic client.

- A **fake** is a small working implementation (``MemoryStore`` keeps decks in a dict).
- A **stub** returns canned answers (``FakeAnthropic`` returns prepared responses).
- A **mock** also records how it was called; the tests use ``unittest.mock`` for those
  and check the recorded calls (``FakeAnthropic.calls`` plays the same role).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from flash.core.model import Deck, Question


class MemoryStore:
    """A storage that keeps everything in memory: no files at all.

    It follows the ``flash.storage.Repository`` interface, so the service can't tell
    it apart from ``JsonStore``. ``saves`` counts how often data would have been written.
    """

    def __init__(self, settings: dict | None = None):
        self.settings = {"shuffle_options": False, **(settings or {})}
        self.decks: dict[str, Deck] = {}
        self.progress: dict[str, dict[str, dict]] = {}
        self.saves = 0

    def save_settings(self) -> None:
        self.saves += 1

    def list_decks(self) -> list[Deck]:
        return list(self.decks.values())

    def load_deck(self, deck_id: str) -> Deck | None:
        return self.decks.get(deck_id)

    def create_deck(self, name: str, source: str, kind: str, questions: list[Question]) -> Deck:
        deck = Deck(id=f"d{len(self.decks) + 1}", name=name, source=source, kind=kind, created="", questions=questions)
        for i, q in enumerate(deck.questions, 1):
            q.id = str(i)
        self.decks[deck.id] = deck
        return deck

    def save_deck(self, deck: Deck) -> None:
        self.decks[deck.id] = deck

    def delete_deck(self, deck_id: str) -> None:
        self.decks.pop(deck_id, None)
        self.progress.pop(deck_id, None)

    def stats(self, deck_id: str) -> dict[str, dict]:
        return self.progress.setdefault(deck_id, {})

    def record(self, deck_id: str, question_id: str, correct: bool) -> None:
        s = self.stats(deck_id).setdefault(question_id, {"seen": 0, "right": 0, "wrong": 0, "streak": 0})
        s["seen"] += 1
        s["right" if correct else "wrong"] += 1
        s["streak"] = s["streak"] + 1 if correct else 0

    def reset_progress(self, deck_id: str) -> None:
        self.progress[deck_id] = {}

    def save_progress(self) -> None:
        self.saves += 1

    def summary(self, deck: Deck) -> dict:
        st = self.progress.get(deck.id, {})
        return {
            "total": len(deck.questions),
            "seen": len(st),
            "learned": sum(1 for s in st.values() if s["streak"] >= 2),
            "weak": sum(1 for s in st.values() if s["streak"] == 0),
        }


class FakeClock:
    """A clock the test moves by hand: ``clock()`` gives the time, ``advance(s)`` moves it."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def ai_response(questions: list[dict] | None = None, text: str | None = None, stop_reason: str = "end_turn"):
    """Something shaped like an Anthropic Messages response.

    Pass ``questions`` for the structured JSON FlasH asks for, or raw ``text`` (e.g. broken JSON).
    """
    if text is None:
        text = json.dumps({"questions": questions or []})
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


def ai_question(question: str, options: list[str], correct_index: int, explanation: str = "") -> dict:
    """One question in the JSON shape FlasH asks Claude for."""
    return {"question": question, "options": options, "correct_index": correct_index, "explanation": explanation}


class FakeAnthropic:
    """Stands in for ``anthropic.Anthropic``: returns prepared responses and records every request.

    ``responses`` are returned one per request, in order; an exception in the list is raised instead.
    Both ``client.messages.create`` and ``client.beta.messages.create`` go to the same queue.
    """

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.api_key = None
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def __call__(self, api_key=None, **_):
        # Used as the class: anthropic.Anthropic(api_key=...) returns this same object.
        self.api_key = api_key
        return self

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakeAPIError(Exception):
    """Stands in for the Anthropic SDK's error classes, which need a real HTTP response to build."""

    def __init__(self, message: str = "error", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
