from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests._ui import application

from video_workbench.media_tools import (
    FFmpegCanceled,
    FFmpegRunError,
    FFmpegRunner,
    MediaToolRequest,
    MediaOperation,
    MediaTaskStatus,
    MediaToolService,
    conversion_request,
)


class FakeRunner:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.commands: list[tuple[str, ...]] = []

    def run(self, command, cancel_event, output_path) -> None:
        self.commands.append(tuple(command))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"generated")
        if self.error is not None:
            raise self.error
        if cancel_event.is_set():
            Path(output_path).unlink(missing_ok=True)
            raise FFmpegCanceled("canceled")


class FakeLibrary:
    def __init__(self) -> None:
        self.imported: list[tuple[str, bool, bool]] = []

    def import_file(
        self,
        source_path,
        copy_to_project: bool = False,
        generate_thumbnail: bool = True,
    ):
        self.imported.append(
            (str(source_path), copy_to_project, generate_thumbnail)
        )

        class Record:
            material_id = "material-1"

        return Record()


class MediaToolServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.source = self.root / "clip.mp4"
        self.source.write_bytes(b"video")

    def wait_for_task(self, service: MediaToolService, task_id: str):
        deadline = time.time() + 3.0
        while time.time() < deadline:
            task = service.get_task(task_id)
            if task is not None and task.status not in {
                MediaTaskStatus.QUEUED,
                MediaTaskStatus.RUNNING,
            }:
                return task
            self.app.processEvents()
            time.sleep(0.01)
        self.fail("task did not finish")

    def test_service_runs_with_unique_output_names(self) -> None:
        runner = FakeRunner()
        service = MediaToolService(runner=runner)
        self.addCleanup(service.shutdown)
        request = conversion_request(self.source, self.output, ".mkv")

        first = service.enqueue(request)
        second = service.enqueue(request)
        first_done = self.wait_for_task(service, first.task_id)
        second_done = self.wait_for_task(service, second.task_id)

        self.assertEqual(first_done.status, MediaTaskStatus.COMPLETED)
        self.assertEqual(second_done.status, MediaTaskStatus.COMPLETED)
        self.assertEqual(Path(first_done.output_path).name, "clip.mkv")
        self.assertEqual(Path(second_done.output_path).name, "clip_1.mkv")
        self.assertEqual(len(runner.commands), 2)

    def test_completed_task_can_be_recorded_in_project_library(self) -> None:
        runner = FakeRunner()
        library = FakeLibrary()
        service = MediaToolService(
            runner=runner,
            library_factory=lambda _root: library,
        )
        self.addCleanup(service.shutdown)
        request = conversion_request(self.source, self.output, ".mkv")

        task = service.enqueue(
            request,
            add_to_library=True,
            project_root=self.root,
        )
        completed = self.wait_for_task(service, task.task_id)

        self.assertEqual(completed.material_id, "material-1")
        self.assertIsNone(completed.library_error)
        self.assertEqual(len(library.imported), 1)
        self.assertFalse(library.imported[0][1])
        self.assertTrue(library.imported[0][2])

    def test_failure_removes_partial_output(self) -> None:
        runner = FakeRunner(error=FFmpegRunError("ffmpeg failed"))
        service = MediaToolService(runner=runner)
        self.addCleanup(service.shutdown)
        request = conversion_request(self.source, self.output, ".mkv")

        task = service.enqueue(request)
        failed = self.wait_for_task(service, task.task_id)

        self.assertEqual(failed.status, MediaTaskStatus.FAILED)
        self.assertIn("ffmpeg failed", failed.error)
        self.assertFalse(Path(failed.output_path).exists())

    def test_invalid_request_does_not_start_runner(self) -> None:
        runner = FakeRunner()
        service = MediaToolService(runner=runner)
        self.addCleanup(service.shutdown)
        request = MediaToolRequest(
            operation=MediaOperation.RESIZE_VIDEO,
            source_path=str(self.source),
            output_directory=str(self.output),
            output_extension=".mp4",
            width=1080,
            height=1079,
        )

        with self.assertRaises(ValueError):
            service.enqueue(request)

        self.assertEqual(runner.commands, [])

    def test_runner_cancellation_terminates_process_and_removes_output(self) -> None:
        output = self.root / "partial.mp4"
        runner = FFmpegRunner(executable=sys.executable)
        cancel_event = threading.Event()
        script = (
            "import pathlib, sys, time; "
            "pathlib.Path(sys.argv[1]).write_text('partial', encoding='utf-8'); "
            "time.sleep(10)"
        )
        canceller = threading.Thread(
            target=lambda: (time.sleep(0.35), cancel_event.set()),
            daemon=True,
        )
        canceller.start()

        with self.assertRaises(FFmpegCanceled):
            runner.run(
                [sys.executable, "-c", script, str(output)],
                cancel_event,
                output,
            )

        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
