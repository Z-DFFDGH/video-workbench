from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from video_workbench.downloader.models import DownloadStatus, DownloadTask
from video_workbench.media_tools.models import MediaTask, MediaTaskStatus

STATUS_LABELS = {
    DownloadStatus.QUEUED: "等待",
    DownloadStatus.RUNNING: "进行中",
    DownloadStatus.COMPLETED: "完成",
    DownloadStatus.FAILED: "失败",
    DownloadStatus.CANCELED: "已取消",
}
ACTIVE_STATUSES = {DownloadStatus.QUEUED, DownloadStatus.RUNNING}


@dataclass(frozen=True, slots=True)
class TaskDrawerItem:
    task_id: str
    title: str
    detail: str
    status: str
    status_label: str
    cancelable: bool


MEDIA_STATUS_LABELS = {
    MediaTaskStatus.QUEUED: "等待",
    MediaTaskStatus.RUNNING: "进行中",
    MediaTaskStatus.COMPLETED: "完成",
    MediaTaskStatus.FAILED: "失败",
    MediaTaskStatus.CANCELED: "已取消",
}


def media_task_item(task: MediaTask) -> TaskDrawerItem:
    if task.status == MediaTaskStatus.FAILED:
        detail = task.error or "媒体处理失败"
    elif task.status == MediaTaskStatus.CANCELED:
        detail = "任务已取消，输出文件已清理"
    elif task.status == MediaTaskStatus.COMPLETED:
        detail = task.output_path
    else:
        detail = f"输出：{task.output_path}"
    return TaskDrawerItem(
        task_id=task.task_id,
        title=task.title,
        detail=detail,
        status=task.status.value,
        status_label=MEDIA_STATUS_LABELS[task.status],
        cancelable=task.status in {
            MediaTaskStatus.QUEUED,
            MediaTaskStatus.RUNNING,
        },
    )


def download_task_item(task: DownloadTask) -> TaskDrawerItem:
    if task.status == DownloadStatus.FAILED:
        detail = task.error or "下载失败"
    elif task.status == DownloadStatus.CANCELED:
        detail = "任务已取消"
    elif task.status == DownloadStatus.COMPLETED:
        detail = task.output_path or "已完成"
    else:
        detail = task.output_directory
    return TaskDrawerItem(
        task_id=task.task_id,
        title=task.source_url,
        detail=detail,
        status=task.status.value,
        status_label=STATUS_LABELS[task.status],
        cancelable=task.status in ACTIVE_STATUSES,
    )


class TaskRow(QFrame):
    def __init__(self, task: TaskDrawerItem, cancel_callback, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TaskRow")
        self.task = task

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 8, 7)
        layout.setSpacing(8)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        self.title_label = QLabel(task.title, self)
        self.title_label.setObjectName("TaskTitle")
        self.title_label.setToolTip(task.title)
        self.detail_label = QLabel(task.detail, self)
        self.detail_label.setObjectName("TaskDetail")
        self.detail_label.setToolTip(task.detail)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.detail_label)

        self.status_label = QLabel(task.status_label, self)
        self.status_label.setObjectName("StatusPill")
        self.status_label.setProperty("status", task.status)

        self.cancel_button = QPushButton(self)
        self.cancel_button.setObjectName("TaskCancelButton")
        self.cancel_button.setIcon(
            self.style().standardIcon(
                self.style().StandardPixmap.SP_BrowserStop
            )
        )
        self.cancel_button.setToolTip("取消任务")
        self.cancel_button.setEnabled(task.cancelable)
        self.cancel_button.clicked.connect(
            lambda: cancel_callback(task.task_id)
        )

        layout.addLayout(text_layout, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.cancel_button)


class TaskDrawer(QFrame):
    expanded_changed = Signal(bool)

    COLLAPSED_HEIGHT = 46
    EXPANDED_HEIGHT = 220

    def __init__(self, animations_enabled: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassTaskDrawer")
        self._animations_enabled = animations_enabled
        self._expanded = False
        self._rows: list[TaskRow] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 6, 12, 6)
        root_layout.setSpacing(4)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.toggle_button = QToolButton(header)
        self.toggle_button.setObjectName("DrawerToggle")
        self.toggle_button.setText("任务")
        self.toggle_button.setToolTip("展开任务列表")
        self.toggle_button.clicked.connect(self.toggle)

        self.summary_label = QLabel("暂无任务", header)
        self.summary_label.setObjectName("SecondaryText")

        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(self.summary_label)
        header_layout.addStretch(1)

        self.content = QWidget(self)
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(4, 2, 4, 4)
        content_layout.setSpacing(5)

        self.rows_container = QWidget(self.content)
        self.rows_container.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
        )
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(5)
        self.rows_layout.addStretch(1)

        self.scroll_area = QScrollArea(self.content)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.viewport().setAutoFillBackground(False)
        self.scroll_area.setStyleSheet("background: transparent; border: 0;")
        self.scroll_area.setWidget(self.rows_container)

        content_layout.addWidget(self.scroll_area)

        root_layout.addWidget(header)
        root_layout.addWidget(self.content)

        self._height_animation = QPropertyAnimation(self, b"maximumHeight", self)
        self._height_animation.setDuration(180)
        self._height_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._height_animation.finished.connect(self._finish_height_animation)
        self.set_expanded(False, animate=False)

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        if expanded == self._expanded and self.maximumHeight() in {
            self.COLLAPSED_HEIGHT,
            self.EXPANDED_HEIGHT,
        }:
            self.content.setVisible(expanded)
            return

        self._expanded = expanded
        target_height = self.EXPANDED_HEIGHT if expanded else self.COLLAPSED_HEIGHT
        self.toggle_button.setToolTip("收起任务列表" if expanded else "展开任务列表")

        if animate and self._animations_enabled:
            self._height_animation.stop()
            self._height_animation.setStartValue(self.maximumHeight())
            self._height_animation.setEndValue(target_height)
            self._height_animation.start()
        else:
            self.setMinimumHeight(target_height)
            self.setMaximumHeight(target_height)
            self.content.setVisible(expanded)

        self.expanded_changed.emit(expanded)

    def set_tasks(
        self,
        tasks: Iterable[DownloadTask],
        cancel_callback: Callable[[str], bool] | None = None,
    ) -> None:
        self.set_items(
            [download_task_item(task) for task in tasks],
            cancel_callback,
        )

    def set_items(
        self,
        tasks: Iterable[TaskDrawerItem],
        cancel_callback: Callable[[str], bool] | None = None,
    ) -> None:
        task_list = list(tasks)
        for row in self._rows:
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        cancel = cancel_callback or (lambda _task_id: False)
        for task in task_list:
            row = TaskRow(task, cancel, self.rows_container)
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
            self._rows.append(row)

        self.scroll_area.setVisible(bool(task_list))

    def set_summary(self, active_count: int, failed_count: int = 0) -> None:
        if active_count <= 0 and failed_count <= 0:
            self.summary_label.setText("暂无任务")
        elif failed_count > 0:
            self.summary_label.setText(f"进行中 {active_count}，失败 {failed_count}")
        else:
            self.summary_label.setText(f"进行中 {active_count}")

    def _finish_height_animation(self) -> None:
        target_height = (
            self.EXPANDED_HEIGHT if self._expanded else self.COLLAPSED_HEIGHT
        )
        self.setMinimumHeight(target_height)
        self.setMaximumHeight(target_height)
        self.content.setVisible(self._expanded)
