"""Unit tests for the data model (flash.core.model): converting to and from JSON-ready dicts."""

import unittest

from flash.core.model import Deck, Question


class QuestionTests(unittest.TestCase):
    def test_round_trip(self):
        q = Question(text="2 + 2?", options=["4", "3", "5"], answer=0, id="7", explanation="Arithmetic.")
        self.assertEqual(Question.from_dict(q.to_dict()), q)

    def test_empty_explanation_is_not_stored(self):
        self.assertNotIn("explanation", Question(text="Q?", options=["a", "b", "c"]).to_dict())

    def test_old_files_without_optional_fields_still_load(self):
        q = Question.from_dict({"q": "Q?", "options": ("a", "b", "c")})
        self.assertEqual((q.answer, q.id, q.explanation, q.options), (0, "", "", ["a", "b", "c"]))


class DeckTests(unittest.TestCase):
    def test_round_trip(self):
        deck = Deck(
            id="abc",
            name="Krok",
            source="krok.pdf",
            kind="bank",
            created="2026-11-20T10:00:00",
            questions=[Question(text="Q?", options=["a", "b", "c"], id="1")],
        )
        self.assertEqual(Deck.from_dict(deck.to_dict()), deck)

    def test_defaults_for_missing_fields(self):
        deck = Deck.from_dict({"id": "x", "name": "Old"})
        self.assertEqual((deck.source, deck.kind, deck.created, deck.questions), ("", "bank", "", []))


if __name__ == "__main__":
    unittest.main()
