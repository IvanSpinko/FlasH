"""Integration tests for JsonStore: real files in a temporary folder."""

import json
import os
import tempfile
import unittest
from unittest import mock

from flash.storage import JsonStore, Repository, data_dir
from tests.helpers import make_questions


class JsonStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.store = JsonStore(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def reopen(self) -> JsonStore:
        return JsonStore(self.root)

    def test_is_a_repository(self):
        self.assertIsInstance(self.store, Repository)

    def test_decks_are_saved_and_loaded(self):
        deck = self.store.create_deck("Krok", "krok.pdf", "bank", make_questions(3))
        self.assertEqual(len(deck.id), 12)
        self.assertTrue(os.path.exists(os.path.join(self.root, "decks", f"{deck.id}.json")))
        self.assertEqual(self.reopen().load_deck(deck.id), deck)

    def test_list_is_newest_first(self):
        with mock.patch("flash.storage.json_store.datetime") as clock:
            clock.now.return_value.isoformat.side_effect = ["2026-01-01T10:00:00", "2026-02-01T10:00:00"]
            old = self.store.create_deck("Old", "", "bank", make_questions(1))
            new = self.store.create_deck("New", "", "bank", make_questions(1))
        self.assertEqual([d.id for d in self.reopen().list_decks()], [new.id, old.id])

    def test_a_broken_file_is_skipped_not_fatal(self):
        deck = self.store.create_deck("Good", "", "bank", make_questions(1))
        with open(os.path.join(self.root, "decks", "broken.json"), "w") as f:
            f.write("{ not json")
        self.assertEqual([d.id for d in self.store.list_decks()], [deck.id])
        self.assertIsNone(self.store.load_deck("broken"))

    def test_progress_is_saved_and_summarised(self):
        deck = self.store.create_deck("Krok", "", "bank", make_questions(4))
        for qid, correct in [("1", True), ("1", True), ("2", False), ("3", True)]:
            self.store.record(deck.id, qid, correct)
        self.store.save_progress()
        again = self.reopen()
        self.assertEqual(again.summary(deck), {"total": 4, "seen": 3, "learned": 1, "weak": 1})
        self.assertEqual(again.stats(deck.id)["2"]["wrong"], 1)

    def test_reset_and_delete(self):
        deck = self.store.create_deck("Krok", "", "bank", make_questions(2))
        self.store.record(deck.id, "1", True)
        self.store.reset_progress(deck.id)
        self.assertEqual(self.reopen().stats(deck.id), {})

        self.store.record(deck.id, "1", True)
        self.store.save_progress()
        self.store.delete_deck(deck.id)
        again = self.reopen()
        self.assertIsNone(again.load_deck(deck.id))
        self.assertNotIn(deck.id, again.progress)
        self.store.delete_deck(deck.id)  # deleting twice is fine

    def test_settings_keep_defaults_for_missing_keys(self):
        self.store.settings["lang"] = "en"
        self.store.save_settings()
        with open(os.path.join(self.root, "settings.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["lang"], "en")
        again = self.reopen()
        self.assertEqual((again.settings["lang"], again.settings["theme"]), ("en", "system"))

    def test_writes_leave_no_temporary_files(self):
        self.store.create_deck("Krok", "", "bank", make_questions(2))
        self.store.save_progress()
        self.store.save_settings()
        leftovers = [n for _, _, names in os.walk(self.root) for n in names if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_non_ascii_text_is_kept(self):
        deck = self.store.create_deck("Біохімія", "", "bank", make_questions(1))
        deck.questions[0].text = "Що таке гліколіз?"
        self.store.save_deck(deck)
        self.assertEqual(self.reopen().load_deck(deck.id).questions[0].text, "Що таке гліколіз?")


class DataDirTests(unittest.TestCase):
    def test_flash_data_dir_wins_and_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "data")
            with mock.patch.dict(os.environ, {"FLASH_DATA_DIR": target}):
                self.assertEqual(data_dir(), target)
            self.assertTrue(os.path.isdir(os.path.join(target, "decks")))


if __name__ == "__main__":
    unittest.main()
