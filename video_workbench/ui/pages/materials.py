from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QListView,
    QPushButton,
    QSplitter,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from video_workbench.materials import (
    MaterialImportError,
    MaterialLibrary,
    MaterialRecord,
    MaterialRepositoryError,
    MaterialStatus,
    MediaType,
)
from video_workbench.ui.components.dialogs import confirm
from video_workbench.ui.components.messages import InlineMessage

MATERIAL_FILE_FILTER = (
    "媒体素材 (*.mp4 *.mov *.mkv *.webm *.avi *.mp3 *.wav *.aac *.flac "
    "*.png *.jpg *.jpeg *.bmp *.webp *.gif);;所有文件 (*.*)"
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


def format_size(size_bytes: int) -> str:
    size = max(0, int(size_bytes))
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "-"
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes:02d}:{remaining_seconds:02d}"


def media_type_label(media_type: MediaType) -> str:
    return {
        MediaType.VIDEO: "视频",
        MediaType.AUDIO: "音频",
        MediaType.IMAGE: "图片",
        MediaType.UNKNOWN: "未知",
    }[media_type]


class MaterialDropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MaterialDropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(92)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        self.title_label = QLabel("拖拽视频、音频或图片到这里", self)
        self.title_label.setObjectName("CardTitle")
        self.hint_label = QLabel("默认只登记文件路径，不复制原文件", self)
        self.hint_label.setObjectName("MetaText")
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.hint_label)
        layout.addLayout(text_layout)
        layout.addStretch(1)

        self.choose_button = QPushButton("选择素材", self)
        self.choose_button.setProperty("role", "primary")
        self.choose_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        layout.addWidget(self.choose_button)

        # Drag events target the child under the pointer, so forward them to
        # this drop zone from every child to keep the whole card interactive.
        for widget in (self.title_label, self.hint_label, self.choose_button):
            widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if watched in {self.title_label, self.hint_label, self.choose_button}:
            if event.type() == QEvent.Type.DragEnter:
                self.dragEnterEvent(event)
                return event.isAccepted()
            if event.type() == QEvent.Type.DragMove:
                self.dragMoveEvent(event)
                return event.isAccepted()
            if event.type() == QEvent.Type.DragLeave:
                self._set_drag_active(False)
                return False
            if event.type() == QEvent.Type.Drop:
                self.dropEvent(event)
                return event.isAccepted()
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_drag_active(True)
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        self._set_drag_active(False)
        paths = local_file_paths(event.mimeData().urls())
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.files_dropped.emit(paths)

    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        style = self.style()
        style.unpolish(self)
        style.polish(self)


def local_file_paths(urls: Iterable[object]) -> list[str]:
    paths: list[str] = []
    for url in urls:
        if not hasattr(url, "isLocalFile") or not url.isLocalFile():
            continue
        path = Path(url.toLocalFile()).expanduser()
        if path.is_file():
            paths.append(str(path.resolve()))
    return paths


