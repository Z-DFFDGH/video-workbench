from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from video_workbench.media_tools import (
    MediaCommandError,
    MediaTask,
    MediaTaskStatus,
    MediaToolService,
    conversion_request,
    resize_request,
    trim_request,
    volume_request,
)
from video_workbench.ui.components.messages import InlineMessage

MEDIA_FILE_FILTER = (
    "媒体文件 (*.mp4 *.mov *.mkv *.webm *.mp3 *.wav *.aac *.flac);;"
    "所有文件 (*.*)"
)
TARGET_FORMATS = (
    ("MP4", ".mp4"),
    ("MOV", ".mov"),
    ("MKV", ".mkv"),
    ("WEBM", ".webm"),
    ("MP3", ".mp3"),
    ("WAV", ".wav"),
    ("AAC", ".aac"),
    ("FLAC", ".flac"),
)
RESIZE_PRESETS = (
    ("9:16 竖屏 1080x1920", 1080, 1920),
    ("16:9 横屏 1920x1080", 1920, 1080),
    ("1:1 正方形 1080x1080", 1080, 1080),
)
TOOL_LABELS = {
    "format": "格式转换",
    "trim": "片段截取",
    "resize": "分辨率处理",
    "volume": "音量调整",
}
TASK_STATUS_LABELS = {
    MediaTaskStatus.QUEUED: "等待",
    MediaTaskStatus.RUNNING: "进行中",
    MediaTaskStatus.COMPLETED: "完成",
    MediaTaskStatus.FAILED: "失败",
    MediaTaskStatus.CANCELED: "已取消",
}


