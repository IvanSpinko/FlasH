import os
import tempfile
import unittest
from unittest import mock

from flash.model import Question
from flash.service import FlashService
from flash.storage import JsonStore, Repository

BANK = """1. Which organ pumps blood?
Heart
Liver
Lungs
Kidneys

2. Which gas do plants absorb?
Carbon dioxide
Oxygen
Nitrogen
Helium

3. What is the chemical symbol of sodium?
Na
K
Ca
S
"""


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = FlashService(JsonStore(self.tmp.name))
        qs = [Question(text=f"Q{i}?", options=[f"right{i}", "a", "b", "c"]) for i in range(1, 11)]
        self.deck = self.service.save_deck("Test", "test.pdf", "bank", qs)

    def tearDown(self):
        self.tmp.cleanup()

    def test_import_a_test_bank_file(self):
        path = os.path.join(self.tmp.name, "bank.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(BANK)
        result = self.service.analyse_file(path)
        self.assertTrue(result.is_bank)
        self.assertEqual([q.options[q.answer] for q in result.questions], ["Heart", "Carbon dioxide", "Na"])

        deck = self.service.save_deck(result.name, result.source, "bank", result.questions)
        self.assertIn(deck.id, [d.id for d in self.service.list_decks()])

    def test_answers_are_saved_as_progress(self):
        session = self.service.start_test(self.deck, mode="ordered", count=3, shuffle_options=False)
        self.assertTrue(self.service.answer(session, 0))  # first option is right without shuffling
        session.next()
        self.assertFalse(self.service.answer(session, 1))
        self.service.save_progress()

        reopened = FlashService(JsonStore(self.tmp.name))
        summary = reopened.deck_summary(reopened.list_decks()[0])
        self.assertEqual(summary["seen"], 2)
        self.assertEqual(summary["weak"], 1)

    def test_retry_has_only_the_mistakes(self):
        session = self.service.start_test(self.deck, mode="ordered", count=4, shuffle_options=False)
        for pos in (0, 1, 0, 1):  # right, wrong, right, wrong
            self.service.answer(session, pos)
            session.next()
        retry = self.service.retry_mistakes(session)
        self.assertEqual(sorted(i.question.id for i in retry.items), ["2", "4"])

    def test_empty_selection_returns_none(self):
        self.assertIsNone(self.service.start_test(self.deck, mode="mistakes"))

    def test_rename_reset_and_delete(self):
        self.service.rename_deck(self.deck, "Renamed")
        self.assertEqual(self.service.list_decks()[0].name, "Renamed")

        session = self.service.start_test(self.deck, count=1)
        self.service.answer(session, 0)
        self.service.reset_progress(self.deck.id)
        self.assertEqual(self.service.deck_summary(self.deck)["seen"], 0)

        self.service.delete_deck(self.deck.id)
        self.assertEqual(self.service.list_decks(), [])

    def test_settings_are_saved(self):
        self.service.update_settings(lang="en", font_size=14)
        reopened = FlashService(JsonStore(self.tmp.name))
        self.assertEqual((reopened.settings["lang"], reopened.settings["font_size"]), ("en", 14))

    def test_ai_problem_codes(self):
        with mock.patch("flash.ai.is_available", return_value=False):
            self.assertEqual(self.service.ai_problem(), "unavailable")
        with mock.patch("flash.ai.is_available", return_value=True), mock.patch.dict(os.environ, clear=True):
            self.assertEqual(self.service.ai_problem(), "no_key")
            self.service.update_settings(api_key="sk-test")
            self.assertIsNone(self.service.ai_problem())


class MemoryStore:
    """A storage that keeps everything in memory: no files at all."""

    def __init__(self):
        self.settings = {"shuffle_options": False}
        self.decks = {}
        self.progress = {}

    def save_settings(self):
        pass

    def list_decks(self):
        return list(self.decks.values())

    def load_deck(self, deck_id):
        return self.decks.get(deck_id)

    def create_deck(self, name, source, kind, questions):
        from flash.model import Deck

        deck = Deck(id=str(len(self.decks) + 1), name=name, source=source, kind=kind, created="", questions=questions)
        for i, q in enumerate(deck.questions, 1):
            q.id = str(i)
        self.decks[deck.id] = deck
        return deck

    def save_deck(self, deck):
        self.decks[deck.id] = deck

    def delete_deck(self, deck_id):
        self.decks.pop(deck_id, None)

    def stats(self, deck_id):
        return self.progress.setdefault(deck_id, {})

    def record(self, deck_id, question_id, correct):
        s = self.stats(deck_id).setdefault(question_id, {"seen": 0, "right": 0, "wrong": 0, "streak": 0})
        s["seen"] += 1
        s["right" if correct else "wrong"] += 1
        s["streak"] = s["streak"] + 1 if correct else 0

    def reset_progress(self, deck_id):
        self.progress[deck_id] = {}

    def save_progress(self):
        pass

    def summary(self, deck):
        st = self.progress.get(deck.id, {})
        return {"total": len(deck.questions), "seen": len(st), "learned": 0, "weak": 0}


class RepositoryTests(unittest.TestCase):
    def test_json_store_is_a_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsInstance(JsonStore(tmp), Repository)

    def test_service_works_with_any_repository(self):
        store = MemoryStore()
        self.assertIsInstance(store, Repository)
        service = FlashService(store)
        deck = service.save_deck("Memory", "", "bank", [Question(text="Q?", options=["yes", "no", "maybe"])])
        session = service.start_test(deck, count=1)
        self.assertTrue(service.answer(session, session.current.correct_pos))
        self.assertEqual(service.deck_summary(deck)["seen"], 1)


if __name__ == "__main__":
    unittest.main()
