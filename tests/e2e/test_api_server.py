"""End-to-end test of the web API as a real server: uvicorn in its own process, plain HTTP.

This is how the API runs in Docker, minus Docker: the same command, a real port, a real
data folder. Skipped when the API's packages aren't installed (requirements-api.txt).
"""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid

from tests.helpers import BANK

HAS_SERVER = all(importlib.util.find_spec(m) for m in ("fastapi", "uvicorn", "multipart"))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(HAS_SERVER, "web API dependencies not installed (requirements-api.txt)")
class ApiServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        port = free_port()
        cls.base = f"http://127.0.0.1:{port}"
        env = {**os.environ, "FLASH_DATA_DIR": cls.tmp.name, "FLASH_LOG_LEVEL": "WARNING"}
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "flash.api.app:create_app", "--factory", "--port", str(port)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(cls.base + "/health", timeout=1)
                break
            except OSError:
                if cls.server.poll() is not None or time.monotonic() > deadline:
                    cls.tearDownClass()
                    raise RuntimeError("the API server did not start") from None
                time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.server.kill()
        cls.server.stderr.close()
        cls.tmp.cleanup()

    def call(self, method: str, path: str, body=None, headers=None):
        """One HTTP request; returns (status, parsed JSON or None)."""
        data = json.dumps(body).encode() if isinstance(body, dict) else body
        headers = headers or ({"Content-Type": "application/json"} if isinstance(body, dict) else {})
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as r:
                raw = r.read()
                return r.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def upload(self, name: str, text: str):
        boundary = uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: text/plain\r\n\r\n{text}\r\n--{boundary}--\r\n"
        ).encode("utf-8")
        return self.call("POST", "/decks", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})

    def test_a_student_takes_a_test(self):
        status, deck = self.upload("krok.txt", BANK)
        self.assertEqual(status, 201, deck)

        status, state = self.call("POST", f"/decks/{deck['id']}/tests", {"mode": "ordered", "shuffle_options": False})
        self.assertEqual(status, 201, state)
        while not state["finished"]:
            status, result = self.call("POST", f"/tests/{state['test_id']}/answer", {"position": 0})
            self.assertEqual(status, 200, result)
            self.assertTrue(result["correct"])  # unshuffled: the first option is right
            state = result["state"]
        self.assertEqual(state["score"], 3)

        status, decks = self.call("GET", "/decks")
        self.assertEqual(decks[0]["progress"]["learned"], 0)
        self.assertEqual(decks[0]["progress"]["seen"], 3)
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "progress.json")))

        self.assertEqual(self.call("DELETE", f"/decks/{deck['id']}")[0], 204)
        self.assertEqual(self.call("GET", "/decks"), (200, []))

    def test_errors_are_json(self):
        self.assertEqual(self.call("GET", "/decks/missing"), (404, {"detail": "Deck not found"}))
        status, body = self.call("POST", "/tests/missing/answer", {"position": 0})
        self.assertEqual(status, 404)
        self.assertIn("detail", body)


if __name__ == "__main__":
    unittest.main()
