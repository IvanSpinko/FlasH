"""Integration tests for importing real files: extract -> parser/generator -> service -> JsonStore."""

import os
import tempfile
import unittest

from flash.core.extract import ExtractionError, extract_lines
from flash.service import FlashService
from flash.storage import JsonStore
from tests.helpers import BANK, BANK_ANSWERS, NOTES, write_pdf, write_text


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = self.tmp.name
        self.service = FlashService(JsonStore(os.path.join(self.folder, "data")))

    def tearDown(self):
        self.tmp.cleanup()

    def assert_bank(self, path):
        result = self.service.analyse_file(path)
        self.assertTrue(result.is_bank, result.lines)
        self.assertEqual([q.options[q.answer] for q in result.questions], BANK_ANSWERS)
        return result

    def test_text_file_bank(self):
        self.assert_bank(write_text(self.folder, "krok.txt", BANK))

    def test_markdown_bank(self):
        self.assert_bank(write_text(self.folder, "krok.md", BANK))

    def test_windows_cyrillic_encoding(self):
        bank = BANK.replace("Which organ pumps blood?", "Який орган качає кров?")
        result = self.assert_bank(write_text(self.folder, "krok.txt", bank, encoding="cp1251"))
        self.assertEqual(result.questions[0].text, "Який орган качає кров?")

    def test_pdf_bank_with_progress(self):
        path = write_pdf(self.folder, "krok.pdf", BANK, lines_per_page=8)
        pages = []
        result = self.service.analyse_file(path, progress=lambda done, total: pages.append((done, total)))
        self.assertTrue(result.is_bank)
        self.assertEqual([q.options[q.answer] for q in result.questions], BANK_ANSWERS)
        self.assertEqual(pages[-1][0], pages[-1][1])
        self.assertGreater(len(pages), 1)

    def test_pdf_page_numbers_are_dropped(self):
        path = write_pdf(self.folder, "numbers.pdf", "A line of real text.\n\n17")
        self.assertNotIn("17", extract_lines(path))

    def test_notes_become_a_generated_deck(self):
        result = self.service.analyse_file(write_pdf(self.folder, "biology.pdf", NOTES))
        self.assertFalse(result.is_bank)
        self.assertTrue(result.has_text)
        questions = self.service.generate_offline(result)
        self.assertGreater(len(questions), 0)

        deck = self.service.save_deck(result.name, result.source, "generated", questions)
        reopened = FlashService(JsonStore(os.path.join(self.folder, "data")))
        self.assertEqual(reopened.get_deck(deck.id).name, "biology")
        self.assertEqual(reopened.get_deck(deck.id).kind, "generated")

    def test_empty_pdf_has_no_text(self):
        self.assertFalse(self.service.analyse_file(write_pdf(self.folder, "scan.pdf", "")).has_text)

    def test_unreadable_files_raise_extraction_error(self):
        broken = write_text(self.folder, "broken.pdf", "this is not a PDF")
        with self.assertRaises(ExtractionError):
            self.service.analyse_file(broken)
        with self.assertRaises(ExtractionError):
            extract_lines(write_text(self.folder, "slides.pptx", "x"))


if __name__ == "__main__":
    unittest.main()
