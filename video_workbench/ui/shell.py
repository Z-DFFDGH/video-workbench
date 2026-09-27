from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from video_workbench.ui.components import DashboardHome, PageHeader, ToastHost
from video_workbench.ui.components.task_drawer import TaskDrawer
from video_workbench.ui.components.wallpaper import WallpaperBackground
from video_workbench.ui.components.window_controls import WindowControls
from video_workbench.ui.pages.download import DownloadPage
from video_workbench.ui.pages.materials import MaterialLibraryPage
from video_workbench.ui.pages.notes import NotesPage
from video_workbench.ui.pages.scripts import ScriptEditorPage
from video_workbench.ui.pages.sensitive import SensitiveWordsPage
from video_workbench.ui.pages.tools import MediaToolsPage


@dataclass(frozen=True, slots=True)
class NavigationItem:
    key: str
    label: str
    title: str
    description: str
    empty_title: str
    icon: QStyle.StandardPixmap


NAVIGATION_ITEMS = (
    NavigationItem(
        "project",
        "当前项目",
        "当前项目",
        "本地项目目录与当前状态",
        "尚未打开项目",
        QStyle.StandardPixmap.SP_ComputerIcon,
    ),
    NavigationItem(
        "download",
        "素材下载",
        "素材下载",
        "链接下载与任务队列",
        "暂无下载任务",
        QStyle.StandardPixmap.SP_ArrowDown,
    ),
    NavigationItem(
        "scripts",
        "脚本文档",
        "脚本文档",
        "纯文本与 Markdown 脚本",
        "还没有脚本",
        QStyle.StandardPixmap.SP_FileIcon,
    ),
    NavigationItem(
        "materials",
        "素材库",
        "素材库",
        "项目素材、标签与检索",
        "素材库为空",
        QStyle.StandardPixmap.SP_DirIcon,
    ),
    NavigationItem(
        "tools",
        "媒体工具箱",
        "媒体工具箱",
        "格式转换、裁剪与基础参数处理",
        "请选择处理工具",
        QStyle.StandardPixmap.SP_FileDialogDetailedView,
    ),
    NavigationItem(
        "notes",
        "项目笔记",
        "项目笔记",
        "项目选题与创作备注",
        "还没有项目笔记",
        QStyle.StandardPixmap.SP_FileDialogInfoView,
    ),
    NavigationItem(
        "sensitive",
        "敏感词检查",
        "敏感词检查",
        "本地词库字符串检查",
        "没有检查结果",
        QStyle.StandardPixmap.SP_MessageBoxWarning,
    ),
)


