from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tests._ui import application

from video_workbench.app import ConfigStore
from video_workbench.downloader import (
    DownloadMode,
    DownloadStatus,
    DownloadTask,
)
from video_workbench.project import create_project
from video_workbench.ui.components.task_drawer import TaskDrawer
from video_workbench.ui.main_window import MainWindow
from video_workbench.ui.pages import DownloadPage


class DownloadUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def test_download_page_validates_lines_and_emits_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            page = DownloadPage()
            page.set_project(temporary_directory)
            page.link_input.setPlainText(
                "https://example.com/one.mp4\n"
                "not-a-link\n"
                "https://example.com/two.mp3"
            )
            received: list[tuple] = []
            page.download_requested.connect(
                lambda *arguments: received.append(arguments)
            )
            self.assertIn(
                "已忽略 1 行",
                page.validation_message.text_label.text(),
            )

            page.start_button.click()

            self.assertEqual(len(received), 1)
            urls, directory, mode, add_to_library = received[0]
            self.assertEqual(
                urls,
                [
                    "https://example.com/one.mp4",
                    "https://example.com/two.mp3",
                ],
            )
            self.assertEqual(
                Path(directory),
                (Path(temporary_directory) / "输出成品").resolve(),
            )
            self.assertEqual(mode, DownloadMode.VIDEO)
            self.assertFalse(add_to_library)
            self.assertIn(
                "已加入下载队列",
                page.validation_message.text_label.text(),
            )

    def test_download_page_blocks_library_when_no_project_is_open(self) -> None:
        page = DownloadPage()

        page.set_project(None)

        self.assertFalse(page.library_checkbox.isEnabled())
        self.assertIn("Downloads", page.output_edit.text())

    def test_main_window_remembers_browse_directory_and_enqueues_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selected = root / "custom-downloads"
            selected.mkdir()
            store = ConfigStore(root / "config.json")
            window = MainWindow(config_store=store, animations_enabled=False)
            self.addCleanup(window.close)
            page = window.shell.download_page
            page.set_project(None)
            page.link_input.setPlainText("https://example.com/audio.mp3")
            page.mode_combo.setCurrentIndex(1)
            queued_task = DownloadTask(
                task_id="task-1",
                source_url="https://example.com/audio.mp3",
                output_directory=str(selected),
                mode=DownloadMode.AUDIO,
            )

            with (
                patch.object(
                    window.download_service,
                    "enqueue_many",
                    return_value=[queued_task],
                ) as enqueue,
                patch(
                    "video_workbench.ui.pages.download.QFileDialog.getExistingDirectory",
                    return_value=str(selected),
                ),
            ):
                page.browse_button.click()
                page.start_button.click()

            enqueue.assert_called_once()
            arguments = enqueue.call_args
            self.assertEqual(arguments.args[0], ["https://example.com/audio.mp3"])
            self.assertEqual(arguments.args[1], str(selected))
            self.assertEqual(arguments.args[2], DownloadMode.AUDIO)
            self.assertFalse(arguments.kwargs["add_to_library"])
            self.assertEqual(
                Path(store.load().download_directory),
                selected.resolve(),
            )

    def test_task_drawer_renders_statuses_and_cancel_action(self) -> None:
        drawer = TaskDrawer(animations_enabled=False)
        cancel = Mock(return_value=True)
        running = DownloadTask(
            task_id="running",
            source_url="https://example.com/running.mp4",
            output_directory="C:\\downloads",
            mode=DownloadMode.VIDEO,
            status=DownloadStatus.RUNNING,
        )
        completed = DownloadTask(
            task_id="completed",
            source_url="https://example.com/completed.mp4",
            output_directory="C:\\downloads",
            mode=DownloadMode.VIDEO,
            status=DownloadStatus.COMPLETED,
            output_path="C:\\downloads\\completed.mp4",
        )

        drawer.set_tasks([running, completed], cancel)

        self.assertEqual(drawer.row_count, 2)
        self.assertTrue(drawer._rows[0].cancel_button.isEnabled())
        self.assertFalse(drawer._rows[1].cancel_button.isEnabled())
        drawer._rows[0].cancel_button.click()
        cancel.assert_called_once_with("running")

    def test_opening_project_enables_library_option_and_uses_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "project")
            window = MainWindow(
                config_store=ConfigStore(root / "config.json"),
                animations_enabled=False,
            )
            self.addCleanup(window.close)

            window._open_project_path(str(project.project_file))

            page = window.shell.download_page
            self.assertTrue(page.library_checkbox.isEnabled())
            self.assertEqual(
                Path(page.output_edit.text()),
                (project.root / "输出成品").resolve(),
            )


if __name__ == "__main__":
    unittest.main()