class MediaToolsPage(QWidget):
    message_requested = Signal(str, str, int)
    output_directory_changed = Signal(str)
    context_changed = Signal(str, str)

    def __init__(
        self,
        parent=None,
        service: MediaToolService | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or MediaToolService(parent=self)
        self._project_root: Path | None = None
        self._last_directory = str(Path.home() / "Downloads")
        self._current_tool = "format"
        self._current_task_id: str | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(12)

        card = QFrame(self)
        card.setObjectName("DashboardCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("媒体处理", card)
        title.setObjectName("CardTitle")
        self.queue_summary = QLabel("工具队列为空", card)
        self.queue_summary.setObjectName("MetaText")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.queue_summary)

        tool_row = QHBoxLayout()
        tool_row.setSpacing(7)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons: dict[str, QToolButton] = {}
        for key, label in TOOL_LABELS.items():
            button = QToolButton(card)
            button.setObjectName("ToolCategoryButton")
            button.setText(label)
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, tool_key=key: self._set_tool(tool_key)
            )
            self.tool_group.addButton(button)
            self.tool_buttons[key] = button
            tool_row.addWidget(button)
        tool_row.addStretch(1)
        self.tool_buttons["format"].setChecked(True)

        input_row = QHBoxLayout()
        input_label = QLabel("输入文件", card)
        input_label.setObjectName("SecondaryText")
        self.input_edit = QLineEdit(card)
        self.input_edit.setObjectName("PathInput")
        self.input_edit.setPlaceholderText("选择任意本地视频或音频")
        self.input_edit.setReadOnly(True)
        self.choose_input_button = QPushButton(card)
        self.choose_input_button.setObjectName("IconButton")
        self.choose_input_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self.choose_input_button.setToolTip("选择输入文件")
        self.choose_input_button.clicked.connect(self.choose_input_file)
        input_row.addWidget(input_label)
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.choose_input_button)

        self.parameter_stack = QStackedWidget(card)
        self.parameter_stack.addWidget(self._build_format_page())
        self.parameter_stack.addWidget(self._build_trim_page())
        self.parameter_stack.addWidget(self._build_resize_page())
        self.parameter_stack.addWidget(self._build_volume_page())

        output_row = QHBoxLayout()
        output_label = QLabel("输出位置", card)
        output_label.setObjectName("SecondaryText")
        self.output_edit = QLineEdit(card)
        self.output_edit.setObjectName("PathInput")
        self.output_edit.setReadOnly(True)
        self.choose_output_button = QPushButton(card)
        self.choose_output_button.setObjectName("IconButton")
        self.choose_output_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self.choose_output_button.setToolTip("选择输出目录")
        self.choose_output_button.clicked.connect(self.choose_output_directory)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.choose_output_button)

        self.library_checkbox = QCheckBox("完成后加入项目素材库", card)
        self.library_checkbox.setChecked(False)
        self.library_checkbox.setEnabled(False)

        self.feedback = InlineMessage("", "info", card)
        self.feedback.setVisible(False)

        action_row = QHBoxLayout()
        self.task_hint = QLabel("尚未创建处理任务", card)
        self.task_hint.setObjectName("MetaText")
        self.start_button = QPushButton("开始处理", card)
        self.start_button.setProperty("role", "primary")
        self.start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.start_button.clicked.connect(self.start_processing)
        action_row.addWidget(self.task_hint)
        action_row.addStretch(1)
        action_row.addWidget(self.library_checkbox)
        action_row.addWidget(self.start_button)

        card_layout.addLayout(header)
        card_layout.addLayout(tool_row)
        card_layout.addLayout(input_row)
        card_layout.addWidget(self.parameter_stack)
        card_layout.addLayout(output_row)
        card_layout.addWidget(self.feedback)
        card_layout.addLayout(action_row)

        root_layout.addWidget(card)
        root_layout.addStretch(1)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.service.task_added.connect(self._handle_task_added)
        self.service.task_updated.connect(self._handle_task_updated)
        self.set_project(None)
        self._set_tool("format")

    def _build_format_page(self) -> QWidget:
        page = QWidget(self)
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("目标格式", page)
        label.setObjectName("SecondaryText")
        self.target_format_combo = QComboBox(page)
        self.target_format_combo.setObjectName("RangeSelector")
        for label_text, extension in TARGET_FORMATS:
            self.target_format_combo.addItem(label_text, extension)
        self.target_format_combo.setCurrentIndex(2)
        layout.addWidget(label)
        layout.addWidget(self.target_format_combo)
        layout.addStretch(1)
        return page

    def _build_trim_page(self) -> QWidget:
        page = QWidget(self)
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        start_label = QLabel("开始", page)
        start_label.setObjectName("SecondaryText")
        self.start_time_edit = QLineEdit(page)
        self.start_time_edit.setObjectName("PathInput")
        self.start_time_edit.setPlaceholderText("00:00")
        end_label = QLabel("结束", page)
        end_label.setObjectName("SecondaryText")
        self.end_time_edit = QLineEdit(page)
        self.end_time_edit.setObjectName("PathInput")
        self.end_time_edit.setPlaceholderText("00:10")
        layout.addWidget(start_label)
        layout.addWidget(self.start_time_edit)
        layout.addSpacing(10)
        layout.addWidget(end_label)
        layout.addWidget(self.end_time_edit)
        layout.addStretch(1)
        return page

    def _build_resize_page(self) -> QWidget:
        page = QWidget(self)
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        preset_label = QLabel("尺寸预设", page)
        preset_label.setObjectName("SecondaryText")
        self.resize_preset_combo = QComboBox(page)
        self.resize_preset_combo.setObjectName("RangeSelector")
        for label, width, height in RESIZE_PRESETS:
            self.resize_preset_combo.addItem(label, (width, height))
        self.resize_preset_combo.addItem("自定义", None)
        self.resize_preset_combo.currentIndexChanged.connect(
            self._apply_resize_preset
        )

        width_label = QLabel("宽", page)
        width_label.setObjectName("SecondaryText")
        self.width_spin = QSpinBox(page)
        self.width_spin.setRange(2, 7680)
        self.width_spin.setSingleStep(2)
        self.width_spin.setValue(1080)
        self.width_spin.valueChanged.connect(self._mark_custom_size)
        height_label = QLabel("高", page)
        height_label.setObjectName("SecondaryText")
        self.height_spin = QSpinBox(page)
        self.height_spin.setRange(2, 7680)
        self.height_spin.setSingleStep(2)
        self.height_spin.setValue(1920)
        self.height_spin.valueChanged.connect(self._mark_custom_size)

        layout.addWidget(preset_label)
        layout.addWidget(self.resize_preset_combo)
        layout.addSpacing(10)
        layout.addWidget(width_label)
        layout.addWidget(self.width_spin)
        layout.addWidget(height_label)
        layout.addWidget(self.height_spin)
        layout.addStretch(1)
        return page

    def _build_volume_page(self) -> QWidget:
        page = QWidget(self)
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("音量变化", page)
        label.setObjectName("SecondaryText")
        self.volume_spin = QDoubleSpinBox(page)
        self.volume_spin.setRange(-60.0, 60.0)
        self.volume_spin.setDecimals(1)
        self.volume_spin.setSingleStep(1.0)
        self.volume_spin.setValue(6.0)
        self.volume_spin.setSuffix(" dB")
        layout.addWidget(label)
        layout.addWidget(self.volume_spin)
        layout.addStretch(1)
        return page

    def _set_tool(self, tool_key: str) -> None:
        indexes = {"format": 0, "trim": 1, "resize": 2, "volume": 3}
        self._current_tool = tool_key
        self.parameter_stack.setCurrentIndex(indexes[tool_key])
        self.tool_buttons[tool_key].setChecked(True)
        self.task_hint.setText(f"当前工具：{TOOL_LABELS[tool_key]}")

    def _apply_resize_preset(self) -> None:
        values = self.resize_preset_combo.currentData()
        if values is None:
            return
        width, height = values
        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)

    def _mark_custom_size(self) -> None:
        self.resize_preset_combo.blockSignals(True)
        self.resize_preset_combo.setCurrentIndex(
            self.resize_preset_combo.count() - 1
        )
        self.resize_preset_combo.blockSignals(False)

    def set_project(self, project_root: str | Path | None) -> None:
        self._project_root = (
            Path(project_root).expanduser().resolve()
            if project_root is not None
            else None
        )
        if self._project_root is None:
            self.output_edit.setText(self._last_directory)
            self.choose_output_button.setEnabled(True)
            self.library_checkbox.setChecked(False)
            self.library_checkbox.setEnabled(False)
        else:
            self.output_edit.setText(str(self._project_root / "输出成品"))
            self.choose_output_button.setEnabled(False)
            self.library_checkbox.setChecked(True)
            self.library_checkbox.setEnabled(True)

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
            self.queue_summary.setText("工具队列为空")
        elif failed_count > 0:
            self.queue_summary.setText(
                f"共 {total_count} 个任务，进行中 {active_count}，失败 {failed_count}"
            )
        else:
            self.queue_summary.setText(
                f"共 {total_count} 个任务，进行中 {active_count}"
            )

    def choose_input_file(self) -> None:
        start_directory = self.input_edit.text().strip()
        if not Path(start_directory).is_file():
            start_directory = str(Path.home())
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择媒体文件",
            start_directory,
            MEDIA_FILE_FILTER,
        )
        if selected:
            self.input_edit.setText(selected)
            self.input_edit.setToolTip(selected)

    def choose_output_directory(self) -> None:
        if self._project_root is not None:
            return
        current = self.output_edit.text().strip()
        start_directory = current if Path(current).is_dir() else self._last_directory
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择媒体工具输出目录",
            start_directory,
        )
        if not selected:
            return
        self._last_directory = str(Path(selected).expanduser().resolve())
        self.output_edit.setText(self._last_directory)
        self.output_directory_changed.emit(self._last_directory)

    def start_processing(self) -> None:
        try:
            request = self._build_request()
            task = self.service.enqueue(
                request,
                add_to_library=self.library_checkbox.isChecked(),
                project_root=self._project_root,
            )
        except (MediaCommandError, ValueError, OSError) as error:
            self._show_feedback(str(error), "error")
            return

        self._current_task_id = task.task_id
        self._show_feedback("已加入媒体处理队列", "success")
        self._publish_task_context(task)

    def _build_request(self):
        source = self.input_edit.text().strip()
        if not source:
            raise MediaCommandError("请先选择输入文件")
        if not Path(source).is_file():
            raise MediaCommandError(f"输入文件不存在：{source}")
        output_directory = self.output_edit.text().strip()
        if not output_directory:
            raise MediaCommandError("请选择输出目录")

        if self._current_tool == "format":
            return conversion_request(
                source,
                output_directory,
                self.target_format_combo.currentData(),
            )
        if self._current_tool == "trim":
            return trim_request(
                source,
                output_directory,
                self.start_time_edit.text(),
                self.end_time_edit.text(),
            )
        if self._current_tool == "resize":
            return resize_request(
                source,
                output_directory,
                self.width_spin.value(),
                self.height_spin.value(),
            )
        return volume_request(
            source,
            output_directory,
            self.volume_spin.value(),
        )

    def _handle_task_added(self, task_id: str) -> None:
        self._current_task_id = task_id
        task = self.service.get_task(task_id)
        if task is not None:
            self._publish_task_context(task)

    def _handle_task_updated(self, task_id: str) -> None:
        if task_id != self._current_task_id:
            return
        task = self.service.get_task(task_id)
        if task is not None:
            self._publish_task_context(task)

    def _publish_task_context(self, task: MediaTask) -> None:
        status = TASK_STATUS_LABELS[task.status]
        if task.status == MediaTaskStatus.FAILED:
            detail = task.error or "FFmpeg 任务失败"
        elif task.status == MediaTaskStatus.CANCELED:
            detail = "任务已取消，未完成的输出文件已清理"
        elif task.status == MediaTaskStatus.COMPLETED:
            detail = task.output_path
            if task.library_error:
                detail = f"{detail}\n加入素材库失败：{task.library_error}"
        else:
            detail = f"输出：{task.output_path}"
        self.context_changed.emit(
            f"{task.title} · {status}",
            detail,
        )

    def publish_context(self) -> None:
        if self._current_task_id is None:
            self.context_changed.emit(
                "媒体工具",
                "选择工具、输入文件和参数后开始处理",
            )
            return
        task = self.service.get_task(self._current_task_id)
        if task is None:
            self.context_changed.emit(
                "媒体工具",
                "选择工具、输入文件和参数后开始处理",
            )
            return
        self._publish_task_context(task)

    def _show_feedback(
        self,
        message: str,
        kind: str,
        duration_ms: int = 4000,
    ) -> None:
        self.feedback.set_message(message, kind)
        self.message_requested.emit(message, kind, duration_ms)
