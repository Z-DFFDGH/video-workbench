from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from video_workbench.materials import (
    FFmpegThumbnailGenerator,
    FFprobeDetector,
    MaterialLibrary,
    MaterialStatus,
    MediaType,
)
from video_workbench.project import create_project


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


class MaterialFfmpegIntegrationTests(unittest.TestCase):
    def test_real_ffprobe_and_ffmpeg_import_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "集成项目")
            video_path = root / "clip.mp4"
            audio_path = root / "voice.wav"
            image_path = root / "cover.png"

            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=blue:s=320x240:d=1",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=1",
                    "-shortest",
                    "-c:v",
                    "mpeg4",
                    "-q:v",
                    "5",
                    "-c:a",
                    "aac",
                    str(video_path),
                ]
            )
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=0.5",
                    "-c:a",
                    "pcm_s16le",
                    str(audio_path),
                ]
            )
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=red:s=320x240",
                    "-frames:v",
                    "1",
                    str(image_path),
                ]
            )

            library = MaterialLibrary(
                project,
                detector=FFprobeDetector(),
                thumbnail_generator=FFmpegThumbnailGenerator(width=320),
            )
            video = library.import_file(video_path, copy_to_project=True)
            audio = library.import_file(audio_path, copy_to_project=True)
            image = library.import_file(image_path, copy_to_project=True)

            self.assertEqual(video.media_type, MediaType.VIDEO)
            self.assertEqual(video.status, MaterialStatus.READY)
            self.assertEqual(video.width, 320)
            self.assertEqual(video.height, 240)
            self.assertEqual(audio.media_type, MediaType.AUDIO)
            self.assertEqual(image.media_type, MediaType.IMAGE)

            self.assertEqual(
                Path(video.path).parent,
                (project.root / "原素材").resolve(),
            )
            self.assertEqual(
                Path(audio.path).parent,
                (project.root / "音频文件").resolve(),
            )
            self.assertEqual(
                Path(image.path).parent,
                (project.root / "图片封面").resolve(),
            )
            self.assertIsNotNone(video.thumbnail_path)
            self.assertTrue(Path(video.thumbnail_path).is_file())
            self.assertGreater(Path(video.thumbnail_path).stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
