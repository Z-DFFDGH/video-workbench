from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._ui import application

from video_workbench.app import AppConfig, ConfigStore
from video_workbench.project import create_project
from video_workbench.ui.main_window import MainWindow


class ProjectLifecycleUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def create_window(self, store: ConfigStore) -> MainWindow:
        window = MainWindow(config_store=store, animations_enabled=False)
        self.addCleanup(window.close)
        return window

    def test_create_project_updates_ui_and_recent_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project_root = root / "新项目"
            project_root.mkdir()
            store = ConfigStore(root / "config.json")
            window = self.create_window(store)

            with patch(
                "video_workbench.ui.main_window.QFileDialog.getExistingDirectory",
                return_value=str(project_root),
            ):
                window._create_project()

            self.assertEqual(window._current_project.name, "新项目")
            self.assertEqual(
                window.shell.top_bar.project_title.text(),
                "新项目",
            )
            self.assertTrue(
                window.shell.top_bar.delete_project_action.isEnabled()
            )
            self.assertEqual(
                store.load().recent_projects,
                [str(project_root.resolve())],
            )

    def test_open_project_uses_directory_picker_and_accepts_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "通过目录打开")
            window = self.create_window(ConfigStore(root / "config.json"))

            with patch(
                "video_workbench.ui.main_window.QFileDialog.getExistingDirectory",
                return_value=str(project.root),
            ) as directory_picker:
                window._prompt_open_project()

            directory_picker.assert_called_once()
            self.assertEqual(window._current_project, project)

    def test_open_project_switches_and_calls_autosave_hook_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = create_project(root / "项目一")
            second = create_project(root / "项目二")
            store = ConfigStore(root / "config.json")
            window = self.create_window(store)
            window._open_project_path(str(first.project_file))

            events: list[str] = []
            window.set_before_project_switch_hook(
                lambda: events.append(window._current_project.name)
            )
            window._open_project_path(str(second.project_file))

            self.assertEqual(events, ["项目一"])
            self.assertEqual(window._current_project, second)
            self.assertEqual(
                store.load().recent_projects[0],
                str(second.root),
            )

    def test_rename_updates_display_name_without_moving_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "原目录名")
            store = ConfigStore(root / "config.json")
            window = self.create_window(store)
            window._open_project_path(str(project.project_file))

            changed = window._rename_current_project("新的显示名称")

            self.assertTrue(changed)
            self.assertEqual(window._current_project.root, project.root)
            self.assertEqual(
                window.shell.dashboard.project_name.text(),
                "新的显示名称",
            )
            metadata = json.loads(
                project.project_file.read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["name"], "新的显示名称")

    def test_delete_uses_confirmation_and_removes_recent_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "待删除项目")
            store = ConfigStore(root / "config.json")
            window = self.create_window(store)
            window._open_project_path(str(project.project_file))

            with (
                patch(
                    "video_workbench.ui.main_window.confirm",
                    return_value=True,
                ) as confirmation,
                patch(
                    "video_workbench.ui.main_window.delete_project",
                ) as trash_project,
            ):
                window._prompt_delete_project()

            confirmation.assert_called_once()
            trash_project.assert_called_once_with(project)
            self.assertIsNone(window._current_project)
            self.assertEqual(
                window.shell.top_bar.project_title.text(),
                "未打开项目",
            )
            self.assertEqual(store.load().recent_projects, [])

    def test_missing_recent_project_is_removed_on_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = ConfigStore(root / "config.json")
            store.save(
                AppConfig(
                    recent_projects=[str(root / "missing-project")],
                )
            )

            window = self.create_window(store)

            self.assertEqual(store.load().recent_projects, [])
            self.assertEqual(window.shell.top_bar.recent_projects_menu.actions()[0].text(), "暂无最近项目")

    def test_open_missing_project_removes_path_and_shows_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            missing = root / "missing-project"
            store = ConfigStore(root / "config.json")
            store.save(AppConfig(recent_projects=[str(missing)]))
            window = self.create_window(store)

            window._open_project_path(str(missing))

            self.assertEqual(store.load().recent_projects, [])
            self.assertGreaterEqual(len(window.shell.toast_host.active_messages), 1)


if __name__ == "__main__":
    unittest.main()
