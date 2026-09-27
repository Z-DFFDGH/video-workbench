from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from urllib.parse import unquote, urlparse

import requests

from .errors import DownloadCanceled, DownloadError, SourceResolutionError
from .ffmpeg import FFmpegAudioExtractor
from .files import sanitize_filename, unique_destination
from .models import DownloadMode

MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
DIRECT_MEDIA_SUFFIXES = {
    ".aac",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}
CONTENT_DISPOSITION_PATTERN = re.compile(
    r"filename\*?=(?:UTF-8''|utf-8'')?\"?([^\";]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DownloadAdapterSettings:
    retry_times: int = 3
    retry_delay_seconds: float = 2.0
    connect_timeout_seconds: float = 30.0
    download_timeout_seconds: float = 120.0
    page_timeout_seconds: float = 20.0
    chunk_size: int = 64 * 1024


@dataclass(frozen=True, slots=True)
class DownloadResult:
    path: Path
    title: str
    attempts: int = 1


@dataclass(frozen=True, slots=True)
class _ResolvedMedia:
    url: str
    title: str
    referer: str


class DefaultDownloadAdapter:
    """Adapter based on the bundled all-in-one downloader's core flow."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        audio_extractor: FFmpegAudioExtractor | None = None,
        settings: DownloadAdapterSettings | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.audio_extractor = audio_extractor or FFmpegAudioExtractor()
        self.settings = settings or DownloadAdapterSettings()

    def download(
        self,
        source_url: str,
        output_directory: str | Path,
        mode: DownloadMode,
        cancel_event: Event,
    ) -> DownloadResult:
        output_root = Path(output_directory).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=".download-", dir=output_root)
        )

        try:
            resolved = self._resolve_download_url(source_url, cancel_event)
            if resolved is not None:
                downloaded, attempts = self._download_resolved(
                    resolved,
                    staging,
                    cancel_event,
                )
                title = resolved.title
            else:
                downloaded, title, attempts = self._download_with_ytdlp(
                    source_url,
                    staging,
                    mode,
                    cancel_event,
                )

            if cancel_event.is_set():
                raise DownloadCanceled("下载已取消")

            if mode == DownloadMode.AUDIO:
                output = unique_destination(
                    output_root,
                    f"{sanitize_filename(title)}.mp3",
                )
                self.audio_extractor.extract(downloaded, output, cancel_event)
            else:
                extension = downloaded.suffix or ".mp4"
                output = unique_destination(
                    output_root,
                    f"{sanitize_filename(title)}{extension}",
                )
                os.replace(downloaded, output)

            return DownloadResult(
                path=output.resolve(),
                title=title,
                attempts=attempts,
            )
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _resolve_download_url(
        self,
        source_url: str,
        cancel_event: Event,
    ) -> _ResolvedMedia | None:
        parsed = urlparse(source_url)
        if "douyin.com" in parsed.netloc.lower() or "iesdouyin.com" in parsed.netloc.lower():
            resolved = self._resolve_douyin(source_url, cancel_event)
            if resolved is not None:
                return resolved

        if Path(parsed.path).suffix.lower() in DIRECT_MEDIA_SUFFIXES:
            return _ResolvedMedia(
                url=source_url,
                title=Path(unquote(parsed.path)).stem or "download",
                referer=f"{parsed.scheme}://{parsed.netloc}/",
            )
        return None

    def _resolve_douyin(
        self,
        source_url: str,
        cancel_event: Event,
    ) -> _ResolvedMedia | None:
        self._check_cancel(cancel_event)
        try:
            response = self.session.get(
                source_url,
                headers=MOBILE_HEADERS,
                allow_redirects=True,
                timeout=self.settings.page_timeout_seconds,
            )
            response.raise_for_status()
            real_url = response.url
            page_text = response.text
            response.close()

            if real_url != source_url:
                page_response = self.session.get(
                    real_url,
                    headers=MOBILE_HEADERS,
                    timeout=self.settings.page_timeout_seconds,
                )
                page_response.raise_for_status()
                page_text = page_response.text
                page_response.close()
        except requests.RequestException as error:
            raise SourceResolutionError(
                f"抖音页面解析失败：{error}"
            ) from error

        match = re.search(
            r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*(?:</script>|;|$)",
            page_text,
            re.DOTALL,
        )
        if not match:
            return None

        try:
            router_data = json.loads(match.group(1))
            loader_data = router_data.get("loaderData", {})
            video_key = next(
                (
                    key
                    for key in loader_data
                    if re.match(r"video_\d+/page", key)
                ),
                None,
            )
            if video_key is None:
                return None

            video_info = (
                loader_data[video_key]
                .get("videoInfoRes", {})
                .get("item_list", [{}])[0]
            )
            url_list = (
                video_info.get("video", {})
                .get("play_addr", {})
                .get("url_list", [])
            )
            if not url_list or not isinstance(url_list[0], str):
                return None
            media_url = url_list[0]
            if media_url.startswith("//"):
                media_url = f"https:{media_url}"
            elif media_url.startswith("http://"):
                media_url = f"https://{media_url[7:]}"

            video_id = self._douyin_video_id(real_url)
            title = str(video_info.get("desc") or video_id or "douyin_video")
            return _ResolvedMedia(
                url=media_url,
                title=title,
                referer="https://www.douyin.com/",
            )
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _douyin_video_id(url: str) -> str | None:
        for pattern in (
            r"/video/(\d+)",
            r"/note/(\d+)",
            r"modal_id=(\d+)",
            r"item_ids=(\d+)",
        ):
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _download_resolved(
        self,
        resolved: _ResolvedMedia,
        staging: Path,
        cancel_event: Event,
    ) -> tuple[Path, int]:
        suffix = Path(urlparse(resolved.url).path).suffix.lower()
        if suffix not in DIRECT_MEDIA_SUFFIXES:
            suffix = ".mp4"
        destination = staging / f"{sanitize_filename(resolved.title)}{suffix}"
        attempts = self._download_file(
            resolved.url,
            destination,
            resolved.referer,
            cancel_event,
        )
        return destination, attempts

    def _download_file(
        self,
        url: str,
        destination: Path,
        referer: str,
        cancel_event: Event,
    ) -> int:
        headers = MOBILE_HEADERS.copy()
        headers["Referer"] = referer
        temporary = destination.with_name(destination.name + ".part")
        last_error: Exception | None = None

        for attempt in range(1, self.settings.retry_times + 1):
            self._check_cancel(cancel_event)
            response = None
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=self.settings.download_timeout_seconds,
                )
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(
                        chunk_size=self.settings.chunk_size
                    ):
                        self._check_cancel(cancel_event)
                        if chunk:
                            output.write(chunk)
                os.replace(temporary, destination)
                return attempt
            except DownloadCanceled:
                temporary.unlink(missing_ok=True)
                raise
            except (OSError, requests.RequestException) as error:
                last_error = error
                temporary.unlink(missing_ok=True)
                if attempt < self.settings.retry_times:
                    self._wait_before_retry(cancel_event)
            finally:
                if response is not None:
                    response.close()

        detail = str(last_error) if last_error else "未知网络错误"
        raise DownloadError(
            f"下载失败，已重试 {self.settings.retry_times} 次：{detail}"
        )

    def _download_with_ytdlp(
        self,
        source_url: str,
        staging: Path,
        mode: DownloadMode,
        cancel_event: Event,
    ) -> tuple[Path, str, int]:
        try:
            import yt_dlp
        except ImportError as error:
            raise SourceResolutionError(
                "缺少 yt-dlp，请运行 pip install -r requirements.txt"
            ) from error

        def progress_hook(_data: dict[str, object]) -> None:
            self._check_cancel(cancel_event)

        output_template = str(staging / "%(title).80s [%(id)s].%(ext)s")
        options: dict[str, object] = {
            "format": (
                "bestaudio/best"
                if mode == DownloadMode.AUDIO
                else "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            ),
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": self.settings.retry_times,
            "fragment_retries": self.settings.retry_times,
            "socket_timeout": self.settings.connect_timeout_seconds,
            "progress_hooks": [progress_hook],
            "overwrites": True,
            "continuedl": False,
        }
        if mode == DownloadMode.VIDEO:
            options["merge_output_format"] = "mp4"
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            options["ffmpeg_location"] = ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(source_url, download=True)
            title = str(info.get("title") or info.get("id") or "download")
        except Exception as error:
            if cancel_event.is_set():
                raise DownloadCanceled("下载已取消") from error
            raise DownloadError(f"yt-dlp 下载失败：{error}") from error

        media_files = [
            path
            for path in staging.rglob("*")
            if path.is_file()
            and path.suffix.lower() not in {".part", ".ytdl"}
            and not path.name.endswith(".part")
        ]
        if not media_files:
            raise DownloadError("yt-dlp 未生成可下载的媒体文件")
        media_path = max(media_files, key=lambda path: path.stat().st_size)
        return media_path, title, 1

    @staticmethod
    def _check_cancel(cancel_event: Event) -> None:
        if cancel_event.is_set():
            raise DownloadCanceled("下载已取消")

    def _wait_before_retry(self, cancel_event: Event) -> None:
        deadline = time.monotonic() + self.settings.retry_delay_seconds
        while time.monotonic() < deadline:
            self._check_cancel(cancel_event)
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
