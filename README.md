# ⚡ FlasH

**UA** · [EN](#english)

FlasH — настільна програма для Windows, яка робить тести з ваших навчальних файлів. Даєте їй PDF, і вона створює з нього тести для практики.

- **Готові збірники тестів** (наприклад, «Крок», ККР): FlasH сам знаходить питання й варіанти відповідей. За замовчуванням правильною вважається перша відповідь, як у таких збірниках. Відповідь також можна позначити `*` або `+`. Нумерація необов'язкова, варіанти, що переносяться на кілька рядків, і питання, розірвані між сторінками, склеюються правильно.
- **Звичайний конспект чи підручник**: питання генеруються
  - **офлайн**: швидко й безкоштовно. Це питання на визначення («Що таке X?») і питання із пропуском;
  - **через ШІ (Claude)**: якісніші питання з поясненнями. Потрібні інтернет і API-ключ Anthropic.
- **Режими тесту**: «розумний» (спочатку слабкі й нові питання), випадковий, по порядку, лише помилки, лише нові. Можна вибрати кількість питань і діапазон (наприклад, № 100–200).
- **Прогрес**: для кожного питання зберігається, скільки разів ви відповіли правильно чи неправильно. Після тесту можна переглянути помилки й пройти їх ще раз.
- **Мови інтерфейсу**: українська та англійська.
- **Світла й темна тема**, а також режим «як у системі». Перемикач є в шапці програми, у темній темі заголовок вікна Windows теж темний.
- **Легка**: Tkinter + PyMuPDF, імпорт 80-сторінкового PDF триває менше секунди, програма займає близько 60 МБ оперативної пам'яті. Працює на слабких ноутбуках.
- **Керування з клавіатури**: `1`–`5` вибирають відповідь, `Enter` переходить до наступного питання.

### Запуск

Готова збірка: `dist\FlasH\FlasH.exe` (після `build.bat`). Python для неї не потрібен, достатньо скопіювати всю папку `dist\FlasH`.

З вихідного коду (Python 3.10+):

```bat
py -m pip install -r requirements.txt
py run_flash.py
```

Збірка `.exe`:

```bat
build.bat
```

Дані (тести, прогрес, налаштування) зберігаються в `%APPDATA%\FlasH`. Щоб використати іншу папку, задайте змінну `FLASH_DATA_DIR`.

### Обмеження

- Скановані PDF (лише зображення, без тексту) поки не підтримуються, бо для них потрібне розпізнавання тексту (OCR).
- Наразі підтримуються формати PDF, TXT і MD. Інші формати можна додати в `flash/core/extract.py`.

---

## English

FlasH is a Windows desktop app that turns study documents into practice tests.

- **Ready-made test banks**: FlasH detects questions and options automatically. The first option is treated as correct by default, as in "Krok"-style collections, and answers can also be marked with `*`/`+`. Numbering is optional. Options that wrap onto several lines and questions split across pages are joined correctly.
- **Plain notes or textbooks**: questions are generated
  - **offline**: instant and free. These are definition and fill-in-the-blank questions;
  - **with AI (Claude)**: better questions with explanations. Needs internet and an Anthropic API key.
- **Test modes**: smart (weak and new questions first), random, in order, mistakes only, new only. You can set the number of questions and a question range.
- **Progress**: right and wrong answers are tracked for each question. After a test you can review your mistakes and retry them.
- **UI languages**: Ukrainian and English.
- **Light and dark themes**, plus a mode that follows the Windows setting. The switch is in the header.
- **Lightweight**: Tkinter + PyMuPDF. An 80-page PDF imports in under a second, and the app uses about 60 MB of RAM.

Run from source with `py -m pip install -r requirements.txt` and `py run_flash.py`. Build the exe with `build.bat`.

## Project layout

Every screen talks to FlasH through `FlashService`. The desktop app calls it directly, so it works offline; the web API reuses the same service.

Diagrams of how the parts fit together are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
flash/
  service.py        FlashService: the one entry point to the logic (no UI code)
  core/             the logic, no UI and no storage
    model.py          Question and Deck
    extract.py        PDF/TXT/MD -> lines (PyMuPDF, falls back to pypdf)
    parser.py         test-bank parser (stems, wrapped options, page breaks)
    generator.py      offline question generator for plain text
    ai.py             optional Claude-based generator (structured JSON output)
    importer.py       file -> questions pipeline
    quiz.py           question selection + test session logic
  storage/          where decks, progress and settings are kept
    base.py           Repository: what any storage must provide
    json_store.py     JsonStore: JSON files in %APPDATA%\FlasH (~/FlasH on macOS/Linux)
  desktop/          Tkinter app
    app.py            main window and import flow
    library_view.py   deck list
    quiz_view.py      test screen
    results_view.py   results and mistakes
    dialogs.py        setup, rename, settings, offline/AI choice, browse, progress
    widgets.py        shared building blocks
    theme.py          light/dark palettes and ttk styling
    i18n.py           UA/EN strings
  api/              optional web API (FastAPI) used by the web app
    app.py            the routes
    schemas.py        request and response shapes (documented in OpenAPI)
    sessions.py       open tests, limited in number and idle time
    config.py         limits from environment variables
    openapi.py        writes docs/openapi.json
frontend/           optional web app (React): runs in any browser, including phones
  src/                screens, API client, translations, and their tests (*.test.tsx)
  e2e/                browser tests (Playwright)
compose.yaml        starts the web API and the web app together
compose.prod.yaml   adds HTTPS and a site password for a public server
deploy/             Caddyfile, update and backup scripts for the server
tests/              unit/, integration/ and e2e/ tests, with shared fakes
docs/               architecture, deployment, API and testing guides; openapi.json
```

## Web version (optional)

FlasH can also run as a website that works in any browser, including on phones. It is two containers: the web app (`frontend/`, React) and the web API (`flash/api`). The desktop app doesn't need either of them.

```bash
docker compose up --build
```

Then open http://localhost:8080. On a phone in the same Wi-Fi network, open `http://<this computer's IP>:8080`; in the browser menu, "Add to Home Screen" makes it look like an app. The API's own docs are at http://localhost:8080/api/docs. Decks and progress are kept in the Docker volume `flash-data`.

To work on the web app with live reload, run the API (`uvicorn flash.api.app:create_app --factory`, after `pip install -r requirements-api.txt`) and, in `frontend/`, `npm install` and `npm run dev`.

The API can also run on its own:

```bash
docker build -t flash-api .
docker run -p 8000:8000 -v flash-data:/data flash-api
```

This first version has no user accounts (everyone using the server shares the same decks), keeps running tests in memory, and doesn't offer AI generation.

To put it online with HTTPS and a password, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). The API is described in [docs/API.md](docs/API.md) and in OpenAPI form at `/api/docs`.

## Development

```bash
pip install -r requirements-dev.txt               # the app, the API, and the test and lint tools
python -m unittest discover -s tests -t .         # all Python tests
ruff check . && ruff format .                     # lint (bugs + docstrings) and format
cd frontend && npm install && npm test            # web app tests
```

What each kind of test covers, and how to run the browser tests, is in [docs/TESTING.md](docs/TESTING.md). Every public function has a docstring; `ruff check` fails if a new one doesn't.

| Guide | What it covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | how the parts fit together, with diagrams |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | putting the web version on a server (AWS Lightsail), updates, backups |
| [docs/API.md](docs/API.md) | the web API, with examples; full reference in `docs/openapi.json` |
| [docs/TESTING.md](docs/TESTING.md) | unit, integration and end-to-end tests, fakes and mocks, CI |
