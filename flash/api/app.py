"""FastAPI app on top of FlashService.

Run it with ``uvicorn flash.api.app:create_app --factory`` (see the Dockerfile). Data is stored
like in the desktop app, in ``FLASH_DATA_DIR``.

First version, on purpose kept small:
- no user accounts: everyone using the server shares the same decks;
- running tests live in memory, so they are lost when the server restarts
  (answers are still saved as progress);
- no AI generation: it would run on the server's API key and cost money.
"""

from __future__ import annotations

import os
import tempfile
import threading
import uuid
from typing import Annotated, Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from .. import __version__
from ..core.extract import SUPPORTED_EXTENSIONS
from ..core.model import Deck
from ..core.quiz import Session
from ..service import FlashService


class DeckOut(BaseModel):
    id: str
    name: str
    kind: str
    created: str
    questions: int
    progress: dict


class QuestionOut(BaseModel):
    text: str
    options: list[str]
    answer: int
    explanation: str = ""


class DeckDetail(DeckOut):
    items: list[QuestionOut]


class TestRequest(BaseModel):
    mode: Literal["smart", "random", "ordered", "mistakes", "unseen"] = "smart"
    count: int | None = Field(default=None, ge=1)
    start: int = Field(default=1, ge=1)
    end: int | None = Field(default=None, ge=1)
    shuffle_options: bool = True


class OpenQuestion(BaseModel):
    number: int
    text: str
    options: list[str]


class TestState(BaseModel):
    test_id: str
    deck_id: str
    total: int
    answered: int
    score: int
    finished: bool
    question: OpenQuestion | None


class AnswerRequest(BaseModel):
    position: int = Field(ge=0, description="Index of the chosen option, as shown in the question")


class AnswerResult(BaseModel):
    correct: bool
    correct_position: int
    explanation: str
    state: TestState


def create_app(service: FlashService | None = None) -> FastAPI:
    service = service or FlashService()
    tests: dict[str, Session] = {}
    lock = threading.Lock()  # JSON storage is not safe for parallel writes
    app = FastAPI(title="FlasH API", version=__version__, description=__doc__)

    def deck_out(deck: Deck) -> DeckOut:
        return DeckOut(
            id=deck.id,
            name=deck.name,
            kind=deck.kind,
            created=deck.created,
            questions=len(deck.questions),
            progress=service.deck_summary(deck),
        )

    def find_deck(deck_id: str) -> Deck:
        deck = service.get_deck(deck_id)
        if deck is None:
            raise HTTPException(404, "Deck not found")
        return deck

    def find_test(test_id: str) -> Session:
        session = tests.get(test_id)
        if session is None:
            raise HTTPException(404, "Test not found (tests are lost when the server restarts)")
        return session

    def state(test_id: str, session: Session) -> TestState:
        item = session.current
        question = None
        if item is not None:
            question = OpenQuestion(number=session.index + 1, text=item.question.text, options=item.options)
        return TestState(
            test_id=test_id,
            deck_id=session.deck_id,
            total=len(session.items),
            answered=len(session.answered),
            score=session.score,
            finished=item is None,
            question=question,
        )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/decks")
    def list_decks() -> list[DeckOut]:
        with lock:
            return [deck_out(d) for d in service.list_decks()]

    @app.get("/decks/{deck_id}")
    def get_deck(deck_id: str) -> DeckDetail:
        with lock:
            deck = find_deck(deck_id)
            items = [
                QuestionOut(text=q.text, options=q.options, answer=q.answer, explanation=q.explanation)
                for q in deck.questions
            ]
            return DeckDetail(**deck_out(deck).model_dump(), items=items)

    @app.post("/decks", status_code=201)
    def import_deck(
        file: Annotated[UploadFile, File(description="A PDF, TXT or MD file")],
        generate: Annotated[
            Literal["offline", "none"], Query(description="For plain notes: make questions offline, or refuse")
        ] = "offline",
    ) -> DeckOut:
        """Upload a test bank (questions are found) or notes (questions are generated offline)."""
        filename = file.filename or "upload"
        name, ext = os.path.splitext(os.path.basename(filename))
        if ext.lower() not in SUPPORTED_EXTENSIONS:
            raise HTTPException(415, f"Unsupported file type; use one of: {', '.join(SUPPORTED_EXTENSIONS)}")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "upload" + ext.lower())
            with open(path, "wb") as f:
                f.write(file.file.read())
            result = service.analyse_file(path)
        if not result.has_text:
            raise HTTPException(422, "No text found (a scanned PDF needs OCR, which is not supported yet)")
        if result.is_bank:
            questions, kind = result.questions, "bank"
        elif generate == "offline":
            questions, kind = service.generate_offline(result), "generated"
        else:
            raise HTTPException(422, "Not a test bank; use generate=offline to make questions from notes")
        if not questions:
            raise HTTPException(422, "No questions could be found or generated")
        with lock:
            return deck_out(service.save_deck(name or "Untitled", filename, kind, questions))

    @app.delete("/decks/{deck_id}", status_code=204)
    def delete_deck(deck_id: str) -> None:
        with lock:
            find_deck(deck_id)
            service.delete_deck(deck_id)

    @app.post("/decks/{deck_id}/tests", status_code=201)
    def start_test(deck_id: str, request: TestRequest | None = None) -> TestState:
        request = request or TestRequest()
        with lock:
            deck = find_deck(deck_id)
            session = service.start_test(deck, **request.model_dump())
        if session is None:
            raise HTTPException(422, "No questions match this selection")
        test_id = uuid.uuid4().hex
        tests[test_id] = session
        return state(test_id, session)

    @app.get("/tests/{test_id}")
    def get_test(test_id: str) -> TestState:
        return state(test_id, find_test(test_id))

    @app.post("/tests/{test_id}/answer")
    def answer(test_id: str, request: AnswerRequest) -> AnswerResult:
        """Answer the open question, then move on to the next one."""
        session = find_test(test_id)
        item = session.current
        if item is None:
            raise HTTPException(409, "The test is already finished")
        if request.position >= len(item.options):
            raise HTTPException(422, f"position must be between 0 and {len(item.options) - 1}")
        with lock:
            correct = service.answer(session, request.position)
            service.save_progress()
        session.next()
        return AnswerResult(
            correct=correct,
            correct_position=item.correct_pos,
            explanation=item.question.explanation,
            state=state(test_id, session),
        )

    return app
