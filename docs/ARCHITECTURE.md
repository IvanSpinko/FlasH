# FlasH architecture

FlasH has one "brain" and two front ends. The desktop app and the web API both go through `FlashService`, so they share the same logic. The web API is used by the web app, which runs in any browser, including phones. Only the web version needs a network.

- **The desktop app stays offline.** The Tkinter window calls the service directly, inside the same program. No server is involved.
- **The web version reuses the brain.** The web app (React) talks to the web API (FastAPI), which calls the same service methods, so a fix to the parser helps both. Each runs in its own Docker container, started together with `docker compose up`.
- **Storage can be swapped.** The service only knows the `Repository` interface: JSON files today, a database later.

## How the code is organised

```mermaid
flowchart TB
    user["Desktop user<br/>FlasH.exe · run_flash.py · python -m flash"]
    phone["Student on a phone or any browser"]

    subgraph web["frontend/ · React web app, served by nginx (own container)"]
        pages["library · test setup · quiz · results<br/>Ukrainian / English · light / dark"]
    end

    subgraph desktop["flash/desktop · Tkinter window"]
        screens["app.py · library_view · quiz_view · results_view<br/>dialogs · widgets · theme · i18n"]
    end

    subgraph api["flash/api · FastAPI, run by uvicorn in Docker"]
        routes["/health · /decks · /decks/{id}/tests · /tests/{id}/answer"]
    end

    service["flash/service.py · FlashService<br/>analyse_file · generate_offline · generate_with_ai · save_deck<br/>start_test · answer · retry_mistakes · decks, progress, settings"]

    subgraph core["flash/core · the logic: no UI, no storage"]
        importer["importer.py<br/>file → questions"] --> extract["extract.py<br/>PyMuPDF: PDF → lines"] --> parser["parser.py<br/>lines → test bank"]
        generator["generator.py<br/>offline questions"]
        ai["ai.py<br/>questions with Claude"]
        quiz["quiz.py<br/>pick · shuffle · score"]
    end

    subgraph storage["flash/storage · decks, progress, settings"]
        repo["Repository<br/>base.py: what any storage must provide"]
        jsonstore["JsonStore<br/>json_store.py: used today"]
        db["Database store<br/>later, for a server"]
    end

    claude{{"Claude API (Anthropic)<br/>only for AI question generation"}}
    data[("Data folder · FLASH_DATA_DIR<br/>desktop: ~/FlasH or %APPDATA%\FlasH<br/>Docker: /data, in the volume flash-data")]

    user -- "opens the window" --> desktop
    phone -. "https://your-domain<br/>(on a server: Caddy adds HTTPS + a password)" .-> web
    web -. "/api/... (HTTP + JSON)" .-> api
    desktop -- "direct calls, in-process: works offline" --> service
    api -- "the same calls, inside Docker" --> service
    service -- "uses" --> core
    service -- "reads and writes" --> repo
    repo -- "implemented by" --> jsonstore
    repo -. "later" .-> db
    ai -. "optional: internet + API key" .-> claude
    jsonstore -- "JSON files" --> data

    classDef hub fill:#ebe9fe,stroke:#4f46e5,stroke-width:2px,color:#1b1f2a
    classDef planned stroke-dasharray:5 5
    class service hub
    class db,claude planned
```

Solid arrows are calls inside one program. Dashed arrows go over the network or aren't built yet. Each deployment runs its own copy of this code with its own data folder, and the desktop app never talks to the server.

| Folder | What it holds | Knows about the UI? | Knows about storage? |
|---|---|---|---|
| `flash/core` | reading files, parsing test banks, generating questions, quiz rules | no | no |
| `flash/storage` | the `Repository` interface and `JsonStore` | no | yes |
| `flash/service.py` | `FlashService`, the one entry point to the logic | no | only through `Repository` |
| `flash/desktop` | the Tkinter app, one module per screen | yes | no |
| `flash/api` | the optional web API | HTTP only | no |
| `frontend/` | the optional web app (React), in its own container | yes | no, only talks to the API |

How the web version runs on a public server (Caddy, the password, backups) is in [DEPLOYMENT.md](DEPLOYMENT.md); the API itself is in [API.md](API.md).

## What happens when you import a file

```mermaid
sequenceDiagram
    actor U as User
    participant F as Front end (desktop or API)
    participant S as FlashService
    participant C as core (importer, extract, parser)
    participant R as JsonStore

    U->>F: choose Krok.pdf
    F->>S: analyse_file(path)
    S->>C: read lines (PyMuPDF), find questions
    C-->>S: ImportResult: is_bank, questions, lines
    S-->>F: ImportResult
    alt the file is a test bank
        F->>S: save_deck(name, source, "bank", questions)
    else the file is plain notes
        F->>S: generate_offline(result) or generate_with_ai(result)
        S-->>F: new questions
        F->>S: save_deck(name, source, "generated" or "ai", questions)
    end
    S->>R: create_deck(...)
    R-->>S: Deck, with ids for the deck and every question
    S-->>F: Deck
    F-->>U: "Imported N questions"
```

The front end decides what to show, such as the "offline or AI?" dialog on the desktop. The service decides what happens to the data.

## What GitHub runs

```mermaid
flowchart LR
    push["git push<br/>or a pull request"] -- "starts" --> tests

    subgraph tests["Tests · tests.yml · jobs run at the same time"]
        lint["Lint<br/>ruff: bugs + docstrings<br/>formatting · shellcheck"]
        matrix["Tests × 4<br/>unit · integration · e2e<br/>Windows · macOS · Ubuntu, Python 3.13 and 3.10<br/>desktop window on Windows and macOS"]
        apijob["Web API + Docker<br/>all tests with the exact versions<br/>coverage ≥ 90% · openapi.json up to date<br/>image builds and turns healthy"]
        webjob["Web app + Compose<br/>type-check · build · Vitest<br/>both containers · Playwright in a browser<br/>production config valid"]
    end

    tag["git tag v0.2.0<br/>git push origin v0.2.0"] -- "starts" --> build

    subgraph release["Windows build · release.yml · one Windows machine"]
        build["build.bat<br/>Python 3.13 · PyInstaller"] --> check["Check output<br/>FlasH.exe and zip exist"] --> artifact["Artifact<br/>zip kept on the run"] --> gh["GitHub Release<br/>FlasH-Windows.zip"]
    end

    button["Actions → Deploy<br/>Run workflow"] -- "starts" --> deploy

    subgraph deployflow["Deploy · deploy.yml · by hand"]
        deploy["SSH to the server<br/>deploy/update.sh"] --> health["Site answers<br/>/api/health"]
    end

    classDef hub fill:#ebe9fe,stroke:#4f46e5,stroke-width:2px,color:#1b1f2a
    class gh,health hub
```

A branch push that changes `build.bat`, `requirements.txt`, `run_flash.py` or `packaging/` runs the same Windows build but stops at the artifact. Only a `v*` tag publishes a release. Deploying is always started by hand, and only works once the server and its secrets are set up ([DEPLOYMENT.md](DEPLOYMENT.md#7-updating)). Dependabot opens pull requests for new dependency versions every week; the tests above check each one.

What each kind of test covers is in [TESTING.md](TESTING.md).
