import json
import unittest
from types import SimpleNamespace
from unittest import mock

from flash import ai


class FakeMessages:
    def __init__(self, calls):
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = {
            "questions": [
                {
                    "question": "Що синтезується?",
                    "options": ["A", "B", "C", "D", "E"],
                    "correct_index": 2,
                    "explanation": "Бо C.",
                },
                {"question": "Bad", "options": ["only one"], "correct_index": 0, "explanation": ""},
            ]
        }
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(payload))])


@unittest.skipUnless(ai.is_available(), "anthropic not installed")
class AITests(unittest.TestCase):
    def test_parses_structured_output_and_moves_answer_first(self):
        calls = []
        fake = SimpleNamespace(messages=FakeMessages(calls), beta=SimpleNamespace(messages=FakeMessages(calls)))
        with mock.patch("anthropic.Anthropic", return_value=fake):
            qs = ai.generate_questions(["Текст лекції про синтез білка." * 5], api_key="k")
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].options[0], "C")
        self.assertEqual(qs[0].answer, 0)
        req = calls[0]
        self.assertEqual(req["model"], ai.DEFAULT_MODEL)
        self.assertEqual(req["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(req["fallbacks"], "default")

    def test_chunking_keeps_all_text(self):
        text = "\n".join(f"Абзац {i} " + "x" * 500 for i in range(100))
        chunks = ai.chunk_text(text, size=5000)
        self.assertGreater(len(chunks), 5)
        self.assertEqual("\n".join(chunks), text)


if __name__ == "__main__":
    unittest.main()
