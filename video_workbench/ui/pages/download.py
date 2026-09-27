from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from video_workbench.downloader import DownloadMode, parse_link_input
from video_workbench.ui.components.messages import InlineMessage


class DownloadPage(QWidget):
    download_requested = Signal(object, str, object, bool)
    output_directory_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._project_root: Path | None = None
        self._last_directory = str(Path.home() / "Downloads")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        input_card = QFrame(self)
        input_card.setObjectName("DashboardCard")
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(16, 14, 16, 14)
        input_layout.setSpacing(9)

        input_header = QHBoxLayout()
        title = QLabel("批量链接", input_card)
        title.setObjectName("CardTitle")
        self.validation_label = QLabel("尚未输入链接", input_card)
        self.validation_label.setObjectName("MetaText")
        input_header.addWidget(title)
        input_header.addStretch(1)
        input_header.addWidget(self.validation_label)

        self.link_input = QPlainTextEdit(input_card)
        self.link_input.setObjectName("DownloadLinkInput")
        self.link_input.setPlaceholderText("每行一个链接")
        self.link_input.setMinimumHeight(142)
        self.link_input.setMaximumHeight(210)
        self.link_input.textChanged.connect(self._validate_links)

        self.validation_message = InlineMessage("", "warning", input_card)
        self.validation_message.setVisible(False)

        input_layout.addLayout(input_header)
        input_layout.addWidget(self.link_input)
        input_layout.addWidget(self.validation_message)

        options_card = QFrame(self)
        options_card.setObjectName("DashboardCard")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(16, 14, 16, 14)
        options_layout.setSpacing(10)

        directory_row = QHBoxLayout()
        directory_label = QLabel("保存目录", options_card)
        directory_label.setObjectName("SecondaryText")
        self.output_edit = QLineEdit(options_card)
        self.output_edit.setObjectName("PathInput")
        self.output_edit.setClearButtonEnabled(True)
        self.output_edit.editingFinished.connect(self._remember_current_directory)
        self.browse_button = QPushButton(options_card)
        self.browse_button.setObjectName("IconButton")
        self.browse_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DirOpenIcon
            )
        )
        self.browse_button.setToolTip("选择保存目录")
        self.browse_button.clicked.connect(self._choose_output_directory)
        directory_row.addWidget(directory_label)
        directory_row.addWidget(self.output_edit, 1)
        directory_row.addWidget(self.browse_button)

        mode_row = QHBoxLayout()
        mode_label = QLabel("下载内容", options_card)
        mode_label.setObjectName("SecondaryText")
        self.mode_combo = QComboBox(options_card)
        self.mode_combo.setObjectName("RangeSelector")
        self.mode_combo.addItem("完整视频", DownloadMode.VIDEO)
        self.mode_combo.addItem("仅提取音频", DownloadMode.AUDIO)
        self.library_checkbox = QCheckBox("完成后加入项目素材库", options_card)
        self.library_checkbox.setChecked(False)
        self.library_checkbox.setEnabled(False)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.mode_combo)
        mode_row.addSpacing(10)
        mode_row.addWidget(self.library_checkbox)
        mode_row.addStretch(1)

        options_layout.addLayout(directory_row)
        options_layout.addLayout(mode_row)

        action_row = QHBoxLayout()
        self.queue_summary = QLabel("下载队列为空", self)
        self.queue_summary.setObjectName("MetaText")
        self.start_button = QPushButton("开始下载", self)
        self.start_button.setProperty("role", "primary")
        self.start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        )
        self.start_button.clicked.connect(self._start_download)
        action_row.addWidget(self.queue_summary)
        action_row.addStretch(1)
        action_row.addWidget(self.start_button)

        layout.addWidget(input_card)
        layout.addWidget(options_card)
        layout.addLayout(action_row)
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_project(self, project_root: str | Path | None) -> None:
        self._project_root = (
            Path(project_root).expanduser().resolve()
            if project_root is not None
            else None
        )
        self.library_checkbox.setEnabled(self._project_root is not None)
        if self._project_root is None:
            self.library_checkbox.setChecked(False)
            self.output_edit.setText(self._last_directory)
        else:
            self.output_edit.setText(str(self._project_root / "输出成品"))

    def set_last_directory(self, directory: str | None) -> None:
        if directory and directory.strip():
            self._last_directory = str(Path(directory).expanduser().resolve())
        if self._project_root is None:
            self.output_edit.setText(self._last_directory)

    def set_queue_summary(
        self,
        active_count: int,
        failed_count: int,
        total_count: int,
    ) -> None:
        if total_count <= 0:
            self.queue_summary.setText("下载队列为空")
        elif failed_count > 0:
            self.queue_summary.setText(
                f"共 {total_count} 个任务，进行中 {active_count}，失败 {failed_count}"
            )
        else:
            self.queue_summary.setText(
                f"共 {total_count} 个任务，进行中 {active_count}"
            )

    def _validate_links(self) -> None:
        result = parse_link_input(self.link_input.toPlainText())
        valid_count = len(result.urls)
        invalid_count = len(result.invalid_lines)
        if valid_count == 0 and invalid_count == 0:
            self.validation_label.setText("尚未输入链接")
            self.validation_message.setVisible(False)
            return

        self.validation_label.setText(
            f"有效 {valid_count}，忽略 {invalid_count}"
        )
        if invalid_count == 0:
            self.validation_message.setVisible(False)
            return

        details = "；".join(
            f"第 {line.line_number} 行：{line.reason}"
            for line in result.invalid_lines[:4]
        )
        if invalid_count > 4:
            details += f"；另有 {invalid_count - 4} 行"
        self.validation_message.set_message(
            f"已忽略 {invalid_count} 行无效输入。{details}",
            "warning",
        )

    def _choose_output_directory(self) -> None:
        current = self.output_edit.text().strip()
        start_directory = current if Path(current).is_dir() else str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择下载保存目录",
            start_directory,
        )
        if selected:
            self.output_edit.setText(selected)
            self._remember_current_directory()

    def _remember_current_directory(self) -> None:
        directory = self.output_edit.text().strip()
        if not directory:
            return
        self._last_directory = str(Path(directory).expanduser().resolve())
        self.output_directory_changed.emit(self._last_directory)

    def _start_download(self) -> None:
        result = parse_link_input(self.link_input.toPlainText())
        if not result.urls:
            self.validation_message.set_message("没有可下载的有效链接", "error")
            return

        directory = self.output_edit.text().strip()
        if not directory:
            self.validation_message.set_message("请选择下载保存目录", "error")
            return

        self._remember_current_directory()
        mode = self.mode_combo.currentData()
        self.download_requested.emit(
            list(result.urls),
            directory,
            mode,
            self.library_checkbox.isChecked(),
        )
        self.link_input.clear()
        self.validation_message.set_message(
            f"已加入下载队列：{len(result.urls)} 个任务",
            "success",
        )
