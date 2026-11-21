"""Integration tests: FlashService on real JSON files, as the desktop app uses it."""

import os
import tempfile
import unittest

from flash.service import FlashService
from flash.storage import JsonStore
from tests.helpers import make_questions


class ServiceStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = FlashService(JsonStore(self.tmp.name))
        self.deck = self.service.save_deck("Test", "test.pdf", "bank", make_questions(10))

    def tearDown(self):
        self.tmp.cleanup()

    def reopen(self) -> FlashService:
        """A new service on the same folder, like restarting the app."""
        return FlashService(JsonStore(self.tmp.name))

    def test_a_whole_test_survives_a_restart(self):
        session = self.service.start_test(self.deck, mode="ordered", count=3, shuffle_options=False)
        for pos in (0, 1, 0):  # right, wrong, right
            self.service.answer(session, pos)
            session.next()
        self.service.save_progress()

        again = self.reopen()
        summary = again.deck_summary(again.list_decks()[0])
        self.assertEqual((summary["seen"], summary["weak"]), (3, 1))
        mistakes = again.start_test(again.get_deck(self.deck.id), mode="mistakes")
        self.assertEqual([i.question.id for i in mistakes.items], ["2"])

    def test_settings_survive_a_restart(self):
        self.service.update_settings(lang="en", font_size=14)
        settings = self.reopen().settings
        self.assertEqual((settings["lang"], settings["font_size"]), ("en", 14))

    def test_rename_and_delete_are_saved(self):
        self.service.rename_deck(self.deck, "Renamed")
        self.assertEqual(self.reopen().list_decks()[0].name, "Renamed")
        self.service.delete_deck(self.deck.id)
        self.assertEqual(self.reopen().list_decks(), [])
        self.assertEqual(os.listdir(os.path.join(self.tmp.name, "decks")), [])


if __name__ == "__main__":
    unittest.main()
