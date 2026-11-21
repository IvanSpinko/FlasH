"""Unit tests for the offline question generator (flash.core.generator)."""

import unittest

from flash.core import generator
from tests.helpers import NOTES

UK_NOTES = """Гліколіз — це процес розщеплення глюкози до пірувату в цитоплазмі клітини.
Глюконеогенез — це синтез глюкози з невуглеводних попередників у печінці.
Ліполіз — це гідроліз триацилгліцеролів до гліцеролу та жирних кислот.
Трансамінування — це перенесення аміногрупи з амінокислоти на кетокислоту.
Декарбоксилювання — це відщеплення карбоксильної групи у вигляді вуглекислого газу.
Фенілкетонурія спричинена дефіцитом фенілаланінгідроксилази в гепатоцитах.
Хвороба Гірке пов'язана з дефіцитом глюкозо-6-фосфатази у печінці та нирках.
Алкаптонурія виникає через недостатність оксидази гомогентизинової кислоти.""".splitlines()


class GeneratorTests(unittest.TestCase):
    def assert_valid(self, questions):
        for q in questions:
            self.assertGreaterEqual(len(q.options), 4, q)
            self.assertEqual(len({o.lower() for o in q.options}), len(q.options), q)
            self.assertTrue(0 <= q.answer < len(q.options), q)

    def test_ukrainian_notes_make_valid_questions(self):
        questions = generator.generate_questions(UK_NOTES, seed=1)
        self.assertGreaterEqual(len(questions), 5)
        self.assert_valid(questions)

    def test_english_notes_make_valid_questions(self):
        questions = generator.generate_questions(NOTES.splitlines(), seed=1)
        self.assertGreater(len(questions), 0)
        self.assert_valid(questions)

    def test_same_seed_same_questions(self):
        first = generator.generate_questions(UK_NOTES, seed=42)
        second = generator.generate_questions(UK_NOTES, seed=42)
        self.assertEqual(first, second)

    def test_limit(self):
        self.assertLessEqual(len(generator.generate_questions(UK_NOTES, limit=2, seed=1)), 2)

    def test_too_little_text_gives_no_questions(self):
        self.assertEqual(generator.generate_questions(["Short."]), [])


class TextHelperTests(unittest.TestCase):
    def test_detect_language(self):
        self.assertEqual(generator.detect_language("Це текст українською мовою."), "uk")
        self.assertEqual(generator.detect_language("This is an English text."), "en")

    def test_lines_to_text_joins_wrapped_lines_and_hyphenation(self):
        text = generator.lines_to_text(["The mito-", "chondrion is", "small.", "", "Next paragraph."])
        self.assertEqual(text, "The mitochondrion is small.\nNext paragraph.")

    def test_split_sentences_drops_very_short_ones(self):
        text = "Too short. This sentence is long enough to be used for a question. Ok."
        self.assertEqual(generator.split_sentences(text), ["This sentence is long enough to be used for a question."])


if __name__ == "__main__":
    unittest.main()
