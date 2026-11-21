import unittest

from flash.core.parser import parse_question_bank, looks_like_question_bank

KROK_COLUMNS = """
1. Під час тривалого голодування
зростає секреція глюкокортикоїдів.
Що є термінальним ферментом цього
процесу?
Глюкозо-6-фосфатаза
Глюкозо-1-фосфатаза
Фруктозо-2,6-дифосфатаза
Фруктозо-6-фосфатаза
Фруктозо-1,6-дифосфатаза

2. Конкурентним інгібітором якого
ферменту є алопуринол?
Ксантиноксидази
Гуаніндезамінази
Гіпоксантинфосфорибозилтрансфера
зи
Аденінфосфорибозилтрансферази
Аденозиндезамінази

3. Який механізм є провідним у
розвитку такої анемії?
Відсутність внутрішнього фактора
Касла
Дефіцит транскобаламіну
Відсутність зовнішнього фактора
Касла
Порушення всмоктування вітаміну
В12 в тонкій кишці
Дефіцит фолієвої кислоти

4. Який із медіаторів запалення має
властивості пірогену?
Інтерлейкін 1
Брадикінін
Гістамін

Тромбоксан А2
Серотонін
5. У пацієнта діагностовано
гемофілію А. Дефіцит якого фактора
є причиною цієї патології?
VIII
V, X
XII
IX
I, II
"""

UNNUMBERED = """
У хворого, що страждав хронічним гломерулонефритом, на тлі хронічної ниркової
недостатності з'явився кашель з відходженням слизистої мокроти. При бронхоскопії:
слизова оболонка бронхів повнокровна, набрякла, з дрібними крововиливами. У просвіті
бронхів багато слизу. Встановіть процес в бронхах.
Вторинний гострий катаральний бронхіт
Первинний гострий бронхіт катаральний
Хронічний катаральний бронхіт
Деструктивно-виразковий бронхіт
Катарально-гнійний бронхіт

Первинний туберкульозний афект, що загоївся, зветься:
осередок Гона
осередок Симона
осередок Абрикосова
осередок Ашофа-Пуля
осередок Асмана-Редекера
"""

ENGLISH_MARKED = """
1) Which organelle produces most of the cell's ATP?
A. Ribosome
B. Mitochondrion *
C. Golgi apparatus
D. Lysosome

2) What is the normal pH of arterial blood?
A. 7.35-7.45 *
B. 6.8-7.0
C. 7.6-7.8
D. 5.5-6.5
"""


def lines(text):
    return [l.strip() for l in text.strip("\n").splitlines()]


class ParserTests(unittest.TestCase):
    def test_wrapped_options_and_page_fragments(self):
        qs = parse_question_bank(lines(KROK_COLUMNS))
        self.assertEqual(len(qs), 5)
        for q in qs:
            self.assertEqual(len(q.options), 5, q.options)
            self.assertEqual(q.answer, 0)
        self.assertTrue(qs[0].text.startswith("Під час"))
        self.assertEqual(qs[0].options[0], "Глюкозо-6-фосфатаза")
        self.assertIn("Гіпоксантинфосфорибозилтрансферази", qs[1].options)
        self.assertEqual(qs[2].options[0], "Відсутність внутрішнього фактора Касла")
        self.assertIn("Порушення всмоктування вітаміну В12 в тонкій кишці", qs[2].options)
        self.assertEqual(qs[3].options[-2:], ["Тромбоксан А2", "Серотонін"])
        self.assertEqual(qs[4].options[0], "VIII")

    def test_unnumbered_with_colon_inside_stem(self):
        qs = parse_question_bank(lines(UNNUMBERED))
        self.assertEqual(len(qs), 2)
        self.assertTrue(qs[0].text.endswith("Встановіть процес в бронхах."))
        self.assertEqual(qs[0].options[0], "Вторинний гострий катаральний бронхіт")
        self.assertEqual(qs[1].options[0], "осередок Гона")

    def test_marked_answers_and_letters(self):
        qs = parse_question_bank(lines(ENGLISH_MARKED))
        self.assertEqual(len(qs), 2)
        self.assertEqual(qs[0].options[qs[0].answer], "Mitochondrion")
        self.assertNotIn("A. Ribosome", qs[0].options)
        self.assertEqual(qs[1].options[qs[1].answer], "7.35-7.45")

    def test_plain_text_is_not_a_bank(self):
        text = [
            "Glycolysis is the metabolic pathway that converts glucose into pyruvate.",
            "It occurs in the cytosol of cells in all living organisms.",
            "",
            "The citric acid cycle is a series of chemical reactions.",
        ] * 10
        qs = parse_question_bank(text)
        self.assertFalse(looks_like_question_bank(text, qs))


if __name__ == "__main__":
    unittest.main()
