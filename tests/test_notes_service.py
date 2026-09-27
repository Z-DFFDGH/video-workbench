from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video_workbench.notes import (
    NotesService,
    NotesValidationError,
    notes_path,
)
from video_workbench.project import create_project


class NotesServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.project = create_project(self.root / "project")
        self.service = NotesService()

    def test_load_creates_notes_markdown_and_reads_utf8(self) -> None:
        path = notes_path(self.project.root)
        self.assertFalse(path.exists())

        content = "# 选题\n\n发布平台：B站\n创作备注"
        self.assertEqual(self.service.load_or_create(self.project.root), "")
        self.assertTrue(path.is_file())

        self.service.save(self.project.root, content)

        self.assertEqual(self.service.read(self.project.root), content)
        self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_missing_project_directory_is_rejected(self) -> None:
        missing = self.root / "missing"

        with self.assertRaises(NotesValidationError):
            self.service.load_or_create(missing)

    def test_atomic_failure_preserves_existing_notes_and_cleans_temp(self) -> None:
        self.service.save(self.project.root, "原笔记")
        path = notes_path(self.project.root)

        with patch(
            "video_workbench.notes.service.os.replace",
            side_effect=OSError("locked"),
        ):
            with self.assertRaises(NotesValidationError):
                self.service.save(self.project.root, "新笔记")

        self.assertEqual(path.read_text(encoding="utf-8"), "原笔记")
        self.assertEqual(list(path.parent.glob(".notes.md.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
