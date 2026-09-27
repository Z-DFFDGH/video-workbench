from __future__ import annotations

import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class FFmpegRunError(Exception):
    """Raised when FFmpeg exits with an error or cannot be started."""


class FFmpegCanceled(Exception):
    """Raised after a running FFmpeg process has been canceled."""


@dataclass(frozen=True, slots=True)
class FFmpegRunResult:
    returncode: int
    stdout: str
    stderr: str


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _cleanup_output(path: str | Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


class FFmpegRunner:
    def __init__(self, executable: str = "ffmpeg") -> None:
        self.executable = executable

    def validate_executable(self) -> str:
        located = shutil.which(self.executable)
        if located is None:
            raise FFmpegRunError(
                f"找不到 FFmpeg 可执行文件：{self.executable}"
            )
        return located

    def run(
        self,
        command: Sequence[str],
        cancel_event: threading.Event,
        output_path: str | Path,
    ) -> FFmpegRunResult:
        self.validate_executable()
        arguments = [str(argument) for argument in command]
        if not arguments:
            raise FFmpegRunError("FFmpeg 命令不能为空")

        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            process = subprocess.Popen(
                arguments,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_creation_flags(),
            )
        except FileNotFoundError as error:
            raise FFmpegRunError(
                f"找不到 FFmpeg 可执行文件：{arguments[0]}"
            ) from error
        except OSError as error:
            raise FFmpegRunError(f"无法启动 FFmpeg：{error}") from error

        stdout = ""
        stderr = ""
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.15)
                break
            except subprocess.TimeoutExpired:
                if not cancel_event.is_set():
                    continue
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                _cleanup_output(output)
                raise FFmpegCanceled("FFmpeg 任务已取消")

        result = FFmpegRunResult(
            returncode=process.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
        )
        if result.returncode != 0:
            _cleanup_output(output)
            detail = result.stderr.strip() or "FFmpeg 返回未知错误"
            raise FFmpegRunError(detail[:2000])
        if not output.is_file():
            _cleanup_output(output)
            raise FFmpegRunError("FFmpeg 未生成输出文件")
        return result
