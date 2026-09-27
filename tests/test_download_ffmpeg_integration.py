from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from threading import Event

from video_workbench.downloader.ffmpeg import FFmpegAudioExtractor
from video_workbench.materials import FFprobeDetector, MediaType


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


class DownloadFfmpegIntegrationTests(unittest.TestCase):
    def test_real_ffmpeg_extracts_mp3_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "voice.wav"
            output = root / "voice.mp3"
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=523.25:duration=0.6",
                    "-c:a",
                    "pcm_s16le",
                    str(source),
                ]
            )

            produced = FFmpegAudioExtractor().extract(
                source,
                output,
                Event(),
            )

            self.assertEqual(produced, output.resolve())
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)
            metadata = FFprobeDetector().detect(output)
            self.assertEqual(metadata.media_type, MediaType.AUDIO)


if __name__ == "__main__":
    unittest.main()
