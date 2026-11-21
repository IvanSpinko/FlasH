"""The web API: FlasH's logic over HTTP, on top of FlashService.

Run it with ``uvicorn flash.api.app:create_app --factory`` (see the Dockerfile).
Data is stored like in the desktop app, in ``FLASH_DATA_DIR``; limits come
from :class:`~flash.api.config.ApiConfig`.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
from typing import Annotated, Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.routing import APIRoute

from .. import __version__
from ..core.extract import SUPPORTED_EXTENSIONS, ExtractionError
from ..core.model import Deck
from ..core.quiz import Session
from ..service import FlashService
from .config import ApiConfig
from .schemas import (
    AnswerRequest,
    AnswerResult,
    DeckDetail,
    DeckOut,
    ErrorOut,
    HealthOut,
    OpenQuestion,
    Progress,
    QuestionOut,
    TestRequest,
    TestState,
)
from .sessions import TestSessions

__all__ = ["create_app", "TestRequest"]

log = logging.getLogger("flash.api")

DESCRIPTION = """
Import study files, then take tests on them, one question at a time.
The same logic as the FlasH desktop app, which doesn't need this API.

**Typical flow**

1. `POST /decks` with a PDF, TXT or MD file. A test collection is read as is;
   plain notes are turned into questions offline.
2. `POST /decks/{deck_id}/tests` to start a test. The response holds the first question.
3. `POST /tests/{test_id}/answer` with the index of the chosen option.
   The response says whether it was right and holds the next question.

**Things to know**

- There are no user accounts: everyone using one server shares the same decks.
  On a public server, protect the whole site with a password (see `docs/DEPLOYMENT.md`).
- Open tests live in memory. They are lost when the server restarts and forgotten
  after a few idle hours; answers are saved as progress straight away.
