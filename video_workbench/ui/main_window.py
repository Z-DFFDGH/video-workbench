from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsOpacityEffect,
    QInputDialog,
    QMainWindow,
    QSizeGrip,
)

from video_workbench.app import AppConfig, ConfigError, ConfigStore
from video_workbench.downloader import DownloadService, DownloadStatus
from video_workbench.project import (
    ProjectError,
    ProjectInfo,
    ProjectNotFoundError,
    create_project,
    delete_project,
    forget_recent_project,
    load_project,
    remember_recent_project,
    rename_project,
)
from video_workbench.media_tools import MediaTaskStatus
from video_workbench.ui.components.dialogs import confirm
from video_workbench.ui.components.task_drawer import (
    download_task_item,
    media_task_item,
)
from video_workbench.ui.components.wallpaper import WallpaperPanel
from video_workbench.ui.shell import AppShell


class MainWindow(QMainWindow):
    def __init__(
        self,
        config_store: ConfigStore | None = None,
        animations_enabled: bool = True,
    ) -> None:
        super().__init__()
        self._config_store = config_store or ConfigStore()
        self._config: AppConfig = self._config_store.load()
        self._animations_enabled = animations_enabled
        self._current_project: ProjectInfo | None = None
        self._before_project_switch_hook: Callable[[], None] | None = None
        self._last_download_statuses: dict[str, DownloadStatus] = {}
        self._last_media_statuses: dict[str, MediaTaskStatus] = {}
        self.download_service = DownloadService(parent=self)

        self.setWindowTitle("自媒体剪辑辅助工具")
        self.setMinimumSize(1120, 720)
        self.resize(1440, 900)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        self.shell = AppShell(animations_enabled=animations_enabled, parent=self)
        media_tools_page = self.shell.media_tools_page
        if media_tools_page is None:
            raise RuntimeError("media tools page was not created")
        self.media_tool_service = media_tools_page.service
        self.setCentralWidget(self.shell)

        self.wallpaper_panel = WallpaperPanel(self)
        self.wallpaper_panel.raise_()

        self._size_grip = QSizeGrip(self)
        self._size_grip.setFixedSize(16, 16)

        self._connect_actions()
        self._load_initial_wallpaper()
        self.shell.download_page.set_last_directory(
            self._config.download_directory
        )
        media_tools_page.set_last_directory(
            self._config.media_output_directory
        )
        self._refresh_download_tasks()
        self._cleanup_recent_projects()

        application = QApplication.instance()
        self._event_filter_installed = application is not None
        if application is not None:
            application.installEventFilter(self)

    def _connect_actions(self) -> None:
        top_bar = self.shell.top_bar
        top_bar.appearance_requested.connect(self._toggle_wallpaper_panel)
        top_bar.minimize_requested.connect(self.showMinimized)
        top_bar.maximize_requested.connect(self._toggle_maximized)
        top_bar.close_requested.connect(self.close)

        self.shell.new_project_requested.connect(self._create_project)
        self.shell.open_project_requested.connect(self._prompt_open_project)
        self.shell.recent_project_requested.connect(self._open_project_path)
        self.shell.rename_project_requested.connect(self._prompt_rename_project)
        self.shell.delete_project_requested.connect(self._prompt_delete_project)
        self.shell.download_page.download_requested.connect(
            self._enqueue_download
        )
        self.shell.download_page.output_directory_changed.connect(
            self._remember_download_directory
        )
        self.shell.media_tools_page.output_directory_changed.connect(
            self._remember_media_output_directory
        )
        self.download_service.task_added.connect(
            self._handle_download_task_added
        )
        self.download_service.task_updated.connect(
            self._handle_download_task_update
        )
        self.download_service.queue_changed.connect(
            self._refresh_download_tasks
        )
        self.media_tool_service.task_added.connect(
            self._handle_media_task_added
        )
        self.media_tool_service.task_updated.connect(
            self._handle_media_task_update
        )
        self.media_tool_service.queue_changed.connect(
            self._refresh_download_tasks
        )

        self.wallpaper_panel.wallpaper_selected.connect(self._apply_wallpaper)
        self.wallpaper_panel.restore_requested.connect(self._restore_default_wallpaper)

    def set_before_project_switch_hook(
        self,
        hook: Callable[[], None] | None,
    ) -> None:
        self._before_project_switch_hook = hook

    def _enqueue_download(
        self,
        urls: list[str],
        output_directory: str,
        mode,
        add_to_library: bool,
    ) -> None:
        project_root = (
            self._current_project.root
            if self._current_project is not None
            else None
        )
        try:
            created = self.download_service.enqueue_many(
                urls,
                output_directory,
                mode,
                add_to_library=add_to_library,
                project_root=project_root,
            )
        except (OSError, ValueError) as error:
            self.shell.show_message(str(error), "error", 5000)
            return
        self.shell.show_message(
            f"已加入下载队列：{len(created)} 个任务",
            "success",
            2500,
        )

    def _remember_download_directory(self, directory: str) -> None:
        self._config.download_directory = directory
        self._save_config()

    def _remember_media_output_directory(self, directory: str) -> None:
        self._config.media_output_directory = directory
        self._save_config()

    def _handle_download_task_added(self, task_id: str) -> None:
        del task_id
        self._refresh_download_tasks()

    def _handle_download_task_update(self, task_id: str) -> None:

        task = self.download_service.get_task(task_id)
        if task is None:
            return
        previous = self._last_download_statuses.get(task_id)
        self._last_download_statuses[task_id] = task.status
        self._refresh_download_tasks()

        if previous == task.status:
            return
        if task.status == DownloadStatus.COMPLETED:
            if task.library_error:
                self.shell.show_message(
                    f"下载完成，但加入素材库失败：{task.library_error}",
                    "warning",
                    6000,
                )
            else:
                self.shell.show_message("下载任务已完成", "success", 3000)
        elif task.status == DownloadStatus.FAILED:
            detail = task.error or "未知错误"
            self.shell.show_message(
                f"下载失败：{detail[:160]}",
                "error",
                6000,
            )
        elif task.status == DownloadStatus.CANCELED:
            self.shell.show_message("下载任务已取消", "warning", 3000)

    def _handle_media_task_added(self, task_id: str) -> None:
        del task_id
        self._refresh_download_tasks()

    def _handle_media_task_update(self, task_id: str) -> None:
        task = self.media_tool_service.get_task(task_id)
        if task is None:
            return
        previous = self._last_media_statuses.get(task_id)
        self._last_media_statuses[task_id] = task.status
        self._refresh_download_tasks()

        if previous == task.status:
            return
        if task.status == MediaTaskStatus.COMPLETED:
            if task.library_error:
                self.shell.show_message(
                    f"媒体处理完成，但加入素材库失败：{task.library_error}",
                    "warning",
                    6000,
                )
            else:
                self.shell.show_message("媒体处理任务已完成", "success", 3000)
        elif task.status == MediaTaskStatus.FAILED:
            detail = task.error or "未知错误"
            self.shell.show_message(
                f"媒体处理失败：{detail[:160]}",
                "error",
                6000,
            )
        elif task.status == MediaTaskStatus.CANCELED:
            self.shell.show_message("媒体处理任务已取消", "warning", 3000)

    def _refresh_download_tasks(self) -> None:
        tasks = self.download_service.tasks()
        media_tasks = self.media_tool_service.tasks()
        task_items = [download_task_item(task) for task in tasks]
        task_items.extend(media_task_item(task) for task in media_tasks)
        self.shell.task_drawer.set_items(
            task_items,
            self._cancel_task,
        )
        self.shell.task_drawer.set_summary(
            self.download_service.active_count()
            + self.media_tool_service.active_count(),
            self.download_service.failed_count()
            + self.media_tool_service.failed_count(),
        )
        self.shell.download_page.set_queue_summary(
            self.download_service.active_count(),
            self.download_service.failed_count(),
            len(tasks),
        )
        self.shell.media_tools_page.set_queue_summary(
            self.media_tool_service.active_count(),
            self.media_tool_service.failed_count(),
            len(media_tasks),
        )

    def _cancel_task(self, task_id: str) -> bool:
        if self.media_tool_service.get_task(task_id) is not None:
            return self.media_tool_service.cancel(task_id)
        return self.download_service.cancel(task_id)

    def eventFilter(self, watched, event) -> bool:
        if self.wallpaper_panel.isVisible():
            if (
                event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape
            ):
                self.wallpaper_panel.hide()
                return True
            if event.type() == QEvent.Type.MouseButtonPress:
                global_position = event.globalPosition().toPoint()
                if not self._contains_global_position(
                    self.wallpaper_panel, global_position
                ) and not self._contains_global_position(
                    self.shell.top_bar.appearance_button, global_position
                ):
                    self.wallpaper_panel.hide()

        return super().eventFilter(watched, event)

    @staticmethod
    def _contains_global_position(widget, global_position: QPoint) -> bool:
        return widget.isVisible() and widget.rect().contains(
            widget.mapFromGlobal(global_position)
        )

    def _load_initial_wallpaper(self) -> None:
        path = self._config.wallpaper_path
        applied = self.shell.set_wallpaper_path(path)
        if path and not applied:
            self.shell.set_wallpaper_path(None)
            self.wallpaper_panel.set_current_wallpaper(None)
            self.shell.show_message(
                "原壁纸文件不可用，已恢复默认壁纸",
                "warning",
                6000,
            )
            return
        self.wallpaper_panel.set_current_wallpaper(path)

    def _toggle_wallpaper_panel(self) -> None:
        if self.wallpaper_panel.isVisible():
            self.wallpaper_panel.hide()
            return

        self.wallpaper_panel.set_current_wallpaper(
            self.shell.wallpaper.wallpaper_path
        )
        self.wallpaper_panel.adjustSize()
        self._position_wallpaper_panel()
        self.wallpaper_panel.show()
        self.wallpaper_panel.raise_()
        self._animate_wallpaper_panel_in()

    def _position_wallpaper_panel(self) -> None:
        button = self.shell.top_bar.appearance_button
        global_position = button.mapToGlobal(QPoint(0, button.height() + 7))
        local_position = self.mapFromGlobal(global_position)
        x = min(
            local_position.x(),
            max(10, self.width() - self.wallpaper_panel.width() - 10),
        )
        y = min(
            local_position.y(),
            max(10, self.height() - self.wallpaper_panel.height() - 10),
        )
        self.wallpaper_panel.move(max(10, x), max(10, y))

    def _animate_wallpaper_panel_in(self) -> None:
        if not self._animations_enabled:
            return
        panel = self.wallpaper_panel
        effect = QGraphicsOpacityEffect(panel)
        panel.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", panel)
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: panel.setGraphicsEffect(None))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _apply_wallpaper(self, path: str) -> None:
        previous_path = self.shell.wallpaper.wallpaper_path
        if not self.shell.set_wallpaper_path(path):
            self.shell.show_message(
                "无法读取所选图片，请选择有效的 PNG、JPG、BMP 或 WEBP 文件",
                "error",
                6000,
            )
            return

        self._config.wallpaper_path = path
        try:
            self._config_store.save(self._config)
        except ConfigError as error:
            self.shell.set_wallpaper_path(previous_path)
            self._config.wallpaper_path = previous_path
            self.shell.show_message(str(error), "error", 6000)
            return

        self.wallpaper_panel.set_current_wallpaper(path)
        self.shell.show_message("壁纸已更新", "success", 3000)

    def _restore_default_wallpaper(self) -> None:
        previous_path = self.shell.wallpaper.wallpaper_path
        self.shell.set_wallpaper_path(None)
        self._config.wallpaper_path = None
        try:
            self._config_store.save(self._config)
        except ConfigError as error:
            self.shell.set_wallpaper_path(previous_path)
            self._config.wallpaper_path = previous_path
            self.shell.show_message(str(error), "error", 6000)
            return

        self.wallpaper_panel.set_current_wallpaper(None)
        self.shell.show_message("已恢复默认壁纸", "success", 3000)

    def _toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._update_size_grip()

    def _create_project(self) -> None:
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "选择项目根目录",
            str(Path.home()),
        )
        if not selected_directory:
            return

        try:
            project = create_project(selected_directory)
        except ProjectError as error:
            self.shell.show_message(str(error), "warning", 6000)
            return
        except OSError as error:
            self.shell.show_message(f"创建项目失败：{error}", "error", 6000)
            return

        if not self._switch_project(project):
            return
        self._remember_project(project)
        self.shell.show_message("项目已创建并打开", "success", 3000)

    def _prompt_open_project(self) -> None:
        start_directory = str(Path.home())
        if self._current_project is not None:
            start_directory = str(self._current_project.root)
        elif self._config.recent_projects:
            start_directory = self._config.recent_projects[0]

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "打开已有项目",
            start_directory,
        )
        if selected_directory:
            self._open_project_path(selected_directory)

    def _open_project_path(self, project_path: str) -> None:
        try:
            project = load_project(project_path)
        except ProjectNotFoundError:
            self._forget_project_path(project_path)
            self.shell.show_message(
                "项目路径不存在，已从最近项目列表移除",
                "warning",
                6000,
            )
            return
        except ProjectError as error:
            self.shell.show_message(str(error), "warning", 6000)
            return
        except OSError as error:
            self.shell.show_message(f"打开项目失败：{error}", "error", 6000)
            return

        if not self._switch_project(project):
            return
        self._remember_project(project)
        self.shell.show_message(f"已打开项目：{project.name}", "success", 3000)

    def _switch_project(self, project: ProjectInfo) -> bool:
        if not self._autosave_project_documents():
            return False
        if self._before_project_switch_hook is not None:
            try:
                self._before_project_switch_hook()
            except Exception as error:
                self.shell.show_message(
                    f"切换项目前自动保存失败：{error}",
                    "error",
                    6000,
                )
                return False

        self._current_project = project
        self.shell.set_project(project.name, str(project.root))
        return True

    def _prompt_rename_project(self) -> None:
        if self._current_project is None:
            self.shell.show_message("请先打开项目", "warning", 4000)
            return

        new_name, accepted = QInputDialog.getText(
            self,
            "重命名项目",
            "新的显示名称：",
            text=self._current_project.name,
        )
        if accepted:
            self._rename_current_project(new_name)

    def _rename_current_project(self, new_name: str) -> bool:
        if self._current_project is None:
            self.shell.show_message("请先打开项目", "warning", 4000)
            return False

        try:
            renamed = rename_project(self._current_project, new_name)
        except ProjectError as error:
            self.shell.show_message(str(error), "warning", 6000)
            return False
        except OSError as error:
            self.shell.show_message(f"重命名项目失败：{error}", "error", 6000)
            return False

        self._current_project = renamed
        self.shell.set_project(renamed.name, str(renamed.root))
        self._remember_project(renamed)
        self.shell.show_message("项目名称已更新", "success", 3000)
        return True

    def _prompt_delete_project(self) -> None:
        if self._current_project is None:
            self.shell.show_message("请先打开项目", "warning", 4000)
            return

        project = self._current_project
        if not confirm(
            self,
            "删除项目",
            f"将“{project.name}”移入 Windows 回收站？\n目录：{project.root}",
            confirm_text="移入回收站",
            destructive=True,
        ):
            return

        if not self._autosave_project_documents():
            return

        try:
            delete_project(project)
        except ProjectError as error:
            self.shell.show_message(str(error), "error", 6000)
            return
        except OSError as error:
            self.shell.show_message(f"删除项目失败：{error}", "error", 6000)
            return

        self._current_project = None
        self.shell.set_project(None)
        self._forget_project_path(project.root)
        self.shell.show_message("项目已移入 Windows 回收站", "success", 4000)

    def _remember_project(self, project: ProjectInfo) -> None:
        self._config.recent_projects = remember_recent_project(
            self._config.recent_projects,
            project.root,
        )
        self._save_config()
        self._refresh_recent_projects()

    def _forget_project_path(self, project_path: str | Path) -> None:
        self._config.recent_projects = forget_recent_project(
            self._config.recent_projects,
            project_path,
        )
        self._save_config()
        self._refresh_recent_projects()

    def _save_config(self) -> bool:
        try:
            self._config_store.save(self._config)
        except ConfigError as error:
            self.shell.show_message(str(error), "error", 6000)
            return False
        return True

    def _cleanup_recent_projects(self) -> None:
        missing_paths = [
            path
            for path in self._config.recent_projects
            if not Path(path).is_dir()
        ]
        for path in missing_paths:
            self._config.recent_projects = forget_recent_project(
                self._config.recent_projects,
                path,
            )

        if missing_paths:
            self._save_config()
            self.shell.show_message(
                f"{len(missing_paths)} 个最近项目路径不可用，已从列表移除",
                "warning",
                6000,
            )
        self._refresh_recent_projects()

    def _refresh_recent_projects(self) -> None:
        entries: list[tuple[str, str]] = []
        for path in self._config.recent_projects:
            try:
                name = load_project(path).name
            except ProjectError:
                name = f"{Path(path).name}（不可用）"
            entries.append((name, path))
        self.shell.set_recent_projects(entries)

    def _autosave_project_documents(self) -> bool:
        pages = (
            ("脚本", self.shell.scripts_page),
            ("项目笔记", self.shell.notes_page),
        )
        succeeded = True
        for label, page in pages:
            if page is None:
                continue
            try:
                saved = page.autosave()
            except Exception as error:
                self.shell.show_message(
                    f"{label}自动保存失败：{error}",
                    "error",
                    6000,
                )
                succeeded = False
                continue
            if not saved:
                self.shell.show_message(
                    f"{label}自动保存失败，操作已取消",
                    "error",
                    6000,
                )
                succeeded = False
        return succeeded

    def _update_size_grip(self) -> None:
        if not hasattr(self, "_size_grip"):
            return
        self._size_grip.setVisible(not self.isMaximized())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "_size_grip"):
            return
        self._position_wallpaper_panel()
        self._size_grip.move(
            self.width() - self._size_grip.width() - 2,
            self.height() - self._size_grip.height() - 2,
        )
        self._update_size_grip()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        self._update_size_grip()

    def closeEvent(self, event) -> None:
        if not self._autosave_project_documents():
            self.shell.show_message(
                "文档自动保存失败，已取消关闭",
                "error",
                6000,
            )
            event.ignore()
            return
        self.download_service.shutdown(wait_seconds=3.0)
        self.media_tool_service.shutdown(wait_seconds=3.0)
        application = QApplication.instance()
        if application is not None and self._event_filter_installed:
            application.removeEventFilter(self)
            self._event_filter_installed = False
        super().closeEvent(event)
