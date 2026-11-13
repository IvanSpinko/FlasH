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
- Наразі підтримуються формати PDF, TXT і MD. Інші формати можна додати в `flash/extract.py`.

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
- **Lightweight**: Tkinter + PyMuPDF. An 80-page PDF imports in under a second, and the app uses about 60 MB of RAM.

Run from source with `py -m pip install -r requirements.txt` and `py run_flash.py`. Build the exe with `build.bat`.

## Project layout

```
flash/
  extract.py    PDF/TXT -> lines (PyMuPDF, falls back to pypdf)
  parser.py     test-bank parser (stems, wrapped options, page breaks)
  generator.py  offline question generator for plain text
  ai.py         optional Claude-based generator (structured JSON output)
  importer.py   file -> questions pipeline
  quiz.py       question selection + test session logic
  storage.py    JSON storage in %APPDATA%\FlasH
  i18n.py       UA/EN strings
  ui.py         Tkinter interface
tests/          unit tests: py -m unittest discover -s tests -t .
```
