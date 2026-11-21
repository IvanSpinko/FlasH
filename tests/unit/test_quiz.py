"""Unit tests for the quiz rules (flash.core.quiz): picking questions, shuffling, scoring."""

import random
import unittest

from flash.core.model import Deck
from flash.core.quiz import MODES, Session, select_questions
from tests.helpers import make_questions


def make_deck(n: int = 20) -> Deck:
    deck = Deck(id="deck", name="Test", source="test.pdf", kind="bank", created="", questions=make_questions(n, 5))
    for i, q in enumerate(deck.questions, 1):
        q.id = str(i)
    return deck


def stat(seen=1, right=0, wrong=0, streak=0) -> dict:
    return {"seen": seen, "right": right, "wrong": wrong, "streak": streak}


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.deck = make_deck()

    def test_shuffled_options_keep_the_correct_answer(self):
        session = Session.create(self.deck.id, self.deck.questions, shuffle_options=True, rng=random.Random(3))
        for item in session.items:
            self.assertTrue(item.options[item.correct_pos].startswith("right"))
        self.assertTrue(any(item.correct_pos != 0 for item in session.items))

    def test_without_shuffling_the_order_is_kept(self):
        session = Session.create(self.deck.id, self.deck.questions[:3], shuffle_options=False)
        self.assertEqual([i.correct_pos for i in session.items], [0, 0, 0])
        self.assertEqual(session.items[0].options, self.deck.questions[0].options)

    def test_scoring_and_mistakes(self):
        session = Session.create(self.deck.id, self.deck.questions[:3], shuffle_options=False)
        self.assertTrue(session.answer(0))
        session.next()
        self.assertFalse(session.answer(2))
        session.next()
        session.next()  # skipped
        self.assertTrue(session.finished)
        self.assertIsNone(session.current)
        self.assertEqual(session.score, 1)
        self.assertEqual(len(session.mistakes), 1)
        self.assertEqual(len(session.answered), 2)

    def test_a_question_can_only_be_answered_once(self):
        session = Session.create(self.deck.id, self.deck.questions[:1], shuffle_options=False)
        session.answer(0)
        with self.assertRaises(ValueError):
            session.answer(1)
        session.next()
        with self.assertRaises(ValueError):
            session.answer(0)

    def test_an_empty_session_is_finished_at_once(self):
        session = Session.create(self.deck.id, [])
        self.assertIsNone(session.current)
        self.assertEqual((session.score, session.mistakes), (0, []))


class SelectQuestionsTests(unittest.TestCase):
    def setUp(self):
        self.deck = make_deck()

    def ids(self, questions):
        return [q.id for q in questions]

    def test_ordered_range_is_one_based_and_inclusive(self):
        picked = select_questions(self.deck, {}, mode="ordered", start=5, end=9)
        self.assertEqual(self.ids(picked), ["5", "6", "7", "8", "9"])

    def test_count_limits_the_test(self):
        self.assertEqual(len(select_questions(self.deck, {}, mode="random", count=7)), 7)
        self.assertEqual(len(select_questions(self.deck, {}, mode="random", count=100)), 20)

    def test_random_is_a_permutation(self):
        picked = select_questions(self.deck, {}, mode="random", rng=random.Random(1))
        self.assertEqual(sorted(self.ids(picked), key=int), [str(i) for i in range(1, 21)])
        self.assertNotEqual(self.ids(picked), [str(i) for i in range(1, 21)])

    def test_mistakes_mode_takes_wrong_answers_not_yet_relearned(self):
        stats = {
            "3": stat(wrong=1, streak=0),  # last answer wrong
            "4": stat(right=1, streak=1),  # never wrong
            "5": stat(seen=3, wrong=1, right=2, streak=2),  # wrong once, then learned
            "6": stat(seen=2, wrong=1, right=1, streak=1),  # wrong once, right once since
        }
        picked = select_questions(self.deck, stats, mode="mistakes")
        self.assertEqual(sorted(self.ids(picked)), ["3", "6"])

    def test_unseen_mode_skips_answered_questions(self):
        stats = {"1": stat(), "2": stat()}
        picked = select_questions(self.deck, stats, mode="unseen")
        self.assertEqual(len(picked), 18)
        self.assertNotIn("1", self.ids(picked))

    def test_smart_mode_puts_weak_and_new_questions_first(self):
        # Questions 1-10 are well known; 11-20 are new. New ones should mostly come first.
        stats = {str(i): stat(seen=5, right=5, streak=5) for i in range(1, 11)}
        firsts = []
        for seed in range(20):
            picked = select_questions(self.deck, stats, mode="smart", count=5, rng=random.Random(seed))
            firsts += [int(q.id) for q in picked]
        new_share = sum(1 for i in firsts if i > 10) / len(firsts)
        self.assertGreater(new_share, 0.8)

    def test_every_mode_returns_a_list(self):
        for mode in MODES:
            self.assertIsInstance(select_questions(self.deck, {}, mode=mode), list, mode)


if __name__ == "__main__":
    unittest.main()
