from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests._ui import application

from video_workbench.downloader import (
    DownloadMode,
    DownloadService,
    DownloadStatus,
)
from video_workbench.downloader.errors import DownloadCanceled


def wait_until(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


class RecordingAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def download(self, source_url, output_directory, mode, cancel_event):
        del mode, cancel_event
        self.calls.append(source_url)
        if source_url.endswith("/fail.mp4"):
            raise RuntimeError("expected failure")
        output = Path(output_directory) / f"{len(self.calls)}.mp4"
        output.write_bytes(b"video")
        return SimpleNamespace(path=output, title=output.stem, attempts=1)


class BlockingAdapter:
    def __init__(self) -> None:
        self.started = threading.Event()

    def download(self, source_url, output_directory, mode, cancel_event):
        del source_url, mode
        part_path = Path(output_directory) / "blocked.mp4.part"
        part_path.write_bytes(b"partial")
        self.started.set()
        if not cancel_event.wait(timeout=3):
            raise RuntimeError("cancel timeout")
        part_path.unlink(missing_ok=True)
        raise DownloadCanceled("canceled")


class StubLibrary:
    def __init__(self) -> None:
        self.imported: list[Path] = []

    def import_file(self, source_path, copy_to_project=False):
        self.imported.append(Path(source_path))
        return SimpleNamespace(material_id="material-1")


class DownloadServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def test_tasks_run_in_order_and_failure_does_not_stop_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            adapter = RecordingAdapter()
            service = DownloadService(adapter=adapter)
            self.addCleanup(service.shutdown)

            service.enqueue_many(
                [
                    "https://example.com/one.mp4",
                    "https://example.com/fail.mp4",
                    "https://example.com/three.mp4",
                ],
                temporary_directory,
                DownloadMode.VIDEO,
            )

            self.assertTrue(
                wait_until(
                    lambda: all(
                        task.status
                        in {
                            DownloadStatus.COMPLETED,
                            DownloadStatus.FAILED,
                        }
                        for task in service.tasks()
                    )
                )
            )
            tasks = service.tasks()
            self.assertEqual(
                adapter.calls,
                [
                    "https://example.com/one.mp4",
                    "https://example.com/fail.mp4",
                    "https://example.com/three.mp4",
                ],
            )
            self.assertEqual(
                [task.status for task in tasks],
                [
                    DownloadStatus.COMPLETED,
                    DownloadStatus.FAILED,
                    DownloadStatus.COMPLETED,
                ],
            )
            self.assertIn("expected failure", tasks[1].error)

    def test_cancel_running_task_cleans_part_and_queue_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            adapter = BlockingAdapter()
            service = DownloadService(adapter=adapter)
            self.addCleanup(service.shutdown)
            tasks = service.enqueue_many(
                ["https://example.com/blocked.mp4"],
                temporary_directory,
                DownloadMode.VIDEO,
            )
            self.assertTrue(adapter.started.wait(timeout=2))

            canceled = service.cancel(tasks[0].task_id)

            self.assertTrue(canceled)
            self.assertTrue(
                wait_until(
                    lambda: service.get_task(tasks[0].task_id).status
                    == DownloadStatus.CANCELED
                )
            )
            self.assertFalse(
                (Path(temporary_directory) / "blocked.mp4.part").exists()
            )

    def test_completed_download_can_be_added_to_project_library(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            library = StubLibrary()
            service = DownloadService(
                adapter=RecordingAdapter(),
                library_factory=lambda _project_root: library,
            )
            self.addCleanup(service.shutdown)

            service.enqueue_many(
                ["https://example.com/one.mp4"],
                root / "downloads",
                DownloadMode.VIDEO,
                add_to_library=True,
                project_root=root / "project",
            )

            self.assertTrue(
                wait_until(
                    lambda: service.tasks()
                    and service.tasks()[0].status
                    == DownloadStatus.COMPLETED
                )
            )
            task = service.tasks()[0]
            self.assertEqual(task.material_id, "material-1")
            self.assertEqual(library.imported, [Path(task.output_path)])

    def test_enqueue_returns_while_adapter_is_still_running(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            adapter = BlockingAdapter()
            service = DownloadService(adapter=adapter)
            self.addCleanup(service.shutdown)

            started_at = time.monotonic()
            service.enqueue_many(
                ["https://example.com/blocked.mp4"],
                temporary_directory,
                DownloadMode.VIDEO,
            )
            elapsed = time.monotonic() - started_at

            self.assertLess(elapsed, 0.5)
            self.assertTrue(adapter.started.wait(timeout=2))


if __name__ == "__main__":
    unittest.main()
