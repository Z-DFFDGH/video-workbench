from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtTest import QTest

from tests._ui import application

from video_workbench.app import ConfigStore
from video_workbench.notes import notes_path
from video_workbench.project import create_project
from video_workbench.ui.main_window import MainWindow
from video_workbench.ui.pages import NotesPage, SensitiveWordsPage
from video_workbench.ui.shell import AppShell


class NotesSensitiveUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.project = create_project(self.root / "project")

    def test_notes_disable_without_project_and_auto_save_with_project(self) -> None:
        page = NotesPage(auto_save_interval_ms=10)

        self.assertTrue(page.editor.isReadOnly())
        page.set_project(self.project.root)

        self.assertFalse(page.editor.isReadOnly())
        self.assertTrue(notes_path(self.project.root).is_file())
        page.editor.setPlainText("# 选题\n自动保存内容")

        QTest.qWait(40)

        self.assertFalse(page.has_unsaved_changes)
        self.assertEqual(
            notes_path(self.project.root).read_text(encoding="utf-8"),
            "# 选题\n自动保存内容",
        )

    def test_main_window_saves_notes_before_switch_and_close(self) -> None:
        second_project = create_project(self.root / "second")
        window = MainWindow(
            config_store=ConfigStore(self.root / "config.json"),
            animations_enabled=False,
        )
        self.addCleanup(window.close)
        window._open_project_path(str(self.project.project_file))
        page = window.shell.notes_page
        self.assertIsNotNone(page)
        page.editor.setPlainText("切换项目前笔记")

        window._open_project_path(str(second_project.project_file))

        self.assertEqual(
            notes_path(self.project.root).read_text(encoding="utf-8"),
            "切换项目前笔记",
        )
        self.assertEqual(page.project_root, second_project.root.resolve())

        page.editor.setPlainText("关闭程序前笔记")
        window.close()

        self.assertEqual(
            notes_path(second_project.root).read_text(encoding="utf-8"),
            "关闭程序前笔记",
        )

    def test_sensitive_words_highlight_positions_and_reload(self) -> None:
        words_path = self.root / "sensitive_words.txt"
        words_path.write_text("风险\nbadword\n", encoding="utf-8")
        page = SensitiveWordsPage(words_path=words_path)
        page.editor.setPlainText("badword 出现风险\n风险再次出现")

        result = page.check_current_text()

        self.assertIsNotNone(result)
        self.assertEqual(result.match_count, 3)
        self.assertEqual(len(page.editor.extraSelections()), 3)
        self.assertEqual(page.result_list.count(), 3)
        self.assertEqual(page.summary_label.text(), "命中 3 处 · 词库 2 个词")
        first_item = page.result_list.item(0).text()
        self.assertIn("第 1 行", first_item)
        self.assertIn("第 1 列", first_item)

        words_path.write_text("badword\n", encoding="utf-8")
        updated = page.check_current_text()

        self.assertIsNotNone(updated)
        self.assertEqual(updated.match_count, 1)
        self.assertEqual(len(page.editor.extraSelections()), 1)
        self.assertEqual(page.result_list.count(), 1)
        self.assertEqual(page.summary_label.text(), "命中 1 处 · 词库 1 个词")

    def test_missing_sensitive_words_file_shows_handled_error(self) -> None:
        page = SensitiveWordsPage(words_path=self.root / "missing.txt")
        page.editor.setPlainText("风险")

        result = page.check_current_text()

        self.assertIsNone(result)
        self.assertEqual(page.summary_label.text(), "词库不可用")
        self.assertEqual(page.feedback.kind, "error")
        self.assertIn("敏感词词库不存在", page.feedback.text_label.text())
        self.assertEqual(page.editor.toPlainText(), "风险")

    def test_shell_creates_real_notes_and_sensitive_pages(self) -> None:
        shell = AppShell(animations_enabled=False)
        self.addCleanup(shell.close)

        self.assertIsInstance(shell.notes_page, NotesPage)
        self.assertIsInstance(shell.sensitive_words_page, SensitiveWordsPage)
        shell.select_page("notes")
        self.assertEqual(shell.current_page_key, "notes")
        shell.select_page("sensitive")
        self.assertEqual(shell.current_page_key, "sensitive")


if __name__ == "__main__":
    unittest.main()
