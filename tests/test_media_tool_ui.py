from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests._ui import application

from video_workbench.app import ConfigStore
from video_workbench.media_tools import (
    FFmpegCanceled,
    FFmpegRunner,
    MediaTaskStatus,
    MediaToolService,
)
from video_workbench.project import create_project
from video_workbench.ui.main_window import MainWindow
from video_workbench.ui.pages.tools import MediaToolsPage


class RecordingRunner:
    def run(self, command, cancel_event, output_path) -> None:
        del command, cancel_event
        Path(output_path).write_bytes(b"generated")


class BlockingRunner:
    def __init__(self) -> None:
        self.started = threading.Event()

    def run(self, command, cancel_event, output_path) -> None:
        del command
        output = Path(output_path)
        output.write_bytes(b"partial")
        self.started.set()
        while not cancel_event.wait(0.01):
            pass
        output.unlink(missing_ok=True)
        raise FFmpegCanceled("canceled")


class MediaToolsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def create_page(self, root: Path) -> tuple[MediaToolsPage, MediaToolService]:
        service = MediaToolService(runner=RecordingRunner())
        self.addCleanup(service.shutdown)
        page = MediaToolsPage(service=service)
        page.set_project(None)
        page.output_edit.setText(str(root))
        return page, service

    def test_default_page_uses_ffmpeg_runner(self) -> None:
        page = MediaToolsPage()
        self.addCleanup(page.service.shutdown)

        self.assertIsInstance(page.service._runner, FFmpegRunner)
        self.assertIs(page.service.parent(), page)

    def test_tool_switching_updates_page_and_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            page, _service = self.create_page(Path(temporary_directory))

            for tool_key, index in (
                ("format", 0),
                ("trim", 1),
                ("resize", 2),
                ("volume", 3),
            ):
                with self.subTest(tool=tool_key):
                    page._set_tool(tool_key)
                    self.assertEqual(page.parameter_stack.currentIndex(), index)
                    self.assertTrue(page.tool_buttons[tool_key].isChecked())

    def test_no_project_can_choose_and_remember_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = root / "selected-output"
            selected.mkdir()
            page, _service = self.create_page(root)
            received: list[str] = []
            page.output_directory_changed.connect(received.append)

            with patch(
                "video_workbench.ui.pages.tools.QFileDialog.getExistingDirectory",
                return_value=str(selected),
            ):
                page.choose_output_button.click()

            self.assertEqual(page.output_edit.text(), str(selected.resolve()))
            self.assertEqual(received, [str(selected.resolve())])
            self.assertTrue(page.choose_output_button.isEnabled())

    def test_main_window_persists_media_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = root / "media-output"
            selected.mkdir()
            store = ConfigStore(root / "config.json")
            window = MainWindow(config_store=store, animations_enabled=False)
            self.addCleanup(window.close)
            page = window.shell.media_tools_page

            with patch(
                "video_workbench.ui.pages.tools.QFileDialog.getExistingDirectory",
                return_value=str(selected),
            ):
                page.choose_output_button.click()

            self.assertEqual(
                Path(store.load().media_output_directory),
                selected.resolve(),
            )

    def test_project_forces_output_directory_and_library_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "project")
            page, _service = self.create_page(root)

            page.set_project(project.root)

            self.assertEqual(
                Path(page.output_edit.text()),
                (project.root / "输出成品").resolve(),
            )
            self.assertFalse(page.choose_output_button.isEnabled())
            self.assertTrue(page.library_checkbox.isChecked())
            self.assertTrue(page.library_checkbox.isEnabled())

    def test_invalid_parameters_do_not_create_task(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            page, service = self.create_page(root)
            page.input_edit.setText(str(source))
            page._set_tool("trim")
            page.start_time_edit.setText("00:05")
            page.end_time_edit.setText("00:02")

            page.start_button.click()

            self.assertEqual(service.tasks(), [])
            self.assertFalse(page.feedback.isHidden())
            self.assertTrue(page.feedback.text_label.text())

    def test_media_task_appears_in_unified_drawer_and_can_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            output = root / "output"
            output.mkdir()
            window = MainWindow(
                config_store=ConfigStore(root / "config.json"),
                animations_enabled=False,
            )
            self.addCleanup(window.close)
            page = window.shell.media_tools_page
            runner = BlockingRunner()
            window.media_tool_service._runner = runner
            page.input_edit.setText(str(source))
            page.output_edit.setText(str(output))

            page.start_processing()
            self.assertTrue(runner.started.wait(2.0))
            self.app.processEvents()

            self.assertEqual(window.shell.task_drawer.row_count, 1)
            row = window.shell.task_drawer._rows[0]
            self.assertTrue(row.cancel_button.isEnabled())
            row.cancel_button.click()

            deadline = time.time() + 3.0
            task = None
            while time.time() < deadline:
                task = window.media_tool_service.tasks()[0]
                if task.status == MediaTaskStatus.CANCELED:
                    break
                self.app.processEvents()
                time.sleep(0.01)
            self.assertIsNotNone(task)
            self.assertEqual(task.status, MediaTaskStatus.CANCELED)
            self.assertFalse(Path(task.output_path).exists())

    def test_opening_project_updates_media_tools_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "project")
            window = MainWindow(
                config_store=ConfigStore(root / "config.json"),
                animations_enabled=False,
            )
            self.addCleanup(window.close)

            window._open_project_path(str(project.root))

            page = window.shell.media_tools_page
            self.assertEqual(
                Path(page.output_edit.text()),
                (project.root / "输出成品").resolve(),
            )
            self.assertTrue(page.library_checkbox.isChecked())


if __name__ == "__main__":
    unittest.main()
