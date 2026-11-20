"""Local storage: decks, progress and settings as JSON in %APPDATA%\\FlasH."""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from datetime import datetime

from .model import Deck


def data_dir() -> str:
    base = os.environ.get("FLASH_DATA_DIR")
    if not base:
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "FlasH")
    os.makedirs(os.path.join(base, "decks"), exist_ok=True)
    return base


def _read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path: str, data) -> None:
    # Write atomically so a power cut never leaves a half-written file.
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


DEFAULT_SETTINGS = {
    "lang": "uk",
    "theme": "system",
    "font_size": 12,
    "shuffle_options": True,
    "instant_feedback": True,
    "default_count": 30,
    "ai_model": "claude-opus-5-5",
    "api_key": "",
}


class Store:
    def __init__(self, root: str | None = None):
        self.root = root or data_dir()
        os.makedirs(os.path.join(self.root, "decks"), exist_ok=True)
        self._settings_path = os.path.join(self.root, "settings.json")
        self._progress_path = os.path.join(self.root, "progress.json")
        self.settings = {**DEFAULT_SETTINGS, **_read_json(self._settings_path, {})}
        self.progress: dict[str, dict[str, dict]] = _read_json(self._progress_path, {})

    # settings ---------------------------------------------------------
    def save_settings(self) -> None:
        _write_json(self._settings_path, self.settings)

    # decks ------------------------------------------------------------
    def _deck_path(self, deck_id: str) -> str:
        return os.path.join(self.root, "decks", f"{deck_id}.json")

    def list_decks(self) -> list[Deck]:
        decks = []
        folder = os.path.join(self.root, "decks")
        for name in os.listdir(folder):
            if name.endswith(".json"):
                d = _read_json(os.path.join(folder, name), None)
                if d:
                    decks.append(Deck.from_dict(d))
        decks.sort(key=lambda d: d.created, reverse=True)
        return decks

    def load_deck(self, deck_id: str) -> Deck | None:
        d = _read_json(self._deck_path(deck_id), None)
        return Deck.from_dict(d) if d else None

    def create_deck(self, name: str, source: str, kind: str, questions) -> Deck:
        deck = Deck(
            id=uuid.uuid4().hex[:12],
            name=name,
            source=source,
            kind=kind,
            created=datetime.now().isoformat(timespec="seconds"),
            questions=list(questions),
        )
        for i, q in enumerate(deck.questions, 1):
            q.id = str(i)
        self.save_deck(deck)
        return deck

    def save_deck(self, deck: Deck) -> None:
        _write_json(self._deck_path(deck.id), deck.to_dict())

    def delete_deck(self, deck_id: str) -> None:
        try:
            os.remove(self._deck_path(deck_id))
        except FileNotFoundError:
            pass
        if self.progress.pop(deck_id, None) is not None:
            self.save_progress()

    # progress ---------------------------------------------------------
    def stats(self, deck_id: str) -> dict[str, dict]:
        return self.progress.setdefault(deck_id, {})

    def record(self, deck_id: str, qid: str, correct: bool) -> None:
        s = self.stats(deck_id).setdefault(qid, {"seen": 0, "right": 0, "wrong": 0, "streak": 0})
        s["seen"] += 1
        if correct:
            s["right"] += 1
            s["streak"] = max(s["streak"], 0) + 1
        else:
            s["wrong"] += 1
            s["streak"] = 0
        s["last"] = int(time.time())

    def reset_progress(self, deck_id: str) -> None:
        self.progress[deck_id] = {}
        self.save_progress()

    def save_progress(self) -> None:
        _write_json(self._progress_path, self.progress)

    def summary(self, deck: Deck) -> dict:
        st = self.progress.get(deck.id, {})
        total = len(deck.questions)
        seen = sum(1 for q in deck.questions if q.id in st)
        learned = sum(1 for q in deck.questions if st.get(q.id, {}).get("streak", 0) >= 2)
        weak = sum(1 for q in deck.questions if q.id in st and st[q.id]["streak"] == 0)
        return {"total": total, "seen": seen, "learned": learned, "weak": weak}
