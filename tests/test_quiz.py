import random
import tempfile
import unittest

from flash.generator import generate_questions
from flash.model import Question
from flash.quiz import Session, select_questions
from flash.storage import Store


def make_store(tmp):
    store = Store(tmp)
    qs = [Question(text=f"Q{i}?", options=[f"right{i}", "a", "b", "c", "d"]) for i in range(1, 21)]
    deck = store.create_deck("Test", "test.pdf", "bank", qs)
    return store, deck


class QuizTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store, self.deck = make_store(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_shuffled_options_keep_correct_answer(self):
        rng = random.Random(3)
        session = Session.create(self.deck.id, self.deck.questions, shuffle_options=True, rng=rng)
        for item in session.items:
            self.assertTrue(item.options[item.correct_pos].startswith("right"))
        self.assertTrue(any(item.correct_pos != 0 for item in session.items))

    def test_scoring_and_mistakes(self):
        session = Session.create(self.deck.id, self.deck.questions[:3], shuffle_options=False)
        self.assertTrue(session.answer(0))
        session.next()
        self.assertFalse(session.answer(2))
        session.next()
        session.next()  # skipped
        self.assertTrue(session.finished)
        self.assertEqual(session.score, 1)
        self.assertEqual(len(session.mistakes), 1)
        self.assertEqual(len(session.answered), 2)

    def test_range_count_and_mistakes_mode(self):
        picked = select_questions(self.deck, {}, mode="ordered", start=5, end=9)
        self.assertEqual([q.id for q in picked], ["5", "6", "7", "8", "9"])
        self.assertEqual(len(select_questions(self.deck, {}, mode="random", count=7)), 7)

        self.store.record(self.deck.id, "3", False)
        self.store.record(self.deck.id, "4", True)
        stats = self.store.stats(self.deck.id)
        self.assertEqual([q.id for q in select_questions(self.deck, stats, mode="mistakes")], ["3"])
        self.assertEqual(len(select_questions(self.deck, stats, mode="unseen")), 18)

    def test_progress_persists(self):
        self.store.record(self.deck.id, "1", True)
        self.store.save_progress()
        again = Store(self.tmp.name)
        self.assertEqual(again.summary(again.load_deck(self.deck.id))["seen"], 1)


class GeneratorTests(unittest.TestCase):
    def test_offline_generator_makes_valid_questions(self):
        text = """Гліколіз — це процес розщеплення глюкози до пірувату в цитоплазмі клітини.
Глюконеогенез — це синтез глюкози з невуглеводних попередників у печінці.
Ліполіз — це гідроліз триацилгліцеролів до гліцеролу та жирних кислот.
Трансамінування — це перенесення аміногрупи з амінокислоти на кетокислоту.
Декарбоксилювання — це відщеплення карбоксильної групи у вигляді вуглекислого газу.
Фенілкетонурія спричинена дефіцитом фенілаланінгідроксилази в гепатоцитах.
Хвороба Гірке пов'язана з дефіцитом глюкозо-6-фосфатази у печінці та нирках.
Алкаптонурія виникає через недостатність оксидази гомогентизинової кислоти.""".splitlines()
        qs = generate_questions(text, seed=1)
        self.assertGreaterEqual(len(qs), 5)
        for q in qs:
            self.assertGreaterEqual(len(q.options), 4)
            self.assertEqual(len(set(o.lower() for o in q.options)), len(q.options))


if __name__ == "__main__":
    unittest.main()
