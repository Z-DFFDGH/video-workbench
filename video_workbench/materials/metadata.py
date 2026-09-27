from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .models import MediaMetadata, MediaType

IMAGE_FORMAT_NAMES = {
    "bmp_pipe",
    "gif",
    "ico",
    "image2",
    "jpeg_pipe",
    "png_pipe",
    "tiff_pipe",
    "webp_pipe",
}


class MediaDetectionError(Exception):
    """Raised when FFprobe cannot identify a media file."""


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FFprobeDetector:
    def __init__(
        self,
        executable: str = "ffprobe",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def detect(self, media_path: str | Path) -> MediaMetadata:
        path = Path(media_path).expanduser().resolve()
        command = [
            self.executable,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=self.timeout_seconds,
                creationflags=_creation_flags(),
            )
        except FileNotFoundError as error:
            raise MediaDetectionError(
                f"找不到 FFprobe 可执行文件：{self.executable}"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise MediaDetectionError("FFprobe 检测超时") from error
        except OSError as error:
            raise MediaDetectionError(f"无法启动 FFprobe：{error}") from error

        if result.returncode != 0:
            detail = result.stderr.strip() or "FFprobe 返回未知错误"
            raise MediaDetectionError(detail)

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise MediaDetectionError("FFprobe 返回了无效 JSON") from error

        return _metadata_from_probe(payload)


def _metadata_from_probe(payload: object) -> MediaMetadata:
    if not isinstance(payload, dict):
        raise MediaDetectionError("FFprobe JSON 根节点无效")

    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise MediaDetectionError("FFprobe JSON 缺少 streams")

    format_payload = payload.get("format")
    if not isinstance(format_payload, dict):
        format_payload = {}

    format_name = _optional_text(format_payload.get("format_name"))
    video_stream = _first_stream(streams, "video")
    audio_stream = _first_stream(streams, "audio")

    if video_stream is not None and _is_image_stream(format_name):
        return MediaMetadata(
            media_type=MediaType.IMAGE,
            width=_optional_int(video_stream.get("width")),
            height=_optional_int(video_stream.get("height")),
            codec=_optional_text(video_stream.get("codec_name")),
            format_name=format_name,
        )

    if video_stream is not None:
        return MediaMetadata(
            media_type=MediaType.VIDEO,
            duration_seconds=_duration_seconds(
                format_payload,
                video_stream,
            ),
            width=_optional_int(video_stream.get("width")),
            height=_optional_int(video_stream.get("height")),
            codec=_optional_text(video_stream.get("codec_name")),
            format_name=format_name,
        )

    if audio_stream is not None:
        return MediaMetadata(
            media_type=MediaType.AUDIO,
            duration_seconds=_duration_seconds(
                format_payload,
                audio_stream,
            ),
            codec=_optional_text(audio_stream.get("codec_name")),
            format_name=format_name,
        )

    raise MediaDetectionError("FFprobe 未识别出视频、音频或图片流")


def _first_stream(
    streams: list[object],
    codec_type: str,
) -> dict[str, Any] | None:
    for stream in streams:
        if (
            isinstance(stream, dict)
            and stream.get("codec_type") == codec_type
        ):
            return stream
    return None


def _is_image_stream(format_name: str | None) -> bool:
    if format_name:
        names = {name.strip().lower() for name in format_name.split(",")}
        if names & IMAGE_FORMAT_NAMES:
            return True
    return False


def _duration_seconds(
    format_payload: dict[str, Any],
    stream: dict[str, Any],
) -> float | None:
    return _optional_float(format_payload.get("duration")) or _optional_float(
        stream.get("duration")
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    clean_value = value.strip()
    return clean_value or None


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
