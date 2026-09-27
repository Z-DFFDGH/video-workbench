from __future__ import annotations

import unittest

from tests._ui import application

from PySide6.QtWidgets import QDialog
from PySide6.QtTest import QTest

from video_workbench.ui.components import (
    ConfirmDialog,
    InlineMessage,
    LoadingButton,
    ToastHost,
)


class UiComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def test_loading_button_enters_and_leaves_loading_state(self) -> None:
        button = LoadingButton("开始处理")

        button.set_loading(True)
        self.assertTrue(button.is_loading)
        self.assertFalse(button.isEnabled())
        self.assertTrue(button.text().startswith("处理中"))
        self.assertEqual(button.spinner_angle, 0)
        button._advance_animation()
        self.assertEqual(button.spinner_angle, 30)

        button.set_loading(False)
        self.assertFalse(button.is_loading)
        self.assertTrue(button.isEnabled())
        self.assertEqual(button.spinner_angle, 0)
        self.assertEqual(button.text(), "开始处理")

    def test_loading_button_keeps_custom_loading_prefix_during_animation(self) -> None:
        button = LoadingButton("开始导入")

        button.set_loading(True, "正在导入")
        button._advance_animation()

        self.assertTrue(button.text().startswith("正在导入"))
        self.assertNotIn("处理中", button.text())

    def test_inline_message_normalizes_unknown_kind(self) -> None:
        message = InlineMessage("测试消息", "unknown")

        self.assertEqual(message.kind, "info")
        message.set_message("失败", "error")
        self.assertEqual(message.kind, "error")
        self.assertEqual(message.text_label.text(), "失败")

    def test_toast_host_deduplicates_identical_active_messages(self) -> None:
        host = ToastHost()

        first = host.show_message("任务完成", "success", duration_ms=0)
        second = host.show_message("任务完成", "success", duration_ms=0)

        self.assertIs(first, second)
        self.assertEqual(list(host.active_messages), [("任务完成", "success")])
        self.assertIsNotNone(host.reveal_animation)
        self.assertEqual(host.reveal_animation.duration(), 220)
        QTest.qWait(350)
        self.assertIsNone(first.graphicsEffect())
        third = host.show_message("任务完成", "success", duration_ms=0)
        self.assertIs(third, first)
        self.assertIsNotNone(host.reveal_animation)

    def test_confirm_dialog_accepts_and_rejects(self) -> None:
        dialog = ConfirmDialog("删除项目", "确定删除吗？", destructive=True)
        dialog.confirm_button.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

        dialog = ConfirmDialog("取消任务", "确定取消吗？")
        dialog.cancel_button.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)


if __name__ == "__main__":
    unittest.main()
