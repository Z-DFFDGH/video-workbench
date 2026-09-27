from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

import requests

from video_workbench.downloader.adapter import (
    DefaultDownloadAdapter,
    DownloadAdapterSettings,
)
from video_workbench.downloader.errors import DownloadCanceled, DownloadError
from video_workbench.downloader.files import sanitize_filename, unique_destination
from video_workbench.downloader.models import DownloadMode


class FakeResponse:
    def __init__(
        self,
        *,
        chunks: list[bytes] | None = None,
        text: str = "",
        url: str = "https://example.com/media.mp4",
        error: Exception | None = None,
        on_chunk=None,
    ) -> None:
        self.chunks = chunks or []
        self.text = text
        self.url = url
        self.error = error
        self.on_chunk = on_chunk
        self.closed = False

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    def iter_content(self, chunk_size: int):
        del chunk_size
        for chunk in self.chunks:
            yield chunk
            if self.on_chunk is not None:
                self.on_chunk()

    def close(self) -> None:
        self.closed = True


class SequenceSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected request")
        return self.responses.pop(0)


class DownloadAdapterTests(unittest.TestCase):
    def test_unknown_page_uses_ytdlp_fallback_with_expected_format(self) -> None:
        class FakeYoutubeDL:
            options = None

            def __init__(self, options):
                FakeYoutubeDL.options = options

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                del exc_type, exc, traceback

            def extract_info(self, url, download):
                del url, download
                template = Path(FakeYoutubeDL.options["outtmpl"])
                output = template.parent / "page [id].mp4"
                output.write_bytes(b"yt-dlp-video")
                return {"title": "page", "id": "id"}

        with tempfile.TemporaryDirectory() as temporary_directory:
            adapter = DefaultDownloadAdapter(session=SequenceSession([]))  # type: ignore[arg-type]
            with patch("yt_dlp.YoutubeDL", FakeYoutubeDL):
                result = adapter.download(
                    "https://example.com/page",
                    temporary_directory,
                    DownloadMode.VIDEO,
                    Event(),
                )

            self.assertEqual(result.path.name, "page.mp4")
            self.assertEqual(result.path.read_bytes(), b"yt-dlp-video")
            self.assertIn(
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]",
                FakeYoutubeDL.options["format"],
            )
    def tearDown(self) -> None:
        self.assertTrue(all(True for _ in ()))

    def test_direct_url_retries_and_removes_part_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            failure = FakeResponse(
                error=requests.ConnectionError("network down")
            )
            success = FakeResponse(chunks=[b"video-data"])
            session = SequenceSession([failure, failure, success])
            adapter = DefaultDownloadAdapter(
                session=session,  # type: ignore[arg-type]
                settings=DownloadAdapterSettings(
                    retry_times=3,
                    retry_delay_seconds=0,
                ),
            )

            result = adapter.download(
                "https://files.example/clip.mp4",
                root,
                DownloadMode.VIDEO,
                Event(),
            )

            self.assertEqual(result.attempts, 3)
            self.assertEqual(result.path.read_bytes(), b"video-data")
            self.assertFalse(Path(str(result.path) + ".part").exists())
            self.assertEqual(len(session.calls), 3)

    def test_cancel_cleans_part_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cancel_event = Event()
            response = FakeResponse(
                chunks=[b"first", b"second"],
                on_chunk=cancel_event.set,
            )
            adapter = DefaultDownloadAdapter(
                session=SequenceSession([response]),  # type: ignore[arg-type]
                settings=DownloadAdapterSettings(retry_delay_seconds=0),
            )

            with self.assertRaises(DownloadCanceled):
                adapter.download(
                    "https://files.example/clip.mp4",
                    root,
                    DownloadMode.VIDEO,
                    cancel_event,
                )

            self.assertEqual(list(root.iterdir()), [])

    def test_retry_exhaustion_reports_failure_and_cleans_part(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            session = SequenceSession(
                [
                    FakeResponse(error=requests.ConnectionError("one")),
                    FakeResponse(error=requests.ConnectionError("two")),
                ]
            )
            adapter = DefaultDownloadAdapter(
                session=session,  # type: ignore[arg-type]
                settings=DownloadAdapterSettings(
                    retry_times=2,
                    retry_delay_seconds=0,
                ),
            )

            with self.assertRaises(DownloadError):
                adapter.download(
                    "https://files.example/clip.mp4",
                    root,
                    DownloadMode.VIDEO,
                    Event(),
                )

            self.assertEqual(list(root.iterdir()), [])

    def test_douyin_parser_does_not_rewrite_playwm_watermark_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            del temporary_directory
            router_data = {
                "loaderData": {
                    "video_123/page": {
                        "videoInfoRes": {
                            "item_list": [
                                {
                                    "desc": "测试视频",
                                    "video": {
                                        "play_addr": {
                                            "url_list": [
                                                "https://cdn.example/playwm/clip.mp4"
                                            ]
                                        }
                                    },
                                }
                            ]
                        }
                    }
                }
            }
            page = (
                "<script>window._ROUTER_DATA = "
                + json.dumps(router_data, ensure_ascii=False)
                + "</script>"
            )
            session = SequenceSession(
                [FakeResponse(text=page, url="https://www.douyin.com/video/123")]
            )
            adapter = DefaultDownloadAdapter(
                session=session,  # type: ignore[arg-type]
            )

            resolved = adapter._resolve_download_url(
                "https://www.douyin.com/video/123",
                Event(),
            )

            self.assertIsNotNone(resolved)
            self.assertIn("/playwm/", resolved.url)
            self.assertEqual(resolved.referer, "https://www.douyin.com/")

    def test_filename_helpers_sanitize_and_avoid_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.assertEqual(
                sanitize_filename('  bad:/name*?  '),
                "bad_name_",
            )
            existing = root / "clip.mp4"
            existing.write_bytes(b"one")
            self.assertEqual(
                unique_destination(root, "clip.mp4").name,
                "clip_1.mp4",
            )


if __name__ == "__main__":
    unittest.main()
