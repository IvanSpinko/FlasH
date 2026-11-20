# FlasH architecture

FlasH has one "brain" and two front ends. The desktop app and the web API both go through `FlashService`, so they share the same logic. Only the web API needs a network.

- **The desktop app stays offline.** The Tkinter window calls the service directly, inside the same program. No server is involved.
- **The web API reuses the brain.** FastAPI, running in Docker, calls the same service methods, so a fix to the parser helps both.
- **Storage can be swapped.** The service only knows the `Repository` interface: JSON files today, a database later.

## How the code is organised

```mermaid
flowchart TB
    user["Desktop user<br/>FlasH.exe · run_flash.py · python -m flash"]
    client["Web client<br/>browser /docs · curl · future phone app"]

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
    client -. "HTTP + JSON" .-> api
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
        lint["Lint<br/>ruff check · ruff format --check"]
        matrix["Tests × 4<br/>Windows · macOS · Ubuntu with Python 3.13<br/>Ubuntu with Python 3.10"]
        apijob["Web API + Docker<br/>API tests · docker build · /health"]
    end

    tag["git tag v0.2.0<br/>git push origin v0.2.0"] -- "starts" --> build

    subgraph release["Windows build · release.yml · one Windows machine"]
        build["build.bat<br/>Python 3.13 · PyInstaller"] --> check["Check output<br/>FlasH.exe and zip exist"] --> artifact["Artifact<br/>zip kept on the run"] --> gh["GitHub Release<br/>FlasH-Windows.zip"]
    end

    classDef hub fill:#ebe9fe,stroke:#4f46e5,stroke-width:2px,color:#1b1f2a
    class gh hub
```

A branch push that changes `build.bat`, `requirements.txt`, `run_flash.py` or `packaging/` runs the same Windows build but stops at the artifact. Only a `v*` tag publishes a release.
