"""The JSON shapes the web API reads and returns.

They are what the OpenAPI document (``/docs``, ``docs/openapi.json``) describes,
so every field has a description and the main shapes have an example.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["smart", "random", "ordered", "mistakes", "unseen"]
"""How questions are picked for a test; the same names as ``flash.core.quiz.MODES``."""


class ErrorOut(BaseModel):
    """Returned with every 4xx response."""

    detail: str | list[dict[str, Any]] = Field(
        description="What went wrong. A sentence for FlasH's own errors; "
        "for a malformed request, FastAPI's list of the fields that are wrong.",
        examples=["Deck not found"],
    )


class HealthOut(BaseModel):
    """The API is up."""

    status: Literal["ok"] = Field(description='Always "ok" when the API can answer.')
    version: str = Field(description="FlasH's version.", examples=["0.1.0"])


class Progress(BaseModel):
    """How far the user is with a deck."""

    total: int = Field(description="Questions in the deck.", examples=[120])
    seen: int = Field(description="Questions answered at least once.", examples=[45])
    learned: int = Field(description="Questions answered right at least twice in a row.", examples=[30])
    weak: int = Field(description="Questions whose last answer was wrong.", examples=[6])


class DeckOut(BaseModel):
    """A deck in the list: its name and progress, without the questions."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "3f9c1a2b7d4e",
                    "name": "Krok 1 2024",
                    "kind": "bank",
                    "created": "2026-11-20T14:05:31",
                    "questions": 120,
                    "progress": {"total": 120, "seen": 45, "learned": 30, "weak": 6},
                }
            ]
        }
    )

    id: str = Field(description="The deck's id, used in other addresses.")
    name: str = Field(description="Shown to the user; the uploaded file's name without its extension.")
    kind: Literal["bank", "generated", "ai"] = Field(
        description='"bank": questions found in a test collection; "generated": made offline from notes; '
        '"ai": made by Claude (desktop app only).'
    )
    created: str = Field(description="When it was imported, ISO 8601 server local time.")
    questions: int = Field(description="Number of questions.")
    progress: Progress


class QuestionOut(BaseModel):
    """One question with its correct answer."""

    text: str = Field(description="The question.")
    options: list[str] = Field(description="Answer options, in the stored order.")
    answer: int = Field(description="Index of the correct option in ``options``.")
    explanation: str = Field(default="", description="Why the answer is right, when known.")


class DeckDetail(DeckOut):
    """A deck with all its questions and answers."""

    items: list[QuestionOut] = Field(description="Every question in the deck, in order.")


class TestRequest(BaseModel):
    """Which questions to ask. Every field is optional."""

    __test__ = False  # not a test case, despite the name
    model_config = ConfigDict(json_schema_extra={"examples": [{"mode": "smart", "count": 30, "shuffle_options": True}]})

    mode: Mode = Field(
        default="smart",
        description='"smart": weak and new questions first; "random"; "ordered": as in the file; '
        '"mistakes": only questions last answered wrong; "unseen": only questions never answered.',
    )
    count: int | None = Field(default=None, ge=1, description="How many questions; all of them when empty.")
    start: int = Field(default=1, ge=1, description="First question number to pick from (1-based, inclusive).")
    end: int | None = Field(
        default=None, ge=1, description="Last question number to pick from; the last one when empty."
    )
    shuffle_options: bool = Field(default=True, description="Show the answer options in a random order.")


class OpenQuestion(BaseModel):
    """The question waiting for an answer. The correct answer is not included."""

    number: int = Field(description="Its place in the test, from 1.")
    text: str = Field(description="The question.")
    options: list[str] = Field(description="Answer options in the order shown; answer with their index.")


class TestState(BaseModel):
    """Where a test is: the score so far and the next question."""

    __test__ = False  # not a test case, despite the name
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "test_id": "9a7c2e0f4b1d4c8e9f3a6b5d2c1e0f7a",
                    "deck_id": "3f9c1a2b7d4e",
                    "total": 30,
                    "answered": 1,
                    "score": 1,
                    "finished": False,
                    "question": {
                        "number": 2,
                        "text": "Which gas do plants absorb?",
                        "options": ["Oxygen", "Carbon dioxide", "Nitrogen", "Helium"],
                    },
                }
            ]
        }
    )

    test_id: str = Field(description="The test's id, used to answer.")
    deck_id: str = Field(description="The deck the questions come from.")
    total: int = Field(description="Questions in this test.")
    answered: int = Field(description="Questions answered so far.")
    score: int = Field(description="Right answers so far.")
    finished: bool = Field(description="True when every question is answered.")
    question: OpenQuestion | None = Field(description="The next question, or null when the test is finished.")


class AnswerRequest(BaseModel):
    """The user's choice for the open question."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"position": 1}]})

    position: int = Field(ge=0, description="Index of the chosen option, as shown in the question.")


class AnswerResult(BaseModel):
    """Whether the answer was right, and the test's new state with the next question."""

    correct: bool = Field(description="The answer was right.")
    correct_position: int = Field(description="Index of the right option, as shown in the question.")
    explanation: str = Field(description="Why that answer is right; empty when the file had no explanation.")
    state: TestState
