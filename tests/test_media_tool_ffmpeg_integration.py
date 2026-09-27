from __future__ import annotations

import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests._ui import application

from video_workbench.materials import FFprobeDetector, MediaType
from video_workbench.ui.pages.tools import MediaToolsPage
from video_workbench.media_tools import (
    MediaTaskStatus,
    MediaToolService,
    conversion_request,
    resize_request,
    trim_request,
    volume_request,
)


def run_ffmpeg(arguments: list[str]) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


class MediaToolFfmpegIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def create_video(self, path: Path, duration: float = 1.2) -> None:
        run_ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c=blue:s=320x180:d={duration}",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:duration={duration}",
                "-shortest",
                "-c:v",
                "mpeg4",
                "-q:v",
                "5",
                "-c:a",
                "aac",
                str(path),
            ]
        )

    def wait_for_task(self, service: MediaToolService, task_id: str):
        deadline = time.time() + 30.0
        while time.time() < deadline:
            task = service.get_task(task_id)
            if task is not None and task.status not in {
                MediaTaskStatus.QUEUED,
                MediaTaskStatus.RUNNING,
            }:
                return task
            self.app.processEvents()
            time.sleep(0.02)
        self.fail("FFmpeg task did not finish")

    def test_real_video_conversion_and_audio_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "clip.mp4"
            output_directory = root / "output"
            output_directory.mkdir()
            self.create_video(source)
            service = MediaToolService()
            self.addCleanup(service.shutdown)

            video_task = service.enqueue(
                conversion_request(source, output_directory, ".mkv")
            )
            audio_task = service.enqueue(
                conversion_request(source, output_directory, ".mp3")
            )
            video_result = self.wait_for_task(service, video_task.task_id)
            audio_result = self.wait_for_task(service, audio_task.task_id)

            self.assertEqual(video_result.status, MediaTaskStatus.COMPLETED)
            self.assertEqual(audio_result.status, MediaTaskStatus.COMPLETED)
            self.assertTrue(Path(video_result.output_path).is_file())
            self.assertTrue(Path(audio_result.output_path).is_file())
            detector = FFprobeDetector()
            self.assertEqual(
                detector.detect(video_result.output_path).media_type,
                MediaType.VIDEO,
            )
            self.assertEqual(
                detector.detect(audio_result.output_path).media_type,
                MediaType.AUDIO,
            )

    def test_default_ui_service_runs_real_ffmpeg(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "clip.mp4"
            output_directory = root / "output"
            output_directory.mkdir()
            self.create_video(source)
            page = MediaToolsPage()
            self.addCleanup(page.service.shutdown)
            page.input_edit.setText(str(source))
            page.output_edit.setText(str(output_directory))

            page.start_processing()
            task = page.service.tasks()[0]
            result = self.wait_for_task(page.service, task.task_id)

            self.assertEqual(result.status, MediaTaskStatus.COMPLETED)
            self.assertTrue(Path(result.output_path).is_file())

    def test_real_trim_resize_and_volume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_video = root / "clip.mp4"
            source_audio = root / "voice.wav"
            output_directory = root / "output"
            output_directory.mkdir()
            self.create_video(source_video)
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=523.25:duration=0.8",
                    "-c:a",
                    "pcm_s16le",
                    str(source_audio),
                ]
            )
            service = MediaToolService()
            self.addCleanup(service.shutdown)

            requests = (
                trim_request(source_video, output_directory, "00:00.2", "00:00.8"),
                resize_request(source_video, output_directory, 180, 320),
                volume_request(source_audio, output_directory, -3),
            )
            results = [
                self.wait_for_task(
                    service,
                    service.enqueue(request).task_id,
                )
                for request in requests
            ]

            self.assertTrue(
                all(
                    result.status == MediaTaskStatus.COMPLETED
                    for result in results
                )
            )
            for result in results:
                self.assertTrue(Path(result.output_path).is_file())
            resized = FFprobeDetector().detect(results[1].output_path)
            self.assertEqual(resized.media_type, MediaType.VIDEO)
            self.assertEqual((resized.width, resized.height), (180, 320))
            volume = FFprobeDetector().detect(results[2].output_path)
            self.assertEqual(volume.media_type, MediaType.AUDIO)


if __name__ == "__main__":
    unittest.main()
