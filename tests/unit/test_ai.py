"""Unit tests for AI question generation (flash.core.ai), with a fake Anthropic client.

No request ever leaves the computer: ``anthropic.Anthropic`` is replaced by ``FakeAnthropic``.
"""

import unittest
from unittest import mock

from flash.core import ai
from tests.fakes import FakeAnthropic, FakeAPIError, ai_question, ai_response

LECTURE = ["Текст лекції про синтез білка. " * 10]


@unittest.skipUnless(ai.is_available(), "anthropic not installed")
class GenerateQuestionsTests(unittest.TestCase):
    def generate(self, responses, lines=LECTURE, **kwargs):
        client = FakeAnthropic(responses)
        with mock.patch("anthropic.Anthropic", client):
            questions = ai.generate_questions(lines, api_key="sk-test", **kwargs)
        return questions, client

    def test_parses_structured_output_and_moves_the_answer_first(self):
        good = ai_question("Що синтезується?", ["A", "B", "C", "D", "E"], 2, "Бо C.")
        too_few_options = ai_question("Bad", ["only one"], 0)
        questions, client = self.generate([ai_response([good, too_few_options])])

        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertEqual((q.text, q.options[0], q.answer, q.explanation), ("Що синтезується?", "C", 0, "Бо C."))
        self.assertEqual(sorted(q.options), ["A", "B", "C", "D", "E"])

        request = client.calls[0]
        self.assertEqual(client.api_key, "sk-test")
        self.assertEqual(request["model"], ai.DEFAULT_MODEL)
        self.assertEqual(request["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(request["fallbacks"], "default")
        self.assertIn("українською", request["system"])

    def test_english_text_gets_an_english_prompt(self):
        _, client = self.generate([ai_response([])], lines=["An English lecture about proteins. " * 10])
        self.assertIn("in English", client.calls[0]["system"])

    def test_a_model_without_fallbacks_uses_the_plain_endpoint(self):
        _, client = self.generate([ai_response([])], model="claude-haiku-5-5")
        self.assertNotIn("fallbacks", client.calls[0])

    def test_bad_items_are_skipped(self):
        items = [
            ai_question("Index out of range", ["a", "b", "c"], 5),
            ai_question("Blank options", ["a", " ", ""], 0),
            ai_question("Fine", ["a", "b", "c"], 1),
        ]
        questions, _ = self.generate([ai_response(items)])
        self.assertEqual([q.text for q in questions], ["Fine"])

    def test_refusals_and_broken_json_are_skipped(self):
        lines = ["x" * 7000, "", "y" * 7000, "", "z" * 7000]  # three paragraphs, one request each
        responses = [
            ai_response(stop_reason="refusal"),
            ai_response(text="{not json"),
            ai_response([ai_question("Kept", ["a", "b", "c"], 0)]),
        ]
        progress = mock.Mock()
        questions, client = self.generate(responses, lines=lines, progress=progress)
        self.assertEqual([q.text for q in questions], ["Kept"])
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(progress.call_args_list, [mock.call(1, 3), mock.call(2, 3), mock.call(3, 3)])

    def test_cancelling_stops_before_the_next_request(self):
        questions, client = self.generate([], cancelled=lambda: True)
        self.assertEqual((questions, client.calls), ([], []))

    def test_api_errors_become_short_codes(self):
        class Auth(FakeAPIError): ...

        class RateLimit(FakeAPIError): ...

        class Connection(FakeAPIError): ...

        class Status(FakeAPIError): ...

        errors = mock.patch.multiple(
            "anthropic",
            AuthenticationError=Auth,
            RateLimitError=RateLimit,
            APIConnectionError=Connection,
            APIStatusError=Status,
        )
        cases = [
            (Auth(), "auth"),
            (RateLimit(), "rate_limit"),
            (Connection(), "network"),
            (Status("overloaded", 529), "API error 529: overloaded"),
        ]
        with errors:
            for error, code in cases:
                with self.subTest(code=code), self.assertRaises(ai.AIError) as caught:
                    self.generate([error])
                self.assertEqual(str(caught.exception), code)


class WithoutAnthropicTests(unittest.TestCase):
    def test_missing_package_is_reported(self):
        with mock.patch.dict("sys.modules", {"anthropic": None}):
            self.assertFalse(ai.is_available())
            with self.assertRaises(ai.AIError):
                ai.generate_questions(LECTURE, api_key="k")


class ChunkTextTests(unittest.TestCase):
    def test_chunking_keeps_all_text(self):
        text = "\n".join(f"Абзац {i} " + "x" * 500 for i in range(100))
        chunks = ai.chunk_text(text, size=5000)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(c) <= 5000 for c in chunks))
        self.assertEqual("\n".join(chunks), text)

    def test_a_paragraph_longer_than_the_limit_stays_whole(self):
        self.assertEqual(ai.chunk_text("x" * 100, size=10), ["x" * 100])


if __name__ == "__main__":
    unittest.main()
