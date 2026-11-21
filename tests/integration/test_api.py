"""Integration tests for the web API: real HTTP requests (in-process) on real JSON files.

Skipped when the API's packages aren't installed: pip install -r requirements-api.txt httpx
"""

import json
import tempfile
import typing
import unittest

from flash.core.quiz import MODES
from flash.service import FlashService
from flash.storage import JsonStore
from tests.helpers import BANK, HAS_API, NOTES, write_pdf


@unittest.skipUnless(HAS_API, "web API dependencies not installed (requirements-api.txt)")
class ApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from flash.api.app import create_app
        from flash.api.config import ApiConfig

        self.tmp = tempfile.TemporaryDirectory()
        self.config = ApiConfig(max_upload_mb=1, log_level="ERROR")
        self.client = TestClient(create_app(FlashService(JsonStore(self.tmp.name)), self.config))

    def tearDown(self):
        self.tmp.cleanup()

    def upload(self, name, content, **params):
        data = content.encode("utf-8") if isinstance(content, str) else content
        return self.client.post("/decks", files={"file": (name, data)}, params=params)

    def answer(self, state, position):
        return self.client.post(f"/tests/{state['test_id']}/answer", json={"position": position})

    def test_health(self):
        body = self.client.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("version", body)

    def test_upload_a_test_bank_and_take_a_test(self):
        r = self.upload("krok.txt", BANK)
        self.assertEqual(r.status_code, 201, r.text)
        deck = r.json()
        self.assertEqual((deck["name"], deck["kind"], deck["questions"]), ("krok", "bank", 3))
        self.assertEqual([d["id"] for d in self.client.get("/decks").json()], [deck["id"]])

        detail = self.client.get(f"/decks/{deck['id']}").json()
        right = {q["text"]: q["options"][q["answer"]] for q in detail["items"]}

        r = self.client.post(f"/decks/{deck['id']}/tests", json={"mode": "ordered"})
        self.assertEqual(r.status_code, 201, r.text)
        state = r.json()
        self.assertEqual(state["total"], 3)
        self.assertEqual(self.client.get(f"/tests/{state['test_id']}").json(), state)

        for i in range(3):
            q = state["question"]
            pos = q["options"].index(right[q["text"]]) if i < 2 else (q["options"].index(right[q["text"]]) + 1) % 4
            result = self.answer(state, pos).json()
            self.assertEqual(result["correct"], i < 2)
            self.assertEqual(q["options"][result["correct_position"]], right[q["text"]])
            state = result["state"]

        self.assertTrue(state["finished"])
        self.assertIsNone(state["question"])
        self.assertEqual((state["score"], state["answered"]), (2, 3))
        self.assertEqual(self.client.get("/decks").json()[0]["progress"]["seen"], 3)
        self.assertEqual(self.answer(state, 0).status_code, 409)

    def test_a_real_pdf(self):
        with tempfile.TemporaryDirectory() as folder, open(write_pdf(folder, "krok.pdf", BANK), "rb") as f:
            r = self.upload("Krok 2024.pdf", f.read())
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()["name"], r.json()["questions"]), ("Krok 2024", 3))

    def test_notes_are_turned_into_questions_offline(self):
        r = self.upload("biology.md", NOTES)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["kind"], "generated")
        self.assertGreater(r.json()["questions"], 0)
        r = self.upload("biology.md", NOTES, generate="none")
        self.assertEqual(r.status_code, 422)
        self.assertTrue(r.json()["detail"].startswith("Not a test bank"))

    def test_start_test_without_a_body_asks_everything(self):
        deck = self.upload("krok.txt", BANK).json()
        state = self.client.post(f"/decks/{deck['id']}/tests").json()
        self.assertEqual(state["total"], 3)

    def test_upload_errors(self):
        cases = [
            ("slides.pptx", "x", 415, "Unsupported file type"),
            ("broken.pdf", "not a pdf", 422, "Could not read the file"),
            ("empty.txt", "", 422, "No text found"),
            ("big.txt", "a" * (1024 * 1024 + 1), 413, "File is too large"),
        ]
        for name, content, status, message in cases:
            with self.subTest(name=name):
                r = self.upload(name, content)
                self.assertEqual(r.status_code, status, r.text)
                self.assertTrue(r.json()["detail"].startswith(message), r.json())
        self.assertEqual(self.client.get("/decks").json(), [])

    def test_other_errors(self):
        self.assertEqual(self.client.get("/decks/nope").status_code, 404)
        self.assertEqual(self.client.delete("/decks/nope").status_code, 404)
        self.assertEqual(self.client.post("/decks/nope/tests").status_code, 404)
        self.assertEqual(self.client.get("/tests/nope").status_code, 404)

        deck = self.upload("krok.txt", BANK).json()
        self.assertEqual(self.client.post(f"/decks/{deck['id']}/tests", json={"mode": "mistakes"}).status_code, 422)
        self.assertEqual(self.client.post(f"/decks/{deck['id']}/tests", json={"mode": "fast"}).status_code, 422)
        self.assertEqual(self.client.post(f"/decks/{deck['id']}/tests", json={"count": 0}).status_code, 422)

        state = self.client.post(f"/decks/{deck['id']}/tests").json()
        self.assertEqual(self.answer(state, 9).status_code, 422)
        self.assertEqual(self.answer(state, -1).status_code, 422)

    def test_deleting_a_deck_closes_its_tests(self):
        deck = self.upload("krok.txt", BANK).json()
        state = self.client.post(f"/decks/{deck['id']}/tests").json()
        self.assertEqual(self.client.delete(f"/decks/{deck['id']}").status_code, 204)
        self.assertEqual(self.client.get("/decks").json(), [])
        self.assertEqual(self.answer(state, 0).status_code, 404)

    def test_test_modes_match_the_quiz_rules(self):
        from flash.api.schemas import TestRequest

        self.assertEqual(typing.get_args(TestRequest.model_fields["mode"].annotation), MODES)

    def test_docs_pages_are_served(self):
        self.assertIn("swagger-ui", self.client.get("/docs").text)
        self.assertIn("redoc", self.client.get("/redoc").text)
        self.assertEqual(self.client.get("/openapi.json").json()["info"]["title"], "FlasH API")


