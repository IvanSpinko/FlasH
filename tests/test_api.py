import importlib.util
import tempfile
import typing
import unittest

from flash.core.quiz import MODES
from flash.service import FlashService
from flash.storage import JsonStore

HAS_API = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "multipart"))

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

NOTES = "\n\n".join(
    f"{term} is a {desc} that is studied in the introductory biology course every year."
    for term, desc in [
        ("Mitochondrion", "membrane organelle producing most of the energy of the cell"),
        ("Ribosome", "molecular machine building proteins from amino acids"),
        ("Lysosome", "small vesicle containing digestive enzymes for waste"),
        ("Chloroplast", "plant organelle where photosynthesis takes place"),
        ("Nucleus", "membrane organelle storing the genetic material"),
    ]
)


@unittest.skipUnless(HAS_API, "web API dependencies not installed (requirements-api.txt)")
class ApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from flash.api.app import create_app

        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(FlashService(JsonStore(self.tmp.name))))

    def tearDown(self):
        self.tmp.cleanup()

    def upload(self, name, text, **params):
        return self.client.post("/decks", files={"file": (name, text.encode("utf-8"))}, params=params)

    def test_health(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")

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

        for i in range(3):
            q = state["question"]
            pos = q["options"].index(right[q["text"]]) if i < 2 else (q["options"].index(right[q["text"]]) + 1) % 4
            result = self.client.post(f"/tests/{state['test_id']}/answer", json={"position": pos}).json()
            self.assertEqual(result["correct"], i < 2)
            state = result["state"]

        self.assertTrue(state["finished"])
        self.assertEqual((state["score"], state["answered"]), (2, 3))
        self.assertEqual(self.client.get("/decks").json()[0]["progress"]["seen"], 3)
        r = self.client.post(f"/tests/{state['test_id']}/answer", json={"position": 0})
        self.assertEqual(r.status_code, 409)

    def test_notes_are_turned_into_questions_offline(self):
        r = self.upload("biology.md", NOTES)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["kind"], "generated")
        self.assertGreater(r.json()["questions"], 0)
        self.assertEqual(self.upload("biology.md", NOTES, generate="none").status_code, 422)

    def test_errors(self):
        self.assertEqual(self.upload("slides.pptx", "x").status_code, 415)
        self.assertEqual(self.client.get("/decks/nope").status_code, 404)
        self.assertEqual(self.client.get("/tests/nope").status_code, 404)
        deck = self.upload("krok.txt", BANK).json()
        state = self.client.post(f"/decks/{deck['id']}/tests").json()
        r = self.client.post(f"/tests/{state['test_id']}/answer", json={"position": 9})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.client.delete(f"/decks/{deck['id']}").status_code, 204)
        self.assertEqual(self.client.get("/decks").json(), [])

    def test_test_modes_match_the_quiz_rules(self):
        from flash.api.app import TestRequest

        self.assertEqual(typing.get_args(TestRequest.model_fields["mode"].annotation), MODES)


if __name__ == "__main__":
    unittest.main()
