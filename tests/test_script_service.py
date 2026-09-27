from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video_workbench.project import create_project
from video_workbench.scripts import (
    ScriptError,
    ScriptService,
    ScriptValidationError,
    scripts_directory,
)


class ScriptServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.project = create_project(self.root / "project")
        self.service = ScriptService()

    def test_create_list_and_read_utf8_documents(self) -> None:
        content = "[00:23] 切换画面\n# 标题\n中文台词"
        first = self.service.create_document(
            self.project.root,
            "口播稿.txt",
            content,
        )
        second = self.service.create_document(
            self.project.root,
            "notes.md",
            "# Notes",
        )

        self.assertEqual(first.content, content)
        self.assertEqual(first.path.read_text(encoding="utf-8"), content)
        self.assertEqual(
            self.service.list_documents(self.project.root),
            [second.path, first.path],
        )
        self.assertEqual(
            self.service.read_document(first.path).content,
            content,
        )

    def test_new_document_adds_txt_and_unique_suffix(self) -> None:
        first = self.service.create_document(self.project.root, "未命名")
        second = self.service.create_document(self.project.root, "未命名")

        self.assertEqual(first.path.name, "未命名.txt")
        self.assertEqual(second.path.name, "未命名_1.txt")

    def test_invalid_names_and_extensions_are_rejected(self) -> None:
        invalid_names = ("../逃逸.txt", "脚本.rtf", "bad?.md", "")
        for filename in invalid_names:
            with self.subTest(filename=filename):
                with self.assertRaises(ScriptValidationError):
                    self.service.create_document(self.project.root, filename)

    def test_save_and_save_as_keep_original_file_untouched(self) -> None:
        original = self.service.create_document(
            self.project.root,
            "原稿.txt",
            "原内容",
        )
        saved = self.service.save_document(
            original,
            "保存内容",
            self.project.root,
        )
        copy = self.service.save_as_document(
            self.project.root,
            scripts_directory(self.project.root) / "副本.md",
            "副本内容",
        )

        self.assertEqual(saved.content, "保存内容")
        self.assertEqual(original.path.read_text(encoding="utf-8"), "保存内容")
        self.assertEqual(copy.content, "副本内容")
        self.assertEqual(copy.path.read_text(encoding="utf-8"), "副本内容")

    def test_save_as_rejects_path_outside_project_scripts_directory(self) -> None:
        with self.assertRaises(ScriptValidationError):
            self.service.save_as_document(
                self.project.root,
                self.root / "outside.txt",
                "内容",
            )

    def test_export_uses_scripts_directory_and_avoids_overwrite(self) -> None:
        source = self.service.create_document(
            self.project.root,
            "口播.txt",
            "正文",
        )
        first_export = self.service.export_document(
            self.project.root,
            source,
            "正文",
            "md",
        )
        second_export = self.service.export_document(
            self.project.root,
            source,
            "更新正文",
            ".md",
        )

        self.assertEqual(first_export.path.name, "口播.md")
        self.assertEqual(second_export.path.name, "口播_1.md")
        self.assertEqual(first_export.path.parent, scripts_directory(self.project.root))
        self.assertEqual(first_export.path.read_text(encoding="utf-8"), "正文")
        self.assertEqual(second_export.path.read_text(encoding="utf-8"), "更新正文")

    def test_invalid_utf8_read_has_clear_error(self) -> None:
        path = scripts_directory(self.project.root) / "bad.txt"
        path.write_bytes(b"\xff\xfe")

        with self.assertRaises(ScriptValidationError):
            self.service.read_document(path)

    def test_atomic_replace_failure_preserves_original_and_cleans_temp(self) -> None:
        document = self.service.create_document(
            self.project.root,
            "锁定.txt",
            "原内容",
        )

        with patch(
            "video_workbench.scripts.service.os.replace",
            side_effect=OSError("locked"),
        ):
            with self.assertRaises(ScriptError):
                self.service.save_document(
                    document,
                    "新内容",
                    self.project.root,
                )

        self.assertEqual(document.path.read_text(encoding="utf-8"), "原内容")
        temporary_files = list(document.path.parent.glob(".锁定.txt.*.tmp"))
        self.assertEqual(temporary_files, [])


if __name__ == "__main__":
    unittest.main()