class Sidebar(QFrame):
    selected_changed = Signal(str)

    EXPANDED_WIDTH = 224
    COLLAPSED_WIDTH = 72

    def __init__(self, animations_enabled: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassSidebar")
        self._animations_enabled = animations_enabled
        self._collapsed = False
        self._buttons: dict[str, QToolButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(5)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        for item in NAVIGATION_ITEMS:
            button = QToolButton(self)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setText(item.label)
            button.setIcon(self.style().standardIcon(item.icon))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setToolTip(item.label)
            button.clicked.connect(
                lambda checked=False, key=item.key: self.selected_changed.emit(key)
            )
            self.button_group.addButton(button)
            self._buttons[item.key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        self.path_label = QLabel("未打开项目", self)
        self.path_label.setObjectName("MetaText")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        self._width_animation = QPropertyAnimation(self, b"maximumWidth", self)
        self._width_animation.setDuration(160)
        self._width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._width_animation.finished.connect(self._finish_width_animation)
        self.set_collapsed(False, animate=False)

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def selected_key(self) -> str | None:
        for key, button in self._buttons.items():
            if button.isChecked():
                return key
        return None

    def select(self, key: str) -> None:
        button = self._buttons[key]
        button.setChecked(True)
        self.selected_changed.emit(key)

    def set_collapsed(self, collapsed: bool, animate: bool = True) -> None:
        self._collapsed = collapsed
        target_width = self.COLLAPSED_WIDTH if collapsed else self.EXPANDED_WIDTH
        style = (
            Qt.ToolButtonStyle.ToolButtonIconOnly
            if collapsed
            else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        for button in self._buttons.values():
            button.setToolButtonStyle(style)
        self.path_label.setVisible(not collapsed)

        if animate and self._animations_enabled:
            self._width_animation.stop()
            self._width_animation.setStartValue(self.maximumWidth())
            self._width_animation.setEndValue(target_width)
            self._width_animation.start()
        else:
            self.setMinimumWidth(target_width)
            self.setMaximumWidth(target_width)

    def _finish_width_animation(self) -> None:
        target_width = self.COLLAPSED_WIDTH if self._collapsed else self.EXPANDED_WIDTH
        self.setMinimumWidth(target_width)
        self.setMaximumWidth(target_width)


class TopBar(QFrame):
    toggle_sidebar_requested = Signal()
    appearance_requested = Signal()
    tasks_requested = Signal()
    new_project_requested = Signal()
    open_project_requested = Signal()
    recent_project_requested = Signal(str)
    rename_project_requested = Signal()
    delete_project_requested = Signal()
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassTopBar")
        self.setFixedHeight(56)
        self._drag_offset = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.sidebar_button = self._icon_button(
            "切换侧栏",
            QStyle.StandardPixmap.SP_TitleBarUnshadeButton,
        )
        self.sidebar_button.clicked.connect(self.toggle_sidebar_requested)

        self.app_title = QLabel("剪辑工作台", self)
        self.app_title.setObjectName("AppTitle")
        self.project_title = QLabel("未打开项目", self)
        self.project_title.setObjectName("ProjectTitle")

        self.tasks_button = QPushButton("任务", self)
        self.tasks_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self.tasks_button.setToolTip("展开任务列表")
        self.tasks_button.clicked.connect(self.tasks_requested)

        self.appearance_button = QPushButton("外观", self)
        self.appearance_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self.appearance_button.setToolTip("更换壁纸")
        self.appearance_button.clicked.connect(self.appearance_requested)

        self.project_menu_button = QPushButton("项目", self)
        self.project_menu_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        )
        self.project_menu = self._create_project_menu()
        self.project_menu_button.setMenu(self.project_menu)

        self.window_controls = WindowControls(self)
        self.window_controls.minimize_requested.connect(self.minimize_requested)
        self.window_controls.maximize_requested.connect(self.maximize_requested)
        self.window_controls.close_requested.connect(self.close_requested)

        layout.addWidget(self.sidebar_button)
        layout.addWidget(self.app_title)
        layout.addWidget(self.project_title)
        layout.addStretch(1)
        layout.addWidget(self.tasks_button)
        layout.addWidget(self.appearance_button)
        layout.addWidget(self.project_menu_button)
        layout.addWidget(self.window_controls)

    def set_project(self, name: str | None, path: str | None = None) -> None:
        self.project_title.setText(name or "未打开项目")
        self.project_title.setToolTip(path or "")
        self.set_project_actions(bool(name))

    def set_project_actions(self, has_project: bool) -> None:
        self.open_project_action.setEnabled(True)
        self.rename_project_action.setEnabled(has_project)
        self.delete_project_action.setEnabled(has_project)
        self.rename_project_action.setStatusTip(
            "修改当前项目的显示名称"
            if has_project
            else "请先打开项目"
        )
        self.delete_project_action.setStatusTip(
            "将当前项目移入 Windows 回收站"
            if has_project
            else "请先打开项目"
        )

    def set_recent_projects(self, projects: list[tuple[str, str]]) -> None:
        self.recent_projects_menu.clear()
        if not projects:
            empty_action = self.recent_projects_menu.addAction("暂无最近项目")
            empty_action.setEnabled(False)
            return

        for name, path in projects:
            action = self.recent_projects_menu.addAction(name)
            action.setToolTip(path)
            action.triggered.connect(
                lambda checked=False, project_path=path: (
                    self.recent_project_requested.emit(project_path)
                )
            )

    def _icon_button(
        self,
        tooltip: str,
        icon: QStyle.StandardPixmap,
    ) -> QPushButton:
        button = QPushButton(self)
        button.setObjectName("WindowControl")
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        return button

    def _create_project_menu(self) -> QMenu:
        menu = QMenu(self)
        self.new_project_action = QAction("新建项目...", menu)
        self.open_project_action = QAction("打开项目...", menu)
        self.rename_project_action = QAction("重命名项目...", menu)
        self.delete_project_action = QAction("删除项目...", menu)
        self.exit_action = QAction("退出", menu)

        self.new_project_action.triggered.connect(self.new_project_requested)
        self.open_project_action.triggered.connect(self.open_project_requested)
        self.open_project_action.setStatusTip("选择已有项目文件夹")
        self.rename_project_action.triggered.connect(self.rename_project_requested)
        self.delete_project_action.triggered.connect(self.delete_project_requested)
        self.recent_projects_menu = QMenu("最近打开", menu)
        self.set_project_actions(False)

        menu.addAction(self.new_project_action)
        menu.addAction(self.open_project_action)
        menu.addMenu(self.recent_projects_menu)
        menu.addSeparator()
        menu.addAction(self.rename_project_action)
        menu.addAction(self.delete_project_action)
        menu.addSeparator()
        menu.addAction(self.exit_action)
        return menu

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            self._drag_offset = (
                event.globalPosition().toPoint() - window.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            window = self.window()
            if not window.isMaximized():
                window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class ContextPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("GlassContext")
        self.setMinimumWidth(260)
        self.setMaximumWidth(296)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.title_label = QLabel("详情", self)
        self.title_label.setObjectName("SectionTitle")
        self.message_label = QLabel("选择一项内容查看详情", self)
        self.message_label.setObjectName("ContextHint")
        self.message_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        layout.addStretch(1)

    def set_context(self, title: str, message: str) -> None:
        self.title_label.setText(title)
        self.message_label.setText(message)


class AppShell(QWidget):
    new_project_requested = Signal()
    open_project_requested = Signal()
    recent_project_requested = Signal(str)
    rename_project_requested = Signal()
    delete_project_requested = Signal()

    def __init__(self, animations_enabled: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AppShell")
        self._animations_enabled = animations_enabled
        self._page_keys: list[str] = []
        self.dashboard: DashboardHome | None = None
        self.download_page: DownloadPage | None = None
        self.materials_page: MaterialLibraryPage | None = None
        self.scripts_page: ScriptEditorPage | None = None
        self.media_tools_page: MediaToolsPage | None = None
        self.notes_page: NotesPage | None = None
        self.sensitive_words_page: SensitiveWordsPage | None = None

        self.wallpaper = WallpaperBackground(self)
        self.wallpaper.lower()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        self.top_bar = TopBar(self)
        self.top_bar.toggle_sidebar_requested.connect(self.toggle_sidebar)
        self.top_bar.tasks_requested.connect(self.toggle_task_drawer)
        self.top_bar.new_project_requested.connect(self.new_project_requested)
        self.top_bar.open_project_requested.connect(self.open_project_requested)
        self.top_bar.recent_project_requested.connect(
            self.recent_project_requested
        )
        self.top_bar.rename_project_requested.connect(
            self.rename_project_requested
        )
        self.top_bar.delete_project_requested.connect(
            self.delete_project_requested
        )
        self.top_bar.exit_action.triggered.connect(lambda: self.window().close())

        body = QWidget(self)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        self.sidebar = Sidebar(animations_enabled=animations_enabled, parent=body)
        self.sidebar.selected_changed.connect(self.select_page)

        self.content_frame = QFrame(body)
        self.content_frame.setObjectName("GlassContent")
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(20, 18, 20, 18)
        content_layout.setSpacing(14)
        self.page_stack = QStackedWidget(self.content_frame)
        content_layout.addWidget(self.page_stack)

        self.context_panel = ContextPanel(body)

        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.content_frame, 1)
        body_layout.addWidget(self.context_panel)

        self.task_drawer = TaskDrawer(
            animations_enabled=animations_enabled,
            parent=self,
        )

        root_layout.addWidget(self.top_bar)
        root_layout.addWidget(body, 1)
        root_layout.addWidget(self.task_drawer)

        self.toast_host = ToastHost(
            self,
            animations_enabled=self._animations_enabled,
        )
        self.toast_host.raise_()

        self._create_pages()
        self.select_page("project")

    @property
    def current_page_key(self) -> str | None:
        index = self.page_stack.currentIndex()
        if 0 <= index < len(self._page_keys):
            return self._page_keys[index]
        return None

    def toggle_sidebar(self) -> None:
        self.sidebar.set_collapsed(not self.sidebar.is_collapsed)

    def toggle_task_drawer(self) -> None:
        self.task_drawer.toggle()

    def select_page(self, key: str) -> None:
        if key not in self._page_keys:
            return
        self.page_stack.setCurrentIndex(self._page_keys.index(key))
        if self._animations_enabled:
            self._fade_in(self.page_stack.currentWidget())
        if self.sidebar.selected_key() != key:
            self.sidebar.select(key)

        self.context_panel.setVisible(key in {"download", "materials", "tools"})
        self._apply_context_for_page(key)

    def set_project(self, name: str | None, path: str | None = None) -> None:
        self.top_bar.set_project(name, path)
        self.sidebar.path_label.setText(path or "未打开项目")
        if self.dashboard is not None:
            self.dashboard.set_project(name)
        if self.download_page is not None:
            self.download_page.set_project(path)
        if self.materials_page is not None:
            self.materials_page.set_project(path)
        if self.scripts_page is not None:
            self.scripts_page.set_project(path)
        if self.media_tools_page is not None:
            self.media_tools_page.set_project(path)
        if self.notes_page is not None:
            self.notes_page.set_project(path)

    def set_recent_projects(self, projects: list[tuple[str, str]]) -> None:
        self.top_bar.set_recent_projects(projects)

    def set_wallpaper_path(self, path: str | None) -> bool:
        return self.wallpaper.set_wallpaper_path(path)

    def show_message(
        self,
        message: str,
        kind: str = "info",
        duration_ms: int = 3000,
    ):
        toast = self.toast_host.show_message(message, kind, duration_ms)
        self.toast_host.raise_()
        self._position_toast_host()
        return toast

    def _create_pages(self) -> None:
        for item in NAVIGATION_ITEMS:
            page = self._create_page(item)
            self._page_keys.append(item.key)
            self.page_stack.addWidget(page)

    def _create_page(self, item: NavigationItem) -> QWidget:
        page = QWidget(self.page_stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header = PageHeader(item.title, item.description, page)
        layout.addWidget(header)

        if item.key == "project":
            dashboard = DashboardHome(
                page,
                animations_enabled=self._animations_enabled,
            )
            dashboard.new_project_requested.connect(self.new_project_requested)
            dashboard.open_project_requested.connect(self.open_project_requested)
            self.dashboard = dashboard
            layout.addWidget(dashboard, 1)
            return page

        if item.key == "download":
            self.download_page = DownloadPage(page)
            layout.addWidget(self.download_page, 1)
            return page

        if item.key == "scripts":
            self.scripts_page = ScriptEditorPage(page)
            self.scripts_page.message_requested.connect(self.show_message)
            layout.addWidget(self.scripts_page, 1)
            return page

        if item.key == "materials":
            self.materials_page = MaterialLibraryPage(page)
            self.materials_page.message_requested.connect(self.show_message)
            self.materials_page.context_changed.connect(
                self.context_panel.set_context
            )
            layout.addWidget(self.materials_page, 1)
            return page

        if item.key == "tools":
            self.media_tools_page = MediaToolsPage(page)
            self.media_tools_page.message_requested.connect(self.show_message)
            self.media_tools_page.context_changed.connect(
                self.context_panel.set_context
            )
            layout.addWidget(self.media_tools_page, 1)
            return page

        if item.key == "notes":
            self.notes_page = NotesPage(page)
            self.notes_page.message_requested.connect(self.show_message)
            layout.addWidget(self.notes_page, 1)
            return page

        if item.key == "sensitive":
            self.sensitive_words_page = SensitiveWordsPage(page)
            self.sensitive_words_page.message_requested.connect(
                self.show_message
            )
            layout.addWidget(self.sensitive_words_page, 1)
            return page

        return page

    def _apply_context_for_page(self, key: str) -> None:
        if key == "download":
            self.context_panel.set_context("下载详情", "选择任务后查看下载状态")
        elif key == "materials":
            if self.materials_page is not None:
                self.materials_page.publish_context()
        elif key == "tools":
            if self.media_tools_page is not None:
                self.media_tools_page.publish_context()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.wallpaper.setGeometry(self.rect())
        self.wallpaper.lower()
        self._position_toast_host()

    def _position_toast_host(self) -> None:
        self.toast_host.fit_to_contents()
        margin = 22
        self.toast_host.move(
            max(margin, self.width() - self.toast_host.width() - margin),
            max(76, self.height() - self.toast_host.height() - margin),
        )

    def _fade_in(self, widget: QWidget) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(220)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