@unittest.skipUnless(HAS_API, "web API dependencies not installed (requirements-api.txt)")
class OpenApiDocumentTests(unittest.TestCase):
    def test_docs_openapi_json_is_up_to_date(self):
        from flash.api import openapi

        with open(openapi.DEFAULT_PATH, encoding="utf-8") as f:
            saved = f.read()
        self.assertEqual(
            saved,
            openapi.render(openapi.build_schema()),
            "docs/openapi.json is out of date: run  python -m flash.api.openapi",
        )

    def test_every_operation_is_documented(self):
        from flash.api import openapi

        schema = json.loads(openapi.render(openapi.build_schema()))
        for path, methods in schema["paths"].items():
            for method, op in methods.items():
                with self.subTest(operation=f"{method.upper()} {path}"):
                    self.assertTrue(op.get("summary"))
                    self.assertTrue(op.get("description"))
                    self.assertTrue(op.get("tags"))
                    self.assertNotIn("_", op["operationId"].strip("_").replace("_", ""), "operationId is readable")
        for name, model in schema["components"]["schemas"].items():
            if name.startswith(("Body_", "HTTPValidationError", "ValidationError")):
                continue  # made by FastAPI itself
            with self.subTest(model=name):
                self.assertTrue(model.get("description"), f"{name} has no description")
                for field, spec in model.get("properties", {}).items():
                    if "$ref" not in spec:
                        self.assertTrue(spec.get("description"), f"{name}.{field} has no description")


if __name__ == "__main__":
    unittest.main()
