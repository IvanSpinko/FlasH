# Web API

The web app talks to FlasH through this HTTP API (`flash/api`). It uses the same `FlashService` as the desktop app.

## Where the full reference is

The API describes itself in the **OpenAPI 3.1** format, generated from the code, so it can't drift from what the API does:

| Where | What |
|---|---|
| `/docs` (`/api/docs` through the web app) | **Swagger UI**: every endpoint, with a "Try it out" button |
| `/redoc` (`/api/redoc`) | **ReDoc**: the same, as one readable page |
| `/openapi.json` (`/api/openapi.json`) | the machine-readable document |
| [`docs/openapi.json`](openapi.json) | a copy in the repo, to read or generate clients from without running anything |

After changing the API, update the copy with `python -m flash.api.openapi`. A test fails until it matches the code.

Tools such as [openapi-generator](https://openapi-generator.tech/) or `openapi-typescript` can generate a client from `docs/openapi.json` in many languages. Every operation has a readable `operationId` (`list_decks`, `start_test`, ...).

## Endpoints

| Method and path | What it does | Success | Errors |
|---|---|---|---|
| `GET /health` | Is the API up? | 200 | |
| `GET /decks` | All decks with progress, newest first | 200 | |
| `POST /decks` | Import a PDF, TXT or MD file (`multipart/form-data`, field `file`; query `generate=offline\|none`) | 201 | 413, 415, 422 |
| `GET /decks/{deck_id}` | A deck with every question and answer | 200 | 404 |
| `DELETE /decks/{deck_id}` | Delete a deck, its progress and its open tests | 204 | 404 |
| `POST /decks/{deck_id}/tests` | Start a test (body optional: `mode`, `count`, `start`, `end`, `shuffle_options`) | 201 | 404, 422 |
| `GET /tests/{test_id}` | A test's score and next question | 200 | 404 |
| `POST /tests/{test_id}/answer` | Answer the open question (`{"position": 1}`) | 200 | 404, 409, 422 |

Every error is JSON: `{"detail": "Deck not found"}`. For a malformed request, `detail` is FastAPI's list of the fields that are wrong.

## Example: a whole test with curl

```bash
API=http://localhost:8080/api      # through the web app; http://localhost:8000 for the API container alone

# 1. Import a file
curl -F file=@krok.pdf "$API/decks"
# {"id":"3f9c1a2b7d4e","name":"krok","kind":"bank","questions":120,"progress":{...},...}

# 2. Start a test: 10 questions, weak and new ones first
curl -H 'Content-Type: application/json' -d '{"mode":"smart","count":10}' "$API/decks/3f9c1a2b7d4e/tests"
# {"test_id":"9a7c...","total":10,"answered":0,"score":0,"finished":false,
#  "question":{"number":1,"text":"...","options":["...","...","..."]}}

# 3. Answer with the index of the chosen option; the reply holds the next question
curl -H 'Content-Type: application/json' -d '{"position":1}' "$API/tests/9a7c.../answer"
# {"correct":true,"correct_position":1,"explanation":"","state":{...,"question":{"number":2,...}}}
```

On a server behind the site password, add `-u student:<password>` to each command.

## Things to know

- **No accounts.** Everyone using one server shares the same decks. Protect a public server with the site password ([DEPLOYMENT.md](DEPLOYMENT.md)).
- **Open tests live in memory.** They are lost when the API restarts and forgotten after `FLASH_TEST_IDLE_HOURS` (default 6) without use. Answers are saved as progress straight away, so nothing learned is lost.
- **One API process.** Because of the above, run uvicorn with one worker, as the Dockerfile does.
- **No AI generation.** It would run on the server's Anthropic key and cost money; the desktop app offers it.
- **Limits** are set with environment variables; see [DEPLOYMENT.md](DEPLOYMENT.md#settings).

## Code

| File | What it holds |
|---|---|
| `flash/api/app.py` | `create_app()`: the routes |
| `flash/api/schemas.py` | the request and response shapes, with descriptions and examples |
| `flash/api/sessions.py` | `TestSessions`: open tests, limited in number and idle time |
| `flash/api/config.py` | `ApiConfig`: limits read from environment variables |
| `flash/api/openapi.py` | writes `docs/openapi.json` |

Run it on its own for development:

```bash
pip install -r requirements-dev.txt
uvicorn flash.api.app:create_app --factory --reload     # http://localhost:8000/docs
```
