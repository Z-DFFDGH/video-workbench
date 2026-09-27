from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._ui import application

from video_workbench.app import ConfigStore
from video_workbench.project import create_project
from video_workbench.scripts import ScriptError, scripts_directory
from video_workbench.ui.main_window import MainWindow
from video_workbench.ui.pages import ScriptEditorPage


class ScriptEditorUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.project = create_project(self.root / "project")
        self.page = ScriptEditorPage()
        self.page.set_project(self.project.root)

    def test_no_project_disables_new_and_editor(self) -> None:
        page = ScriptEditorPage()

        page.set_project(None)

        self.assertFalse(page.new_button.isEnabled())
        self.assertFalse(page.open_button.isEnabled())
        self.assertTrue(page.editor.isReadOnly())
        page.prompt_create_document()
        self.assertIn("请先打开项目", page.message.text_label.text())

    def test_create_edit_and_save_document(self) -> None:
        document = self.page.create_document("口播.txt")
        self.assertIsNotNone(document)
        content = "[00:23] 切换画面\n# 标题\n中文台词"

        self.page.editor.setPlainText(content)

        self.assertTrue(self.page.has_unsaved_changes)
        self.assertEqual(self.page.save_status.text(), "未保存")
        self.assertTrue(self.page.save_button.isEnabled())
        self.assertTrue(self.page.save_document())

        self.assertFalse(self.page.has_unsaved_changes)
        self.assertEqual(self.page.save_status.text(), "已保存")
        self.assertEqual(document.path.read_text(encoding="utf-8"), content)

    def test_autosave_failure_keeps_unsaved_state_and_content(self) -> None:
        document = self.page.create_document("锁定.txt")
        self.page.editor.setPlainText("尚未保存")

        with patch.object(
            self.page._service,
            "save_document",
            side_effect=ScriptError("目标文件被占用"),
        ):
            saved = self.page.autosave()

        self.assertFalse(saved)
        self.assertTrue(self.page.has_unsaved_changes)
        self.assertEqual(self.page.save_status.text(), "未保存")
        self.assertEqual(self.page.editor.toPlainText(), "尚未保存")
        self.assertEqual(document.path.read_text(encoding="utf-8"), "")

    def test_export_uses_project_scripts_directory_without_dialog(self) -> None:
        document = self.page.create_document("口播.txt")
        self.page.editor.setPlainText("导出正文")

        exported = self.page.export_document(".md")

        self.assertIsNotNone(exported)
        self.assertEqual(exported.path, scripts_directory(self.project.root) / "口播.md")
        self.assertEqual(exported.path.read_text(encoding="utf-8"), "导出正文")
        self.assertEqual(document.path.read_text(encoding="utf-8"), "")

    def test_save_as_uses_dialog_and_keeps_original_path(self) -> None:
        original = self.page.create_document("原稿.txt")
        target = scripts_directory(self.project.root) / "副本.md"
        self.page.editor.setPlainText("副本内容")

        with patch(
            "video_workbench.ui.pages.scripts.QFileDialog.getSaveFileName",
            return_value=(str(target), "Markdown 文件 (*.md)"),
        ):
            copied = self.page.prompt_save_as()

        self.assertIsNotNone(copied)
        self.assertEqual(copied.path, target.resolve())
        self.assertEqual(copied.path.read_text(encoding="utf-8"), "副本内容")
        self.assertEqual(original.path.read_text(encoding="utf-8"), "")

    def test_copy_all_matches_editor_content(self) -> None:
        self.page.create_document("复制.txt")
        content = "[00:23] 第一行\n第二行"
        self.page.editor.setPlainText(content)

        self.assertTrue(self.page.copy_all())

        self.assertEqual(self.app.clipboard().text(), content)

    def test_switching_documents_restores_cursor_position(self) -> None:
        first = self.page.create_document("一.txt")
        second = self.page.create_document("二.txt")
        self.page.editor.setPlainText("[00:23] 切换画面\n第二行")
        cursor = self.page.editor.textCursor()
        cursor.setPosition(7)
        self.page.editor.setTextCursor(cursor)

        self.page.open_document(second.path)
        self.page.open_document(first.path)

        self.assertEqual(self.page.current_document.path, first.path)
        self.page.open_document(second.path)

        self.assertEqual(self.page.editor.textCursor().position(), 7)

    def test_main_window_autosaves_before_switch_and_close(self) -> None:
        second_project = create_project(self.root / "second")
        window = MainWindow(
            config_store=ConfigStore(self.root / "config.json"),
            animations_enabled=False,
        )
        self.addCleanup(window.close)
        window._open_project_path(str(self.project.project_file))
        page = window.shell.scripts_page
        document = page.create_document("自动保存.txt")
        page.editor.setPlainText("切换前保存")

        window._open_project_path(str(second_project.project_file))

        self.assertEqual(
            document.path.read_text(encoding="utf-8"),
            "切换前保存",
        )
        self.assertEqual(page.project_root, second_project.root.resolve())

        second_document = page.create_document("关闭保存.txt")
        page.editor.setPlainText("关闭前保存")
        window.close()

        self.assertEqual(
            second_document.path.read_text(encoding="utf-8"),
            "关闭前保存",
        )


if __name__ == "__main__":
    unittest.main()
