"""Unit tests for FlashService, with an in-memory storage (MemoryStore) and mocks.

No files are read or written here; the same service on real JSON files is tested in
tests/integration/test_service_storage.py.
"""

import os
import unittest
from unittest import mock

from flash.core.importer import ImportResult
from flash.core.model import Question
from flash.service import FlashService
from flash.storage import Repository
from tests.fakes import MemoryStore
from tests.helpers import make_questions


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.service = FlashService(self.store)
        self.deck = self.service.save_deck("Test", "test.pdf", "bank", make_questions(10))

    def test_the_fake_is_a_repository(self):
        self.assertIsInstance(self.store, Repository)

    def test_save_deck_gives_ids(self):
        self.assertEqual([q.id for q in self.deck.questions], [str(i) for i in range(1, 11)])
        self.assertEqual(self.service.get_deck(self.deck.id), self.deck)
        self.assertEqual(self.service.list_decks(), [self.deck])

    def test_answers_are_recorded(self):
        session = self.service.start_test(self.deck, mode="ordered", count=3, shuffle_options=False)
        self.assertTrue(self.service.answer(session, 0))  # first option is right without shuffling
        session.next()
        self.assertFalse(self.service.answer(session, 1))
        self.assertEqual(self.store.progress[self.deck.id]["1"]["right"], 1)
        self.assertEqual(self.store.progress[self.deck.id]["2"]["wrong"], 1)
        self.assertEqual(self.service.deck_summary(self.deck)["seen"], 2)

    def test_start_test_passes_the_selection_on(self):
        session = self.service.start_test(self.deck, mode="ordered", start=3, end=5, shuffle_options=False)
        self.assertEqual([i.question.id for i in session.items], ["3", "4", "5"])

    def test_empty_selection_returns_none(self):
        self.assertIsNone(self.service.start_test(self.deck, mode="mistakes"))

    def test_retry_has_only_the_mistakes(self):
        session = self.service.start_test(self.deck, mode="ordered", count=4, shuffle_options=False)
        for pos in (0, 1, 0, 1):  # right, wrong, right, wrong
            self.service.answer(session, pos)
            session.next()
        retry = self.service.retry_mistakes(session)
        self.assertEqual(sorted(i.question.id for i in retry.items), ["2", "4"])
        self.assertEqual(retry.deck_id, self.deck.id)

    def test_rename_reset_and_delete(self):
        self.service.rename_deck(self.deck, "Renamed")
        self.assertEqual(self.service.list_decks()[0].name, "Renamed")

        session = self.service.start_test(self.deck, count=1)
        self.service.answer(session, 0)
        self.service.reset_progress(self.deck.id)
        self.assertEqual(self.service.deck_summary(self.deck)["seen"], 0)

        self.service.delete_deck(self.deck.id)
        self.assertEqual(self.service.list_decks(), [])

    def test_settings_are_updated_and_saved(self):
        self.service.update_settings(lang="en", font_size=14)
        self.assertEqual((self.service.settings["lang"], self.service.settings["font_size"]), ("en", 14))
        self.assertEqual(self.store.saves, 1)

    def test_save_progress_writes_once(self):
        self.service.save_progress()
        self.assertEqual(self.store.saves, 1)


class ImportTests(unittest.TestCase):
    """The service only passes work on to flash.core; mocks check that it does so correctly."""

    def setUp(self):
        self.service = FlashService(MemoryStore())
        self.result = ImportResult(name="notes", source="notes.txt", lines=["line"], questions=[], is_bank=False)

    def test_analyse_file_uses_the_importer(self):
        with mock.patch("flash.service.analyse_file", return_value=self.result) as analyse:
            self.assertIs(self.service.analyse_file("notes.txt", progress=print), self.result)
        analyse.assert_called_once_with("notes.txt", print)

    def test_generate_offline_uses_the_lines(self):
        made = [Question(text="Q?", options=["a", "b", "c"])]
        with mock.patch("flash.core.generator.generate_questions", return_value=made) as generate:
            self.assertEqual(self.service.generate_offline(self.result), made)
        generate.assert_called_once_with(["line"])

    def test_generate_with_ai_uses_the_saved_key_and_model(self):
        self.service.update_settings(api_key="sk-saved", ai_model="claude-haiku-5-5")
        with mock.patch("flash.core.ai.generate_questions", return_value=[]) as generate:
            self.service.generate_with_ai(self.result)
        args, kwargs = generate.call_args
        self.assertEqual(args, (["line"], "sk-saved", "claude-haiku-5-5"))

    def test_ai_key_falls_back_to_the_environment(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env"}):
            self.assertEqual(self.service.ai_key(), "sk-env")
            self.service.update_settings(api_key="sk-saved")
            self.assertEqual(self.service.ai_key(), "sk-saved")

    def test_ai_problem_codes(self):
        with mock.patch("flash.core.ai.is_available", return_value=False):
            self.assertEqual(self.service.ai_problem(), "unavailable")
        with mock.patch("flash.core.ai.is_available", return_value=True), mock.patch.dict(os.environ, clear=True):
            self.assertEqual(self.service.ai_problem(), "no_key")
            self.service.update_settings(api_key="sk-test")
            self.assertIsNone(self.service.ai_problem())


if __name__ == "__main__":
    unittest.main()
