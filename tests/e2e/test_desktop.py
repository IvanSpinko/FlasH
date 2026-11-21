"""End-to-end test of the desktop app: the real Tkinter window, driven through a whole test.

The window stays hidden. It needs a screen, so it's skipped where Tk can't open one
(for example on a Linux server without a display). Data goes to a temporary folder.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

from flash.service import FlashService
from flash.storage import JsonStore
from tests.helpers import BANK, write_text


REQUIRED = os.environ.get("FLASH_E2E_DESKTOP") == "1"
"""Set FLASH_E2E_DESKTOP=1 (CI does on Windows and macOS) to fail instead of skipping without a screen."""


def tk_can_open_a_window() -> bool:
    """True if Tk can open a window here. Checked in a separate process:
    on macOS, a second Tk window in one process can crash it.
    The first Tk start after boot can take ~25 s on a Mac, hence the long timeout."""
    probe = "import tkinter; tkinter.Tk().destroy()"
    try:
        return subprocess.run([sys.executable, "-c", probe], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@unittest.skipUnless(REQUIRED or tk_can_open_a_window(), "Tk can't open a window here (no display)")
class DesktopTests(unittest.TestCase):
    def setUp(self):
        from flash.desktop.app import App

        self.tmp = tempfile.TemporaryDirectory()
        self.data = os.path.join(self.tmp.name, "data")
        self.app = App(FlashService(JsonStore(self.data)))
        self.app.withdraw()
        self.app.update()

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass  # already closed by the test
        self.tmp.cleanup()

    def step(self):
        self.app.update()
        return type(self.app.view).__name__

    def test_import_take_a_test_retry_and_settings(self):
        app, service = self.app, self.app.service
        result = service.analyse_file(write_text(self.tmp.name, "krok.txt", BANK))
        deck = service.save_deck(result.name, result.source, "bank", result.questions)

        app.show_library()
        self.assertEqual(self.step(), "LibraryView")

        session = service.start_test(deck, mode="ordered")
        app.start_session(session, True)
        self.assertEqual(self.step(), "QuizView")
        quiz = app.view
        for i in range(3):  # right, wrong, right
            item = quiz.session.current
            quiz.choose(item.correct_pos if i != 1 else (item.correct_pos + 1) % len(item.options))
            self.step()
            quiz.go_next()
            self.step()

        self.assertEqual(self.step(), "ResultsView")
        self.assertEqual((session.score, len(session.mistakes)), (2, 1))

        app.view.retry()
        self.assertEqual(self.step(), "QuizView")
        self.assertEqual(len(app.view.session.items), 1)

        app.toggle_theme()
        self.step()
        app.change_language("en")
        self.step()
        app.show_library()
        self.assertEqual(self.step(), "LibraryView")
        app.on_close()

        with open(os.path.join(self.data, "progress.json"), encoding="utf-8") as f:
            stats = json.load(f)[deck.id]
        with open(os.path.join(self.data, "settings.json"), encoding="utf-8") as f:
            settings = json.load(f)
        self.assertEqual((len(stats), sum(s["right"] for s in stats.values())), (3, 2))
        self.assertEqual(settings["lang"], "en")
        self.assertIn(settings["theme"], ("light", "dark"))


if __name__ == "__main__":
    unittest.main()
