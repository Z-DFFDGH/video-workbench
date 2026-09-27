from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .metadata import _creation_flags


class ThumbnailGenerationError(Exception):
    """Raised when FFmpeg cannot generate a video thumbnail."""


class FFmpegThumbnailGenerator:
    def __init__(
        self,
        executable: str = "ffmpeg",
        width: int = 640,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.executable = executable
        self.width = width
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        video_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        source = Path(video_path).expanduser().resolve()
        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        scale_filter = (
            f"scale={self.width}:-2:force_original_aspect_ratio=decrease"
        )
        command = [
            self.executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "0",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-frames:v",
            "1",
            "-vf",
            scale_filter,
            "-q:v",
            "3",
            str(output),
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
            raise ThumbnailGenerationError(
                f"找不到 FFmpeg 可执行文件：{self.executable}"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise ThumbnailGenerationError("FFmpeg 缩略图生成超时") from error
        except OSError as error:
            raise ThumbnailGenerationError(
                f"无法启动 FFmpeg：{error}"
            ) from error

        if result.returncode != 0 or not output.is_file():
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
            detail = result.stderr.strip() or "FFmpeg 未生成缩略图"
            raise ThumbnailGenerationError(detail)

        return output
