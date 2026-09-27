from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from video_workbench.scripts import (
    ScriptDocument,
    ScriptError,
    ScriptService,
    scripts_directory,
)
from video_workbench.ui.components.messages import InlineMessage


class ScriptEditorPage(QWidget):
    message_requested = Signal(str, str, int)

    def __init__(
        self,
        parent=None,
        service: ScriptService | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service or ScriptService()
        self._project_root: Path | None = None
        self._current_document: ScriptDocument | None = None
        self._dirty = False
        self._suspend_text_tracking = False
        self._editor_states: dict[Path, tuple[int, int]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(7)

        self.new_button = self._toolbar_button(
            "新建",
            QStyle.StandardPixmap.SP_FileIcon,
            "新建 TXT 或 MD 脚本",
        )
        self.open_button = self._toolbar_button(
            "打开",
            QStyle.StandardPixmap.SP_DialogOpenButton,
            "从当前项目打开脚本",
        )
        self.save_button = self._toolbar_button(
            "保存",
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "保存当前脚本",
        )
        self.save_as_button = self._toolbar_button(
            "另存为",
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "将当前脚本另存为 TXT 或 MD",
        )
        self.export_txt_button = self._toolbar_button(
            "导出 TXT",
            QStyle.StandardPixmap.SP_FileIcon,
            "导出到当前项目“脚本文档”目录",
        )
        self.export_md_button = self._toolbar_button(
            "导出 MD",
            QStyle.StandardPixmap.SP_FileIcon,
            "导出到当前项目“脚本文档”目录",
        )
        self.copy_button = self._toolbar_button(
            "全选复制",
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "全选并复制当前脚本内容",
        )
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.save_button)
        toolbar.addWidget(self.save_as_button)
        toolbar.addSpacing(5)
        toolbar.addWidget(self.export_txt_button)
        toolbar.addWidget(self.export_md_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.copy_button)

        self.message = InlineMessage("", "info", self)
        self.message.setVisible(False)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        list_frame = QFrame(splitter)
        list_frame.setObjectName("DashboardCard")
        list_frame.setMinimumWidth(190)
        list_frame.setMaximumWidth(300)
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(8)
        list_title = QLabel("项目脚本", list_frame)
        list_title.setObjectName("CardTitle")
        self.document_list = QListWidget(list_frame)
        self.document_list.setObjectName("ScriptDocumentList")
        self.document_list.viewport().setObjectName("ScriptDocumentListViewport")
        self.document_list.itemClicked.connect(self._open_list_item)
        list_layout.addWidget(list_title)
        list_layout.addWidget(self.document_list, 1)

        editor_frame = QFrame(splitter)
        editor_frame.setObjectName("DashboardCard")
        editor_layout = QVBoxLayout(editor_frame)
        editor_layout.setContentsMargins(12, 12, 12, 12)
        editor_layout.setSpacing(8)

        editor_header = QHBoxLayout()
        self.document_label = QLabel("未选择文档", editor_frame)
        self.document_label.setObjectName("CardTitle")
        self.save_status = QLabel("未选择文档", editor_frame)
        self.save_status.setObjectName("SaveStatus")
        editor_header.addWidget(self.document_label)
        editor_header.addStretch(1)
        editor_header.addWidget(self.save_status)

        self.editor = QPlainTextEdit(editor_frame)
        self.editor.setObjectName("ScriptEditor")
        self.editor.viewport().setObjectName("ScriptEditorViewport")
        self.editor.setPlaceholderText("请先打开项目，然后新建或打开脚本文档")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setReadOnly(True)
        self.editor.textChanged.connect(self._handle_text_changed)

        editor_layout.addLayout(editor_header)
        editor_layout.addWidget(self.editor, 1)

        splitter.addWidget(list_frame)
        splitter.addWidget(editor_frame)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([230, 760])

        layout.addLayout(toolbar)
        layout.addWidget(self.message)
        layout.addWidget(splitter, 1)

        self.new_button.clicked.connect(self.prompt_create_document)
        self.open_button.clicked.connect(self.prompt_open_document)
        self.save_button.clicked.connect(self.save_document)
        self.save_as_button.clicked.connect(self.prompt_save_as)
        self.export_txt_button.clicked.connect(
            lambda: self.export_document(".txt")
        )
        self.export_md_button.clicked.connect(
            lambda: self.export_document(".md")
        )
        self.copy_button.clicked.connect(self.copy_all)
        self.set_project(None)

    def _toolbar_button(
        self,
        text: str,
        icon: QStyle.StandardPixmap,
        tooltip: str,
    ) -> QPushButton:
        button = QPushButton(text, self)
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        return button

    @property
    def project_root(self) -> Path | None:
        return self._project_root

    @property
    def current_document(self) -> ScriptDocument | None:
        return self._current_document

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
            self._refresh_documents()
            self._update_action_state()
            return True
        if self._dirty and not self.autosave():
            return False

        self._project_root = new_root
        self._current_document = None
        self._dirty = False
        self._editor_states.clear()
        self._set_editor_text("")
        self.document_label.setText("未选择文档")
        self.document_label.setToolTip("")
        self._set_save_status("empty")
        self._refresh_documents()
        self._update_action_state()
        return True

    def prompt_create_document(self) -> ScriptDocument | None:
        if self._project_root is None:
            self._show_feedback("请先打开项目，再新建脚本文档", "warning")
            return None

        filename, accepted = QInputDialog.getText(
            self,
            "新建脚本文档",
            "文件名（支持 .txt 和 .md）：",
            text="新脚本.txt",
        )
        if not accepted:
            return None
        return self.create_document(filename)

    def create_document(self, filename: str) -> ScriptDocument | None:
        if self._project_root is None:
            self._show_feedback("请先打开项目，再新建脚本文档", "warning")
            return None

        if self._dirty and not self.autosave():
            return None

        try:
            document = self._service.create_document(
                self._project_root,
                filename,
            )
        except ScriptError as error:
            self._show_feedback(str(error), "error")
            return None

        self._editor_states.clear()
        self._refresh_documents()
        self._open_document(document, save_current=False)
        self._show_feedback(f"已新建脚本：{document.name}", "success")
        return document

    def prompt_open_document(self) -> ScriptDocument | None:
        if self._project_root is None:
            self._show_feedback("请先打开项目，再打开脚本文档", "warning")
            return None

        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "打开脚本文档",
            str(scripts_directory(self._project_root)),
            "脚本文档 (*.txt *.md);;文本文件 (*.txt);;Markdown 文件 (*.md)",
        )
        if not selected_file:
            return None
        return self.open_document(selected_file)

    def open_document(self, path: str | Path) -> ScriptDocument | None:
        if self._project_root is None:
            self._show_feedback("请先打开项目，再打开脚本文档", "warning")
            return None

        document_path = Path(path).expanduser().resolve()
        try:
            self._validate_document_path(document_path)
        except ScriptError as error:
            self._show_feedback(str(error), "error")
            return None

        if (
            self._current_document is not None
            and self._current_document.path == document_path
        ):
            if self._dirty and not self.autosave():
                return None
            return self._current_document

        if self._dirty and not self.autosave():
            return None

        try:
            document = self._service.read_document(path)
        except ScriptError as error:
            self._show_feedback(str(error), "error")
            return None

        if not self._open_document(document, save_current=False):
            return None
        self._show_feedback(f"已打开脚本：{document.name}", "success")
        return document

    def _open_list_item(self, item: QListWidgetItem) -> None:
        path_value = item.data(Qt.ItemDataRole.UserRole)
        if path_value:
            self.open_document(str(path_value))

    def _open_document(
        self,
        document: ScriptDocument,
        save_current: bool = True,
    ) -> bool:
        if save_current and self._dirty and not self.autosave():
            return False

        self._remember_editor_state()
        self._current_document = document
        self._set_editor_text(document.content)
        self._dirty = False
        self.document_label.setText(document.name)
        self.document_label.setToolTip(str(document.path))
        self._set_save_status("saved")
        self._restore_editor_state(document.path)
        self._select_document_in_list(document.path)
        self._update_action_state()
        return True

    def save_document(self) -> bool:
        return self.autosave(force=True)

    def autosave(self, force: bool = False) -> bool:
        if self._current_document is None or self._project_root is None:
            return True
        if not self._dirty and not force:
            return True

        self._set_save_status("saving")
        try:
            saved = self._service.save_document(
                self._current_document,
                self.editor.toPlainText(),
                self._project_root,
            )
        except ScriptError as error:
            self._set_save_status("dirty")
            self._show_feedback(str(error), "error")
            return False

        self._current_document = saved
        self._dirty = False
        self._set_save_status("saved")
        self._refresh_documents()
        self._select_document_in_list(saved.path)
        self._update_action_state()
        if force:
            self._show_feedback("脚本已保存", "success")
        return True

    def prompt_save_as(self) -> ScriptDocument | None:
        if self._project_root is None or self._current_document is None:
            self._show_feedback("请先打开一个脚本文档", "warning")
            return None

        selected_file, _ = QFileDialog.getSaveFileName(
            self,
            "脚本另存为",
            str(
                scripts_directory(self._project_root)
                / self._current_document.name
            ),
            "文本文件 (*.txt);;Markdown 文件 (*.md)",
        )
        if not selected_file:
            return None
        return self.save_as_document(selected_file)

    def save_as_document(self, target_path: str | Path) -> ScriptDocument | None:
        if self._project_root is None or self._current_document is None:
            self._show_feedback("请先打开一个脚本文档", "warning")
            return None

        try:
            document = self._service.save_as_document(
                self._project_root,
                target_path,
                self.editor.toPlainText(),
            )
        except ScriptError as error:
            self._show_feedback(str(error), "error")
            return None

        self._current_document = document
        self._dirty = False
        self.document_label.setText(document.name)
        self.document_label.setToolTip(str(document.path))
        self._set_save_status("saved")
        self._refresh_documents()
        self._select_document_in_list(document.path)
        self._update_action_state()
        self._show_feedback(f"已另存为：{document.name}", "success")
        return document

    def export_document(self, extension: str) -> ScriptDocument | None:
        if self._project_root is None or self._current_document is None:
            self._show_feedback("请先打开一个脚本文档", "warning")
            return None

        try:
            exported = self._service.export_document(
                self._project_root,
                self._current_document,
                self.editor.toPlainText(),
                extension,
            )
        except ScriptError as error:
            self._show_feedback(str(error), "error")
            return None

        if exported.path == self._current_document.path:
            self._current_document = exported
            self._dirty = False
            self._set_save_status("saved")
        self._refresh_documents()
        self._select_document_in_list(self._current_document.path)
        self._update_action_state()
        self._show_feedback(f"已导出到：{exported.path}", "success")
        return exported

    def copy_all(self) -> bool:
        if self._current_document is None:
            self._show_feedback("请先打开一个脚本文档", "warning")
            return False

        self.editor.selectAll()
        self.editor.copy()
        if QApplication.clipboard().text() != self.editor.toPlainText():
            QApplication.clipboard().setText(self.editor.toPlainText())
        self._show_feedback("脚本内容已全选并复制", "success")
        return True

    def _handle_text_changed(self) -> None:
        if self._suspend_text_tracking or self._current_document is None:
            return
        self._dirty = True
        self._set_save_status("dirty")
        self._update_action_state()

    def _set_editor_text(self, content: str) -> None:
        self._suspend_text_tracking = True
        try:
            self.editor.setPlainText(content)
        finally:
            self._suspend_text_tracking = False

    def _remember_editor_state(self) -> None:
        if self._current_document is None:
            return
        self._editor_states[self._current_document.path] = (
            self.editor.textCursor().position(),
            self.editor.verticalScrollBar().value(),
        )

    def _restore_editor_state(self, path: Path) -> None:
        cursor_position, scroll_value = self._editor_states.get(path, (0, 0))
        cursor = self.editor.textCursor()
        cursor.setPosition(min(cursor_position, len(self.editor.toPlainText())))
        self.editor.setTextCursor(cursor)
        self.editor.verticalScrollBar().setValue(scroll_value)

    def _refresh_documents(self) -> None:
        current_path = (
            self._current_document.path
            if self._current_document is not None
            else None
        )
        self.document_list.clear()
        if self._project_root is None:
            return

        try:
            documents = self._service.list_documents(self._project_root)
        except ScriptError as error:
            self._show_feedback(str(error), "error")
            return

        for path in documents:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.document_list.addItem(item)
        if current_path is not None:
            self._select_document_in_list(current_path)

    def _select_document_in_list(self, path: Path) -> None:
        for index in range(self.document_list.count()):
            item = self.document_list.item(index)
            if Path(str(item.data(Qt.ItemDataRole.UserRole))).resolve() == path.resolve():
                self.document_list.setCurrentItem(item)
                return

    def _validate_document_path(self, path: Path) -> None:
        if self._project_root is None:
            raise ScriptError("请先打开项目")
        try:
            path.resolve().relative_to(
                scripts_directory(self._project_root)
            )
        except ValueError as error:
            raise ScriptError(
                "脚本文档必须位于当前项目的“脚本文档”目录内"
            ) from error

    def _update_action_state(self) -> None:
        has_project = self._project_root is not None
        has_document = self._current_document is not None
        self.new_button.setEnabled(has_project)
        self.open_button.setEnabled(has_project)
        self.document_list.setEnabled(has_project)
        self.editor.setReadOnly(not has_document)
        self.save_button.setEnabled(has_document and self._dirty)
        self.save_as_button.setEnabled(has_document)
        self.export_txt_button.setEnabled(has_document)
        self.export_md_button.setEnabled(has_document)
        self.copy_button.setEnabled(has_document)

    def _set_save_status(self, status: str) -> None:
        labels = {
            "empty": "未选择文档",
            "dirty": "未保存",
            "saving": "保存中",
            "saved": "已保存",
        }
        self.save_status.setText(labels[status])
        self.save_status.setProperty("status", status)
        style = self.save_status.style()
        style.unpolish(self.save_status)
        style.polish(self.save_status)

    def _show_feedback(self, message: str, kind: str) -> None:
        self.message.set_message(message, kind)
        self.message_requested.emit(message, kind, 4000)