class MaterialLibraryPage(QWidget):
    message_requested = Signal(str, str, int)
    context_changed = Signal(str, str)

    def __init__(
        self,
        parent=None,
        library_factory: Callable[[Path], MaterialLibrary] | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_root: Path | None = None
        self._library: MaterialLibrary | None = None
        self._library_factory = library_factory or MaterialLibrary
        self._selected_id: str | None = None
        self._preview_processes: list[subprocess.Popen] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.search_row = QHBoxLayout()
        self.search_row.setContentsMargins(0, 0, 0, 0)
        self.search_row.setSpacing(8)
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("按名称或标签检索")
        self.search_input.setClearButtonEnabled(True)
        self.result_label = QLabel("尚未打开项目", self)
        self.result_label.setObjectName("MetaText")

        self.list_view_button = self._view_button(
            "列表",
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
        )
        self.thumbnail_view_button = self._view_button(
            "缩略图",
            QStyle.StandardPixmap.SP_FileDialogListView,
        )
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        self.view_group.addButton(self.list_view_button)
        self.view_group.addButton(self.thumbnail_view_button)
        self.list_view_button.setChecked(True)

        self.copy_checkbox = QCheckBox("复制到项目文件夹", self)
        self.copy_checkbox.setChecked(False)

        self.search_row.addWidget(self.search_input, 1)
        self.search_row.addWidget(self.result_label)
        self.search_row.addSpacing(8)
        self.search_row.addWidget(self.list_view_button)
        self.search_row.addWidget(self.thumbnail_view_button)
        self.search_row.addSpacing(8)
        self.search_row.addWidget(self.copy_checkbox)

        self.drop_zone = MaterialDropZone(self)
        self.drop_zone.choose_button.clicked.connect(self.prompt_import_files)
        self.drop_zone.files_dropped.connect(self.import_paths)
        self.message = InlineMessage("", "info", self)
        self.message.setVisible(False)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        list_frame = QFrame(splitter)
        list_frame.setObjectName("DashboardCard")
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(8)
        list_title = QLabel("项目素材", list_frame)
        list_title.setObjectName("CardTitle")
        self.material_list = QListWidget(list_frame)
        self.material_list.setObjectName("MaterialList")
        self.material_list.viewport().setObjectName("MaterialListViewport")
        self.material_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.material_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.material_list.setMovement(QListView.Movement.Static)
        self.material_list.setWordWrap(True)
        self.material_list.itemSelectionChanged.connect(self._update_selected_detail)
        self.material_list.itemDoubleClicked.connect(lambda _: self.preview_selected())
        list_layout.addWidget(list_title)
        list_layout.addWidget(self.material_list, 1)

        detail_frame = QFrame(splitter)
        detail_frame.setObjectName("DashboardCard")
        detail_frame.setMinimumWidth(300)
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(8)

        self.preview_label = QLabel("选择素材后查看详情", detail_frame)
        self.preview_label.setObjectName("MaterialPreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(280, 170)
        self.preview_label.setMaximumHeight(240)

        self.detail_name = QLabel("未选择素材", detail_frame)
        self.detail_name.setObjectName("CardTitle")
        self.detail_name.setWordWrap(True)
        self.detail_meta = QLabel("-", detail_frame)
        self.detail_meta.setObjectName("SecondaryText")
        self.detail_meta.setWordWrap(True)
        self.detail_path = QLabel("-", detail_frame)
        self.detail_path.setObjectName("MetaText")
        self.detail_path.setWordWrap(True)
        self.detail_error = QLabel("", detail_frame)
        self.detail_error.setObjectName("InlineMessageText")
        self.detail_error.setWordWrap(True)
        self.detail_error.setVisible(False)

        tag_title = QLabel("标签", detail_frame)
        tag_title.setObjectName("CardTitle")
        self.tag_list = QListWidget(detail_frame)
        self.tag_list.setObjectName("TagList")
        self.tag_list.viewport().setObjectName("TagListViewport")
        self.tag_list.setMaximumHeight(86)
        tag_row = QHBoxLayout()
        self.tag_input = QLineEdit(detail_frame)
        self.tag_input.setObjectName("SearchInput")
        self.tag_input.setPlaceholderText("输入标签")
        self.add_tag_button = QPushButton("添加", detail_frame)
        self.remove_tag_button = QPushButton("删除标签", detail_frame)
        tag_row.addWidget(self.tag_input, 1)
        tag_row.addWidget(self.add_tag_button)
        tag_row.addWidget(self.remove_tag_button)

        action_row = QHBoxLayout()
        self.preview_button = QPushButton("预览媒体", detail_frame)
        self.preview_button.setProperty("role", "primary")
        self.remove_button = QPushButton("移除记录", detail_frame)
        self.remove_button.setProperty("role", "danger")
        action_row.addWidget(self.preview_button)
        action_row.addStretch(1)
        action_row.addWidget(self.remove_button)

        detail_layout.addWidget(self.preview_label)
        detail_layout.addWidget(self.detail_name)
        detail_layout.addWidget(self.detail_meta)
        detail_layout.addWidget(self.detail_path)
        detail_layout.addWidget(self.detail_error)
        detail_layout.addWidget(tag_title)
        detail_layout.addWidget(self.tag_list)
        detail_layout.addLayout(tag_row)
        detail_layout.addStretch(1)
        detail_layout.addLayout(action_row)

        splitter.addWidget(list_frame)
        splitter.addWidget(detail_frame)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([760, 360])

        layout.addLayout(self.search_row)
        layout.addWidget(self.drop_zone)
        layout.addWidget(self.message)
        layout.addWidget(splitter, 1)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.perform_search)
        self.search_input.textChanged.connect(self._schedule_search)
        self.list_view_button.clicked.connect(lambda: self.set_view_mode("list"))
        self.thumbnail_view_button.clicked.connect(
            lambda: self.set_view_mode("thumbnails")
        )
        self.add_tag_button.clicked.connect(self.add_tag)
        self.remove_tag_button.clicked.connect(self.remove_tag)
        self.tag_input.returnPressed.connect(self.add_tag)
        self.preview_button.clicked.connect(self.preview_selected)
        self.remove_button.clicked.connect(self.remove_selected)
        self.set_project(None)

    def _view_button(
        self,
        text: str,
        icon: QStyle.StandardPixmap,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("ViewModeButton")
        button.setText(text)
        button.setIcon(self.style().standardIcon(icon))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setCheckable(True)
        return button

    @property
    def current_record(self) -> MaterialRecord | None:
        if self._library is None or self._selected_id is None:
            return None
        try:
            return self._library.get_material(self._selected_id)
        except Exception:
            return None

    def set_project(self, project_root: str | Path | None) -> None:
        self._project_root = (
            Path(project_root).expanduser().resolve()
            if project_root is not None
            else None
        )
        self._library = None
        self._selected_id = None
        self.search_input.clear()
        self.message.set_message("", "info")
        if self._project_root is None:
            self.material_list.clear()
            self.result_label.setText("尚未打开项目")
            self.drop_zone.setEnabled(True)
            self.message.set_message(
                "请先从顶部“项目 > 打开项目”选择项目文件夹",
                "info",
            )
            self._set_detail(None)
            self._update_action_state()
            return

        try:
            self._library = self._library_factory(self._project_root)
        except Exception as error:
            self._show_feedback(f"无法读取素材库：{error}", "error")
            self.material_list.clear()
            self.result_label.setText("素材库不可用")
            self.drop_zone.setEnabled(False)
            self._update_action_state()
            return

        self.drop_zone.setEnabled(True)
        self.set_view_mode("list")
        self.refresh_results()

    def prompt_import_files(self) -> None:
        if self._project_root is None:
            self._show_feedback("请先打开项目，再入库素材", "warning")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要入库的素材",
            str(self._project_root),
            MATERIAL_FILE_FILTER,
        )
        if paths:
            self.import_paths(paths)

    def import_paths(self, paths: Iterable[str | Path]) -> int:
        if self._library is None:
            self._show_feedback("请先打开项目，再入库素材", "warning")
            return 0

        valid_paths: list[Path] = []
        rejected: list[Path] = []
        for value in paths:
            path = Path(value).expanduser()
            if path.is_file():
                valid_paths.append(path.resolve())
            else:
                rejected.append(path)
        if not valid_paths:
            self._show_feedback("没有可入库的本地文件", "warning")
            return 0

        imported = 0
        failed = 0
        last_error = ""
        for path in valid_paths:
            try:
                record = self._library.import_file(
                    path,
                    copy_to_project=self.copy_checkbox.isChecked(),
                    generate_thumbnail=True,
                )
            except (MaterialImportError, MaterialRepositoryError) as error:
                failed += 1
                last_error = str(error)
                continue
            imported += 1
            if record.status == MaterialStatus.ERROR:
                failed += 1
                last_error = record.error or "无法识别媒体格式"
            self._selected_id = record.material_id

        self.refresh_results()
        parts = [f"已处理 {imported} 个文件"]
        if failed:
            parts.append(f"{failed} 个无法识别")
        if rejected:
            parts.append(f"{len(rejected)} 个文件或文件夹不存在")
        if last_error:
            parts.append(last_error[:160])
        kind = "warning" if failed or rejected else "success"
        self._show_feedback("；".join(parts), kind)
        return imported

    def perform_search(self) -> None:
        self.refresh_results()

    def _schedule_search(self) -> None:
        self._search_timer.start()

    def set_view_mode(self, mode: str) -> None:
        if mode == "thumbnails":
            self.thumbnail_view_button.setChecked(True)
            self.material_list.setViewMode(QListView.ViewMode.IconMode)
            self.material_list.setIconSize(QSize(156, 88))
            self.material_list.setGridSize(QSize(190, 150))
            self.material_list.setSpacing(7)
        else:
            self.list_view_button.setChecked(True)
            self.material_list.setViewMode(QListView.ViewMode.ListMode)
            self.material_list.setIconSize(QSize(96, 54))
            self.material_list.setGridSize(QSize())
            self.material_list.setSpacing(2)

    def refresh_results(self) -> None:
        if self._library is None:
            self.material_list.clear()
            return

        selected_id = self._selected_id
        query = self.search_input.text()
        records = self._library.search(query)
        self.material_list.clear()
        for record in records:
            item = QListWidgetItem(self._material_icon(record), record.name)
            item.setData(Qt.ItemDataRole.UserRole, record.material_id)
            item.setToolTip(f"{record.name}\n{record.path}")
            self.material_list.addItem(item)

        if query.strip():
            self.result_label.setText(f"找到 {len(records)} 个素材")
        else:
            self.result_label.setText(f"共 {len(records)} 个素材")

        if selected_id is not None:
            self._select_material(selected_id)
        if self.material_list.currentItem() is None:
            self._selected_id = None
            self._set_detail(None)
        self._update_action_state()

    def _select_material(self, material_id: str) -> None:
        for index in range(self.material_list.count()):
            item = self.material_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == material_id:
                self.material_list.setCurrentItem(item)
                return

    def _update_selected_detail(self) -> None:
        item = self.material_list.currentItem()
        if item is None:
            self._selected_id = None
            self._set_detail(None)
            self._update_action_state()
            return
        self._selected_id = str(item.data(Qt.ItemDataRole.UserRole))
        self._set_detail(self.current_record)
        self._update_action_state()

    def _set_detail(self, record: MaterialRecord | None) -> None:
        if record is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("选择素材后查看详情")
            self.detail_name.setText("未选择素材")
            self.detail_meta.setText("-")
            self.detail_path.setText("-")
            self.detail_error.clear()
            self.detail_error.setVisible(False)
            self.tag_list.clear()
            self.tag_input.clear()
            self.context_changed.emit("素材详情", "选择素材后查看标签和预览")
            return

        self.detail_name.setText(record.name)
        status = "可用" if record.status == MaterialStatus.READY else "无法识别"
        metadata = [
            media_type_label(record.media_type),
            status,
            format_size(record.size_bytes),
        ]
        if record.duration_seconds is not None:
            metadata.append(format_duration(record.duration_seconds))
        if record.width and record.height:
            metadata.append(f"{record.width}x{record.height}")
        if record.codec:
            metadata.append(record.codec)
        self.detail_meta.setText(" · ".join(metadata))
        self.detail_path.setText(record.path)
        self.detail_path.setToolTip(record.path)
        self.detail_error.setText(record.error or "")
        self.detail_error.setVisible(bool(record.error))

        self.tag_list.clear()
        for tag in record.tags:
            self.tag_list.addItem(tag)
        self._set_detail_preview(record)
        context_message = "\n".join(
            [
                " · ".join(metadata),
                f"标签：{'、'.join(record.tags) if record.tags else '无'}",
                record.path,
                record.error or "",
            ]
        ).strip()
        self.context_changed.emit(record.name, context_message)

    def _set_detail_preview(self, record: MaterialRecord) -> None:
        pixmap = self._preview_pixmap(record)
        if pixmap.isNull():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("预览不可用")
            return
        self.preview_label.setText("")
        self.preview_label.setPixmap(
            pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _preview_pixmap(self, record: MaterialRecord) -> QPixmap:
        if record.media_type == MediaType.IMAGE:
            return QPixmap(record.path)
        if record.media_type == MediaType.VIDEO and record.thumbnail_path:
            return QPixmap(record.thumbnail_path)
        return self.style().standardIcon(
            self._material_icon_type(record)
        ).pixmap(QSize(220, 140))

    def _material_icon(self, record: MaterialRecord) -> QIcon:
        pixmap = QPixmap()
        if record.media_type == MediaType.IMAGE:
            pixmap = QPixmap(record.path)
        elif record.media_type == MediaType.VIDEO and record.thumbnail_path:
            pixmap = QPixmap(record.thumbnail_path)
        if pixmap.isNull():
            return self.style().standardIcon(self._material_icon_type(record))
        return QIcon(
            pixmap.scaled(
                self.material_list.iconSize(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _material_icon_type(self, record: MaterialRecord) -> QStyle.StandardPixmap:
        if record.media_type == MediaType.VIDEO:
            return QStyle.StandardPixmap.SP_MediaPlay
        if record.media_type == MediaType.AUDIO:
            return QStyle.StandardPixmap.SP_MediaVolume
        if record.media_type == MediaType.IMAGE:
            return QStyle.StandardPixmap.SP_FileDialogContentsView
        return QStyle.StandardPixmap.SP_MessageBoxWarning

    def add_tag(self) -> None:
        record = self.current_record
        if record is None or self._library is None:
            self._show_feedback("请先选择素材", "warning")
            return
        tag = self.tag_input.text().strip()
        if not tag:
            self._show_feedback("标签不能为空", "warning")
            return
        try:
            self._library.add_tag(record.material_id, tag)
        except (OSError, ValueError, MaterialRepositoryError) as error:
            self._show_feedback(str(error), "error")
            return
        self.tag_input.clear()
        self.refresh_results()
        self._show_feedback("标签已添加", "success")

    def remove_tag(self) -> None:
        record = self.current_record
        if record is None or self._library is None:
            self._show_feedback("请先选择素材", "warning")
            return
        tag_item = self.tag_list.currentItem()
        tag = tag_item.text() if tag_item is not None else self.tag_input.text().strip()
        if not tag:
            self._show_feedback("请选择或输入要删除的标签", "warning")
            return
        try:
            self._library.remove_tag(record.material_id, tag)
        except (OSError, ValueError, MaterialRepositoryError) as error:
            self._show_feedback(str(error), "error")
            return
        self.tag_input.clear()
        self.refresh_results()
        self._show_feedback("标签已删除", "success")

    def preview_selected(self) -> None:
        record = self.current_record
        if record is None:
            self._show_feedback("请先选择素材", "warning")
            return
        if not Path(record.path).is_file():
            self._show_feedback(f"素材文件不存在：{record.path}", "error")
            return
        if record.media_type == MediaType.IMAGE:
            self._open_image_preview(record)
            return
        if record.media_type in {MediaType.VIDEO, MediaType.AUDIO}:
            self._launch_ffplay(record)
            return
        self._show_feedback("该素材无法预览", "warning")

    def _open_image_preview(self, record: MaterialRecord) -> None:
        pixmap = QPixmap(record.path)
        if pixmap.isNull():
            self._show_feedback("图片加载失败，无法预览", "error")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"图片预览 - {record.name}")
        dialog.resize(
            min(max(pixmap.width(), 480), 1280),
            min(max(pixmap.height(), 320), 820),
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        label = QLabel(dialog)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setPixmap(
            pixmap.scaled(
                dialog.size() - QSize(28, 28),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        layout.addWidget(label)
        dialog.exec()

    def _launch_ffplay(self, record: MaterialRecord) -> None:
        command = [
            "ffplay",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-autoexit",
            "-window_title",
            record.name,
            record.path,
        ]
        try:
            process = subprocess.Popen(command)
        except FileNotFoundError:
            self._show_feedback(
                "找不到 FFplay，请确认 FFmpeg 的 bin 目录已加入 PATH",
                "error",
            )
            return
        except OSError as error:
            self._show_feedback(f"无法启动 FFplay：{error}", "error")
            return
        self._preview_processes = [
            item for item in self._preview_processes if item.poll() is None
        ]
        self._preview_processes.append(process)
        self._show_feedback("已打开独立预览窗口", "success")

    def remove_selected(self) -> None:
        record = self.current_record
        if record is None or self._library is None:
            self._show_feedback("请先选择素材", "warning")
            return
        if not confirm(
            self,
            "移除素材记录",
            f"从素材库移除“{record.name}”？\n磁盘文件不会被删除。",
            confirm_text="移除记录",
            destructive=True,
        ):
            return

        try:
            removed = self._library.remove_material(record.material_id)
        except (OSError, MaterialRepositoryError) as error:
            self._show_feedback(f"移除素材记录失败：{error}", "error")
            return
        if not removed:
            self._show_feedback("素材记录不存在或已移除", "warning")
            return
        self._selected_id = None
        self.refresh_results()
        self._show_feedback(
            "已从素材库移除记录，磁盘文件没有删除",
            "success",
            5000,
        )

    def publish_context(self) -> None:
        if self.current_record is None:
            self.context_changed.emit("素材详情", "选择素材后查看标签和预览")
            return
        self._set_detail(self.current_record)

    def _update_action_state(self) -> None:
        has_record = self.current_record is not None
        has_project = self._library is not None
        self.search_input.setEnabled(has_project)
        self.copy_checkbox.setEnabled(has_project)
        self.list_view_button.setEnabled(has_project)
        self.thumbnail_view_button.setEnabled(has_project)
        self.add_tag_button.setEnabled(has_record)
        self.remove_tag_button.setEnabled(has_record)
        self.tag_input.setEnabled(has_record)
        self.preview_button.setEnabled(has_record)
        self.remove_button.setEnabled(has_record)

    def _show_feedback(
        self,
        message: str,
        kind: str,
        duration_ms: int = 4000,
    ) -> None:
        self.message.set_message(message, kind)
        self.message_requested.emit(message, kind, duration_ms)