- AI question generation is not offered here: it would run on the server's API key.
- Errors come back as `{"detail": "..."}` with a 4xx status.
"""

TAGS = [
    {"name": "health", "description": "Is the API up?"},
    {"name": "decks", "description": "Import files as decks of questions, list and delete them."},
    {"name": "tests", "description": "Take a test on a deck, one question at a time."},
]


def _error(description: str) -> dict:
    return {"model": ErrorOut, "description": description}


def _setup_logging(level: str) -> None:
    # Uvicorn only configures its own loggers; give FlasH's a handler once.
    logger = logging.getLogger("flash")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(level)


def create_app(service: FlashService | None = None, config: ApiConfig | None = None) -> FastAPI:
    """Build the API app.

    ``service`` defaults to one that stores data in ``FLASH_DATA_DIR`` and ``config``
    to :meth:`ApiConfig.from_env`; tests pass their own of both.
    """
    config = config or ApiConfig.from_env()
    _setup_logging(config.log_level)
    service = service or FlashService()
    tests = TestSessions(config.max_open_tests, config.test_idle_hours * 3600)
    lock = threading.Lock()  # JSON storage and open tests aren't safe for parallel writes

    app = FastAPI(
        title="FlasH API",
        version=__version__,
        summary="Practice tests from your study files.",
        description=DESCRIPTION,
        openapi_tags=TAGS,
        # operationId = the function name (list_decks, ...), so generated clients read well.
        generate_unique_id_function=lambda route: route.name if isinstance(route, APIRoute) else "",
    )

    def deck_out(deck: Deck) -> DeckOut:
        return DeckOut(
            id=deck.id,
            name=deck.name,
            kind=deck.kind,
            created=deck.created,
            questions=len(deck.questions),
            progress=Progress(**service.deck_summary(deck)),
        )

    def find_deck(deck_id: str) -> Deck:
        deck = service.get_deck(deck_id)
        if deck is None:
            raise HTTPException(404, "Deck not found")
        return deck

    def find_test(test_id: str) -> Session:
        session = tests.get(test_id)
        if session is None:
            raise HTTPException(404, "Test not found (it may have expired or the server restarted)")
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

    def save_upload(file: UploadFile, path: str) -> None:
        # Copy in chunks and stop as soon as the file is too big, so it never fills the disk.
        size = 0
        with open(path, "wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > config.max_upload_bytes:
                    raise HTTPException(413, f"File is too large; the limit is {config.max_upload_mb:g} MB")
                out.write(chunk)

    @app.get("/health", tags=["health"], summary="Check that the API is up")
    def health() -> HealthOut:
        """Answers as long as the API runs. Used by Docker's health check and uptime monitors."""
        return HealthOut(status="ok", version=__version__)

    @app.get("/decks", tags=["decks"], summary="List decks")
    def list_decks() -> list[DeckOut]:
        """Every deck with its progress, newest first."""
        with lock:
            return [deck_out(d) for d in service.list_decks()]

    @app.get(
        "/decks/{deck_id}",
        tags=["decks"],
        summary="Get a deck with its questions",
        responses={404: _error("No deck with this id.")},
    )
    def get_deck(deck_id: str) -> DeckDetail:
        """The deck, its progress, and every question with its correct answer."""
        with lock:
            deck = find_deck(deck_id)
            items = [
                QuestionOut(text=q.text, options=q.options, answer=q.answer, explanation=q.explanation)
                for q in deck.questions
            ]
            return DeckDetail(**deck_out(deck).model_dump(), items=items)

    @app.post(
        "/decks",
        status_code=201,
        tags=["decks"],
        summary="Import a file as a new deck",
        responses={
            413: _error("The file is larger than the server allows (FLASH_MAX_UPLOAD_MB)."),
            415: _error("Not a PDF, TXT or MD file."),
            422: _error(
                "The file can't be read (damaged or password-protected), has no text (a scanned PDF), "
                "is plain notes with `generate=none`, has no questions, or the request is malformed."
            ),
        },
    )
    def import_deck(
        file: Annotated[UploadFile, File(description="A PDF, TXT or MD file.")],
        generate: Annotated[
            Literal["offline", "none"],
            Query(description='For plain notes: "offline" makes questions from them, "none" refuses them.'),
        ] = "offline",
    ) -> DeckOut:
        """Upload a test collection (its questions are read as they are) or study notes
        (questions are made from them offline). The deck is named after the file."""
        filename = os.path.basename(file.filename or "upload")
        name, ext = os.path.splitext(filename)
        if ext.lower() not in SUPPORTED_EXTENSIONS:
            raise HTTPException(415, f"Unsupported file type; use one of: {', '.join(SUPPORTED_EXTENSIONS)}")
        tmp = tempfile.mkdtemp(prefix="flash-upload-")
        try:
            path = os.path.join(tmp, "upload" + ext.lower())
            save_upload(file, path)
            result = service.analyse_file(path)
        except ExtractionError as e:
            log.warning("could not read upload %r: %s", filename, e)
            raise HTTPException(422, "Could not read the file; it may be damaged or password-protected") from None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
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
            deck = service.save_deck(name or "Untitled", filename, kind, questions)
            log.info("imported deck %s (%s, %d questions)", deck.id, kind, len(questions))
            return deck_out(deck)

    @app.delete(
        "/decks/{deck_id}",
        status_code=204,
        tags=["decks"],
        summary="Delete a deck",
        responses={404: _error("No deck with this id.")},
    )
    def delete_deck(deck_id: str) -> None:
        """Delete the deck, its progress and its open tests. This can't be undone."""
        with lock:
            find_deck(deck_id)
            service.delete_deck(deck_id)
            dropped = tests.drop_deck(deck_id)
        log.info("deleted deck %s (%d open tests closed)", deck_id, dropped)

    @app.post(
        "/decks/{deck_id}/tests",
        status_code=201,
        tags=["tests"],
        summary="Start a test",
        responses={
            404: _error("No deck with this id."),
            422: _error(
                "No questions match the selection (for example, no mistakes yet), or the request is malformed."
            ),
        },
    )
    def start_test(deck_id: str, request: TestRequest | None = None) -> TestState:
        """Pick questions from the deck. The response holds the first question.
        The body is optional; without it, all questions are asked in smart order."""
        request = request or TestRequest()
        with lock:
            deck = find_deck(deck_id)
            session = service.start_test(deck, **request.model_dump())
            if session is None:
                raise HTTPException(422, "No questions match this selection")
            test_id = tests.add(session)
            return state(test_id, session)

    @app.get(
        "/tests/{test_id}",
        tags=["tests"],
        summary="Get a test's state",
        responses={404: _error("No open test with this id: it never existed, expired, or the server restarted.")},
    )
    def get_test(test_id: str) -> TestState:
        """The score so far and the question waiting for an answer, for example after reloading the page."""
        with lock:
            return state(test_id, find_test(test_id))

    @app.post(
        "/tests/{test_id}/answer",
        tags=["tests"],
        summary="Answer the open question",
        responses={
            404: _error("No open test with this id: it never existed, expired, or the server restarted."),
            409: _error("The test is already finished."),
            422: _error("`position` is not one of the shown options, or the request is malformed."),
        },
    )
    def answer(test_id: str, request: AnswerRequest) -> AnswerResult:
        """Check the answer, save it as progress, and move on to the next question."""
        with lock:
            session = find_test(test_id)
            item = session.current
            if item is None:
                raise HTTPException(409, "The test is already finished")
            if request.position >= len(item.options):
                raise HTTPException(422, f"position must be between 0 and {len(item.options) - 1}")
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
