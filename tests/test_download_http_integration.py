from __future__ import annotations

import functools
import subprocess
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event

from video_workbench.downloader.adapter import DefaultDownloadAdapter
from video_workbench.downloader.models import DownloadMode
from video_workbench.materials import (
    FFmpegThumbnailGenerator,
    FFprobeDetector,
    MaterialLibrary,
    MediaType,
)
from video_workbench.project import create_project


class QuietRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args) -> None:
        del format, args


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


class DownloadHttpIntegrationTests(unittest.TestCase):
    def test_real_http_download_then_ffmpeg_audio_extract_and_library_import(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            server_root = root / "server"
            server_root.mkdir()
            source = server_root / "voice.wav"
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=0.4",
                    "-c:a",
                    "pcm_s16le",
                    str(source),
                ]
            )

            handler = functools.partial(
                QuietRequestHandler,
                directory=str(server_root),
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )
            thread.start()

            def stop_server() -> None:
                server.shutdown()
                thread.join(timeout=3)
                server.server_close()

            self.addCleanup(stop_server)

            output_directory = root / "downloads"
            result = DefaultDownloadAdapter().download(
                f"http://127.0.0.1:{server.server_port}/voice.wav",
                output_directory,
                DownloadMode.AUDIO,
                Event(),
            )

            self.assertEqual(result.path.suffix.lower(), ".mp3")
            self.assertTrue(result.path.is_file())
            self.assertEqual(
                FFprobeDetector().detect(result.path).media_type,
                MediaType.AUDIO,
            )

            project = create_project(root / "project")
            library = MaterialLibrary(
                project,
                detector=FFprobeDetector(),
                thumbnail_generator=FFmpegThumbnailGenerator(),
            )
            material = library.import_file(result.path)

            self.assertEqual(material.media_type, MediaType.AUDIO)
            self.assertEqual(material.path, str(result.path.resolve()))


if __name__ == "__main__":
    unittest.main()
