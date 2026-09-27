from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from threading import Event

from .errors import DownloadCanceled, DownloadError


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FFmpegAudioExtractor:
    def __init__(
        self,
        executable: str = "ffmpeg",
        timeout_seconds: float = 1800.0,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def extract(
        self,
        media_path: str | Path,
        output_path: str | Path,
        cancel_event: Event | None = None,
    ) -> Path:
        source = Path(media_path).expanduser().resolve()
        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        command = [
            self.executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-map",
            "0:a:0",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output),
        ]

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_creation_flags(),
            )
        except FileNotFoundError as error:
            raise DownloadError(
                f"找不到 FFmpeg 可执行文件：{self.executable}"
            ) from error
        except OSError as error:
            raise DownloadError(f"无法启动 FFmpeg：{error}") from error

        started_at = time.monotonic()
        try:
            while process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    self._terminate(process)
                    raise DownloadCanceled("音频提取已取消")
                if time.monotonic() - started_at > self.timeout_seconds:
                    self._terminate(process)
                    raise DownloadError("FFmpeg 音频提取超时")
                time.sleep(0.1)
            stdout, stderr = process.communicate(timeout=5)
        except BaseException:
            self._terminate(process)
            output.unlink(missing_ok=True)
            raise

        if process.returncode != 0 or not output.is_file():
            output.unlink(missing_ok=True)
            detail = (stderr or stdout).strip() or "FFmpeg 未生成音频文件"
            raise DownloadError(detail)

        return output

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
