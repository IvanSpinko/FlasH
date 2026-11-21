"""Unit tests for the desktop app's translations (flash.desktop.i18n).

Importing it needs no window, so these run without a display.
"""

import re
import unittest

from flash.desktop import i18n


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("uk")

    def test_every_language_has_the_same_keys(self):
        keys = {lang: set(strings) for lang, strings in i18n.STRINGS.items()}
        self.assertEqual(set(keys), set(i18n.LANGUAGES))
        for lang, have in keys.items():
            with self.subTest(lang=lang):
                self.assertEqual(have, keys["uk"])

    def test_placeholders_match_between_languages(self):
        names = re.compile(r"\{(\w+)")
        for key, text in i18n.STRINGS["uk"].items():
            with self.subTest(key=key):
                self.assertEqual(set(names.findall(text)), set(names.findall(i18n.STRINGS["en"][key])))

    def test_switching_language(self):
        i18n.set_language("en")
        self.assertEqual(i18n.get_language(), "en")
        self.assertEqual(i18n.t("delete"), "Delete")
        i18n.set_language("uk")
        self.assertEqual(i18n.t("delete"), "Видалити")

    def test_unknown_key_shows_the_key(self):
        self.assertEqual(i18n.t("no_such_key"), "no_such_key")


if __name__ == "__main__":
    unittest.main()
