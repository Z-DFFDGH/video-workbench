from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from video_workbench.sensitive_words import (
    SensitiveWordsFileNotFoundError,
    SensitiveWordsService,
    SensitiveWordsValidationError,
    default_sensitive_words_path,
)


class SensitiveWordsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.words_path = self.root / "sensitive_words.txt"
        self.service = SensitiveWordsService()

    def write_words(self, content: str) -> None:
        self.words_path.write_text(content, encoding="utf-8")

    def test_load_ignores_blank_lines_and_duplicate_words(self) -> None:
        self.write_words("\n风险\n\nbadword\nBadWord\n中文词\n")

        library = self.service.load_library(self.words_path)

        self.assertEqual(library.words, ("风险", "badword", "中文词"))

    def test_literal_matching_supports_chinese_and_ascii_case_insensitive(self) -> None:
        self.write_words("风险\nbadword\n")
        result = self.service.check(
            "BADWORD 有风险\nbadword 还需要检查风险",
            self.words_path,
        )

        self.assertEqual(result.word_count, 2)
        self.assertEqual(result.match_count, 4)
        self.assertEqual(
            [(match.word, match.matched_text) for match in result.matches],
            [
                ("badword", "BADWORD"),
                ("风险", "风险"),
                ("badword", "badword"),
                ("风险", "风险"),
            ],
        )

    def test_multiple_positions_include_line_and_column(self) -> None:
        self.write_words("风险\n")
        text = "风险出现在第一行\n第二行也有风险"

        result = self.service.check(text, self.words_path)

        self.assertEqual(
            [
                (match.start, match.line, match.column)
                for match in result.matches
            ],
            [(0, 1, 1), (14, 2, 6)],
        )

    def test_matching_is_literal_not_regular_expression(self) -> None:
        self.write_words("a.b\n")

        result = self.service.check("a.b axb", self.words_path)

        self.assertEqual(result.match_count, 1)
        self.assertEqual(result.matches[0].start, 0)

    def test_missing_word_file_returns_handled_error(self) -> None:
        with self.assertRaises(SensitiveWordsFileNotFoundError):
            self.service.load_library(self.words_path)

    def test_bundled_default_library_is_utf8_and_deduplicated(self) -> None:
        path = default_sensitive_words_path()
        library = self.service.load_library(path)

        self.assertGreaterEqual(len(library.words), 10_000)
        self.assertEqual(
            len({word.lower() for word in library.words}),
            len(library.words),
        )
        self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn("赌博机", library.words)
        result = self.service.check_text("包含赌博机的内容", library)
        self.assertEqual(result.match_count, 1)

    def test_invalid_utf8_word_file_returns_handled_error(self) -> None:
        self.words_path.write_bytes(b"\xff\xfe")

        with self.assertRaises(SensitiveWordsValidationError):
            self.service.load_library(self.words_path)


if __name__ == "__main__":
    unittest.main()
