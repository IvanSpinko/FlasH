# Testing

FlasH has three layers of tests, from many small fast ones to a few slow ones that use the real thing:

```
            ▲  few, slow, real          e2e/         the real window, a real API server, a real browser
            │                           integration/ real files, real PDFs, real HTTP inside one process
            ▼  many, fast, isolated     unit/        one part at a time, with fakes and mocks
```

| Layer | Where | What it checks | Needs |
|---|---|---|---|
| **Unit** | `tests/unit/` | Quiz rules, the parser, the offline generator, the AI client (with a fake Claude), the service (with in-memory storage), API settings and open-test storage, translations | Python + `requirements.txt` |
| **Integration** | `tests/integration/` | `JsonStore` on real files; importing real TXT, MD and PDF files; the service on disk; every API endpoint over HTTP; that `docs/openapi.json` is up to date and every operation is documented | `+ requirements-dev.txt` for the API tests |
| **End to end (Python)** | `tests/e2e/` | The desktop window driven through a whole test; the API as a real `uvicorn` server process | A screen for the window test; `requirements-dev.txt` for the server test |
| **Web app: unit and component** | `frontend/src/**/*.test.ts(x)` | The API client (with a mocked `fetch`), error messages, translations, and the screens with a mocked API | Node |
| **Web app: end to end** | `frontend/e2e/` | A real browser, phone- and desktop-sized, against the running containers: upload, a whole test, practising mistakes, the keyboard, language, layout, no browser errors | Docker + Chromium |

## Running them

```bash
# Python: everything. Tests whose packages or screen are missing are skipped, and say why.
pip install -r requirements-dev.txt
python -m unittest discover -s tests -t .

# One layer, one file, or one test
python -m unittest discover -s tests/unit -t .
python -m unittest tests.integration.test_api -v
python -m unittest tests.unit.test_quiz.SessionTests.test_scoring_and_mistakes

# How much of the code the tests run (the desktop window is left out: the e2e test covers it)
python -m coverage run -m unittest discover -s tests -t .
python -m coverage report

# Web app
cd frontend
npm test                                   # unit and component tests (Vitest)
docker compose up -d --build --wait        # from the project root: start the web version
npx playwright install chromium            # once
npm run e2e                                # browser tests against http://localhost:8080
```

The browser tests can run against any address: `E2E_BASE_URL=https://flash.example.com E2E_USER=student E2E_PASSWORD=... npm run e2e`. They add their own decks with unique names and delete them afterwards.

## Fakes, stubs and mocks

Tests replace slow, costly or unpredictable parts with stand-ins. They live in `tests/fakes.py`:

| Stand-in | Kind | Replaces | Why |
|---|---|---|---|
| `MemoryStore` | **fake**: a small working version | `JsonStore` | Service tests run without touching the disk. |
| `FakeClock` | **fake** | `time.monotonic` | Tests move time forward to check that idle tests expire, without waiting hours. |
| `FakeAnthropic` | **stub** plus call recorder | the Anthropic client | AI tests return prepared answers, send nothing over the network, and check what would have been sent. |
| `FakeAPIError` | **stub** | the SDK's error classes | Checks that each API failure becomes the right short code. |
| `unittest.mock.patch` | **mock** | single functions | For example, it checks that the service passes the saved API key and model on. |
| `vi.mock("../api")` | **mock** (web app) | the API client | Screens are tested without a server. |

Sample data and helpers (`BANK`, `NOTES`, `make_questions`, `write_pdf`) are in `tests/helpers.py`.

## In CI

Every push and pull request runs `.github/workflows/tests.yml`:

| Job | Runs |
|---|---|
| Lint | ruff (bugs + docstrings), formatting, shellcheck on `deploy/*.sh` |
| Windows / macOS / Ubuntu · Python 3.13, Ubuntu · Python 3.10 | all Python tests with the desktop packages; on Windows and macOS the desktop window test must run (`FLASH_E2E_DESKTOP=1`) |
| Web API + Docker | all Python tests with the API's exact versions (`requirements-api-lock.txt`), coverage (fails under 90%), the Docker image and its health check |
| Web app + Compose | type-check, build, Vitest, both containers with Compose, Playwright, and a check of the production config |

## Adding a test

- **A new rule in `flash/core`**: a unit test next to the others in `tests/unit/`.
- **Something that reads or writes files**: an integration test, with a `tempfile.TemporaryDirectory()` so real data is never touched.
- **A new API endpoint**: a test in `tests/integration/test_api.py`, then `python -m flash.api.openapi` to update `docs/openapi.json` (a test fails until you do).
- **A new screen in the web app**: a component test with the API mocked, and a step in `frontend/e2e/flash.spec.ts` if it's part of what students do.
