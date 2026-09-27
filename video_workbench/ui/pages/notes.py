from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from video_workbench.notes import NotesError, NotesService, notes_path
from video_workbench.ui.components.messages import InlineMessage


class NotesPage(QWidget):
    message_requested = Signal(str, str, int)

    def __init__(
        self,
        parent=None,
        service: NotesService | None = None,
        auto_save_interval_ms: int = 800,
    ) -> None:
        super().__init__(parent)
        self._service = service or NotesService()
        self._project_root: Path | None = None
        self._dirty = False
        self._load_failed = False
        self._suspend_text_tracking = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = QFrame(self)
        card.setObjectName("DashboardCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(9)

        header = QHBoxLayout()
        title = QLabel("项目笔记", card)
        title.setObjectName("CardTitle")
        self.path_label = QLabel("未打开项目", card)
        self.path_label.setObjectName("PathHint")
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.save_status = QLabel("未打开项目", card)
        self.save_status.setObjectName("SaveStatus")
        header.addWidget(title)
        header.addWidget(self.path_label, 1)
        header.addWidget(self.save_status)

        self.editor = QPlainTextEdit(card)
        self.editor.setObjectName("NotesEditor")
        self.editor.viewport().setObjectName("NotesEditorViewport")
        self.editor.setPlaceholderText("请先打开项目，再记录选题、发布平台和创作备注。")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setReadOnly(True)
        self.editor.textChanged.connect(self._handle_text_changed)

        self.message = InlineMessage("", "info", card)
        self.message.setVisible(False)

        card_layout.addLayout(header)
        card_layout.addWidget(self.editor, 1)
        card_layout.addWidget(self.message)
        layout.addWidget(card, 1)

        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(max(0, auto_save_interval_ms))
        self._auto_save_timer.timeout.connect(self.autosave)
        self.set_project(None)

    @property
    def project_root(self) -> Path | None:
        return self._project_root

    @property
    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def set_project(self, project_root: str | Path | None) -> bool:
        new_root = (
            Path(project_root).expanduser().resolve()
            if project_root is not None
            else None
        )
        if new_root == self._project_root:
            return True
        if self._dirty and not self.autosave():
            return False

        self._auto_save_timer.stop()
        self._project_root = new_root
        self._dirty = False
        self._load_failed = False
        self._set_editor_text("")

        if new_root is None:
            self.path_label.setText("未打开项目")
            self.path_label.setToolTip("")
            self._set_save_status("empty")
            self.editor.setReadOnly(True)
            return True

        path = notes_path(new_root)
        self.path_label.setText(str(path))
        self.path_label.setToolTip(str(path))
        try:
            content = self._service.load_or_create(new_root)
        except NotesError as error:
            self._load_failed = True
            self.editor.setReadOnly(True)
            self._set_save_status("error")
            self._show_feedback(str(error), "error")
            return True

        self._set_editor_text(content)
        self.editor.setReadOnly(False)
        self._set_save_status("saved")
        self.message.setVisible(False)
        return True

    def autosave(self, force: bool = False) -> bool:
        if (
            self._project_root is None
            or self._load_failed
            or (not self._dirty and not force)
        ):
            return True

        self._auto_save_timer.stop()
        self._set_save_status("saving")
        try:
            self._service.save(self._project_root, self.editor.toPlainText())
        except NotesError as error:
            self._dirty = True
            self._set_save_status("dirty")
            self._show_feedback(str(error), "error")
            return False

        self._dirty = False
        self._set_save_status("saved")
        if force:
            self._show_feedback("项目笔记已保存", "success")
        return True

    def _handle_text_changed(self) -> None:
        if (
            self._suspend_text_tracking
            or self._project_root is None
            or self._load_failed
        ):
            return
        self._dirty = True
        self._set_save_status("dirty")
        self._auto_save_timer.start()

    def _set_editor_text(self, content: str) -> None:
        self._suspend_text_tracking = True
        try:
            self.editor.setPlainText(content)
        finally:
            self._suspend_text_tracking = False

    def _set_save_status(self, status: str) -> None:
        labels = {
            "empty": "未打开项目",
            "dirty": "未保存",
            "saving": "保存中",
            "saved": "已保存",
            "error": "读取失败",
        }
        self.save_status.setText(labels[status])
        self.save_status.setProperty("status", status)
        style = self.save_status.style()
        style.unpolish(self.save_status)
        style.polish(self.save_status)

    def _show_feedback(self, message: str, kind: str) -> None:
        self.message.set_message(message, kind)
        self.message_requested.emit(message, kind, 4000)
