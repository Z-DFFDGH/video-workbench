from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from video_workbench.sensitive_words import (
    SensitiveWordsError,
    SensitiveWordsService,
    default_sensitive_words_path,
)
from video_workbench.ui.components.messages import InlineMessage


class SensitiveWordsPage(QWidget):
    message_requested = Signal(str, str, int)

    def __init__(
        self,
        parent=None,
        service: SensitiveWordsService | None = None,
        words_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service or SensitiveWordsService()
        self._words_path = (
            Path(words_path).expanduser().resolve()
            if words_path is not None
            else default_sensitive_words_path()
        )
        self.last_result = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        editor_card = QFrame(self)
        editor_card.setObjectName("DashboardCard")
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(16, 14, 16, 14)
        editor_layout.setSpacing(9)

        editor_header = QHBoxLayout()
        title = QLabel("待检查文本", editor_card)
        title.setObjectName("CardTitle")
        self.check_button = QPushButton("检查当前文本", editor_card)
        self.check_button.setProperty("role", "primary")
        self.check_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        )
        self.check_button.clicked.connect(self.check_current_text)
        editor_header.addWidget(title)
        editor_header.addStretch(1)
        editor_header.addWidget(self.check_button)

        self.editor = QPlainTextEdit(editor_card)
        self.editor.setObjectName("SensitiveTextEditor")
        self.editor.viewport().setObjectName("SensitiveTextEditorViewport")
        self.editor.setPlaceholderText("粘贴或输入脚本文本，然后点击“检查当前文本”。")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        editor_layout.addLayout(editor_header)
        editor_layout.addWidget(self.editor, 1)

        result_card = QFrame(self)
        result_card.setObjectName("DashboardCard")
        result_card.setMinimumWidth(300)
        result_card.setMaximumWidth(380)
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(16, 14, 16, 14)
        result_layout.setSpacing(9)

        result_title = QLabel("检查结果", result_card)
        result_title.setObjectName("CardTitle")
        self.summary_label = QLabel("尚未检查", result_card)
        self.summary_label.setObjectName("MetricLabel")

        path_title = QLabel("本地词库", result_card)
        path_title.setObjectName("MetaText")
        self.words_path_label = QLabel(str(self._words_path), result_card)
        self.words_path_label.setObjectName("PathHint")
        self.words_path_label.setWordWrap(True)
        self.words_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.result_list = QListWidget(result_card)
        self.result_list.setObjectName("SensitiveMatchList")
        self.result_list.viewport().setObjectName("SensitiveMatchListViewport")

        self.feedback = InlineMessage("", "info", result_card)
        self.feedback.setVisible(False)

        result_layout.addWidget(result_title)
        result_layout.addWidget(self.summary_label)
        result_layout.addWidget(path_title)
        result_layout.addWidget(self.words_path_label)
        result_layout.addWidget(self.result_list, 1)
        result_layout.addWidget(self.feedback)

        layout.addWidget(editor_card, 1)
        layout.addWidget(result_card)

    @property
    def words_path(self) -> Path:
        return self._words_path

    def set_words_path(self, path: str | Path) -> None:
        self._words_path = Path(path).expanduser().resolve()
        self.words_path_label.setText(str(self._words_path))
        self.words_path_label.setToolTip(str(self._words_path))
        self.last_result = None
        self.result_list.clear()
        self.editor.setExtraSelections([])
        self.summary_label.setText("尚未检查")
        self.feedback.setVisible(False)

    def check_current_text(self):
        self.editor.setExtraSelections([])
        self.result_list.clear()
        try:
            library = self._service.load_library(self._words_path)
        except SensitiveWordsError as error:
            self.last_result = None
            self.summary_label.setText("词库不可用")
            self._show_feedback(str(error), "error")
            return None

        result = self._service.check_text(self.editor.toPlainText(), library)
        self.last_result = result
        self.summary_label.setText(
            f"命中 {result.match_count} 处 · 词库 {result.word_count} 个词"
        )

        selections = []
        document = self.editor.document()
        for match in result.matches:
            cursor = QTextCursor(document)
            cursor.setPosition(match.start)
            cursor.setPosition(match.end, QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(QColor("#9B405F"))
            selection.format.setForeground(QColor("#FFF4F8"))
            selections.append(selection)

            item = QListWidgetItem(
                f"第 {match.line} 行，第 {match.column} 列 · "
                f"{match.word} · {match.matched_text}"
            )
            item.setToolTip(
                f"字符位置：{match.start} - {match.end}\n词条：{match.word}"
            )
            self.result_list.addItem(item)

        self.editor.setExtraSelections(selections)
        if result.match_count:
            self._show_feedback(
                f"已高亮 {result.match_count} 处命中，位置与结果列表一致。",
                "warning",
            )
        else:
            self._show_feedback("未发现敏感词。", "success")
        return result

    def _show_feedback(self, message: str, kind: str) -> None:
        self.feedback.set_message(message, kind)
        self.message_requested.emit(message, kind, 4000)
