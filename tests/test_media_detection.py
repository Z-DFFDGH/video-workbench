from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video_workbench.materials import (
    FFmpegThumbnailGenerator,
    FFprobeDetector,
    MediaDetectionError,
    MediaType,
    ThumbnailGenerationError,
)


class MediaDetectionTests(unittest.TestCase):
    def test_ffprobe_command_and_video_metadata(self) -> None:
        payload = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "duration": "12.345",
            },
        }
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

        with patch(
            "video_workbench.materials.metadata.subprocess.run",
            return_value=completed,
        ) as run:
            metadata = FFprobeDetector().detect("clip.mp4")

        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["ffprobe", "-v", "error", "-print_format", "json"])
        self.assertIn("-show_format", command)
        self.assertIn("-show_streams", command)
        self.assertEqual(metadata.media_type, MediaType.VIDEO)
        self.assertEqual(metadata.duration_seconds, 12.345)
        self.assertEqual(metadata.width, 1920)
        self.assertEqual(metadata.height, 1080)
        self.assertEqual(metadata.codec, "h264")

    def test_ffprobe_recognizes_audio_and_image_streams(self) -> None:
        cases = (
            (
                {
                    "streams": [
                        {"codec_type": "audio", "codec_name": "pcm_s16le"}
                    ],
                    "format": {"format_name": "wav", "duration": "2.0"},
                },
                MediaType.AUDIO,
            ),
            (
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "png",
                            "width": 800,
                            "height": 600,
                        }
                    ],
                    "format": {"format_name": "png_pipe"},
                },
                MediaType.IMAGE,
            ),
        )

        for payload, expected_type in cases:
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
            with self.subTest(expected_type=expected_type):
                with patch(
                    "video_workbench.materials.metadata.subprocess.run",
                    return_value=completed,
                ):
                    metadata = FFprobeDetector().detect("media.bin")
                self.assertEqual(metadata.media_type, expected_type)

    def test_ffprobe_failure_is_reported(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="Invalid data found",
        )

        with patch(
            "video_workbench.materials.metadata.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaises(MediaDetectionError):
                FFprobeDetector().detect("broken.mp4")

    def test_ffmpeg_thumbnail_command_creates_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "clip.mp4"
            output = root / "thumbnail.jpg"
            source.write_bytes(b"video")

            def fake_run(command, **kwargs):
                self.assertEqual(kwargs["check"], False)
                Path(command[-1]).write_bytes(b"jpeg")
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout="",
                    stderr="",
                )

            with patch(
                "video_workbench.materials.thumbnails.subprocess.run",
                side_effect=fake_run,
            ) as run:
                generated = FFmpegThumbnailGenerator(width=640).generate(
                    source,
                    output,
                )

            command = run.call_args.args[0]
            self.assertEqual(command[0], "ffmpeg")
            self.assertIn("-frames:v", command)
            self.assertEqual(command[command.index("-frames:v") + 1], "1")
            self.assertEqual(
                command[command.index("-vf") + 1],
                "scale=640:-2:force_original_aspect_ratio=decrease",
            )
            self.assertEqual(generated, output.resolve())
            self.assertTrue(generated.is_file())

    def test_ffmpeg_thumbnail_failure_removes_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "clip.mp4"
            output = root / "thumbnail.jpg"
            source.write_bytes(b"video")
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="encoding failed",
            )

            with patch(
                "video_workbench.materials.thumbnails.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaises(ThumbnailGenerationError):
                    FFmpegThumbnailGenerator().generate(source, output)

            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
