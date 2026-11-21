"""Unit tests for the web API's own parts: settings from the environment and open-test storage.

They don't need FastAPI, so they run everywhere.
"""

import unittest

from flash.api.config import ApiConfig
from flash.api.sessions import TestSessions
from flash.core.quiz import Session
from tests.fakes import FakeClock
from tests.helpers import make_questions


class ApiConfigTests(unittest.TestCase):
    def test_defaults_without_any_variables(self):
        self.assertEqual(ApiConfig.from_env({}), ApiConfig())

    def test_empty_values_mean_the_default(self):
        env = {"FLASH_MAX_UPLOAD_MB": "", "FLASH_MAX_OPEN_TESTS": " ", "FLASH_LOG_LEVEL": ""}
        self.assertEqual(ApiConfig.from_env(env), ApiConfig())

    def test_values_are_read(self):
        env = {
            "FLASH_MAX_UPLOAD_MB": "2.5",
            "FLASH_MAX_OPEN_TESTS": "10",
            "FLASH_TEST_IDLE_HOURS": "0.5",
            "FLASH_LOG_LEVEL": "debug",
        }
        config = ApiConfig.from_env(env)
        self.assertEqual(
            config, ApiConfig(max_upload_mb=2.5, max_open_tests=10, test_idle_hours=0.5, log_level="DEBUG")
        )
        self.assertEqual(config.max_upload_bytes, int(2.5 * 1024 * 1024))

    def test_bad_values_name_the_variable(self):
        for env in (
            {"FLASH_MAX_UPLOAD_MB": "fifty"},
            {"FLASH_MAX_UPLOAD_MB": "0"},
            {"FLASH_MAX_OPEN_TESTS": "1.5"},
            {"FLASH_TEST_IDLE_HOURS": "-1"},
            {"FLASH_LOG_LEVEL": "LOUD"},
        ):
            with self.subTest(env=env), self.assertRaises(ValueError) as caught:
                ApiConfig.from_env(env)
            self.assertIn(next(iter(env)), str(caught.exception))


def session(deck_id: str = "deck") -> Session:
    return Session.create(deck_id, make_questions(2))


class TestSessionsTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.tests = TestSessions(max_open=3, idle_seconds=60, clock=self.clock)

    def test_add_and_get(self):
        s = session()
        test_id = self.tests.add(s)
        self.assertIs(self.tests.get(test_id), s)
        self.assertIsNone(self.tests.get("unknown"))
        self.assertEqual(len(self.tests), 1)

    def test_ids_are_unique_and_hard_to_guess(self):
        ids = {self.tests.add(session()) for _ in range(3)}
        self.assertEqual(len(ids), 3)
        self.assertTrue(all(len(i) == 32 for i in ids))

    def test_idle_tests_expire(self):
        test_id = self.tests.add(session())
        self.clock.advance(59)
        self.assertIsNotNone(self.tests.get(test_id))  # using it resets the timer
        self.clock.advance(59)
        self.assertIsNotNone(self.tests.get(test_id))
        self.clock.advance(61)
        self.assertIsNone(self.tests.get(test_id))
        self.assertEqual(len(self.tests), 0)

    def test_the_least_recently_used_test_goes_first_when_full(self):
        first, second, third = (self.tests.add(session()) for _ in range(3))
        self.tests.get(first)  # first is now the most recently used
        fourth = self.tests.add(session())
        self.assertIsNone(self.tests.get(second))
        for kept in (first, third, fourth):
            self.assertIsNotNone(self.tests.get(kept))
        self.assertEqual(len(self.tests), 3)

    def test_drop_deck(self):
        kept = self.tests.add(session("keep"))
        self.tests.add(session("gone"))
        self.tests.add(session("gone"))
        self.assertEqual(self.tests.drop_deck("gone"), 2)
        self.assertEqual(len(self.tests), 1)
        self.assertIsNotNone(self.tests.get(kept))

    def test_max_open_must_be_positive(self):
        with self.assertRaises(ValueError):
            TestSessions(max_open=0)


if __name__ == "__main__":
    unittest.main()
