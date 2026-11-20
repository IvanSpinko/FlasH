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
  api/              optional web API (FastAPI) for a future website or phone app
    app.py
tests/              unit tests: py -m unittest discover -s tests -t .
```

## Web API (optional)

The web API is a separate way to use FlasH's logic over HTTP, for example from a website or a phone app. The desktop app doesn't need it.

```bash
docker build -t flash-api .
docker run -p 8000:8000 -v flash-data:/data flash-api
```

Then open http://localhost:8000/docs to try it. Without Docker: `pip install -r requirements-api.txt` and `uvicorn flash.api.app:create_app --factory`.

This first version has no user accounts, keeps running tests in memory, and doesn't offer AI generation.
