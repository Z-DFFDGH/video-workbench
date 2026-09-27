from __future__ import annotations

import math
from pathlib import Path

from .models import MediaOperation, MediaToolRequest

AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


class MediaCommandError(ValueError):
    """Raised when media tool parameters cannot form a safe FFmpeg command."""


def normalize_extension(value: str) -> str:
    extension = value.strip().lower()
    if extension and not extension.startswith("."):
        extension = f".{extension}"
    return extension


def _source_path(value: str | Path) -> Path:
    source = Path(value).expanduser().resolve()
    if not source.is_file():
        raise MediaCommandError(f"输入文件不存在：{source}")
    return source


def _output_directory(value: str | Path) -> Path:
    directory = Path(value).expanduser().resolve()
    if directory.exists() and not directory.is_dir():
        raise MediaCommandError(f"输出位置不是文件夹：{directory}")
    return directory


def _media_kind(extension: str) -> str:
    if extension in AUDIO_EXTENSIONS:
        return "audio"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    raise MediaCommandError(f"不支持的媒体扩展名：{extension or '无'}")


def parse_timecode(value: str, field_name: str = "时间") -> float:
    text = value.strip()
    if not text:
        raise MediaCommandError(f"{field_name}不能为空")

    if ":" in text:
        parts = text.split(":")
        if len(parts) not in {2, 3} or any(not part.strip() for part in parts):
            raise MediaCommandError(f"{field_name}格式无效，请使用 MM:SS 或 HH:MM:SS")
        try:
            numbers = [float(part) for part in parts]
        except ValueError as error:
            raise MediaCommandError(f"{field_name}格式无效") from error
        if any(number < 0 for number in numbers):
            raise MediaCommandError(f"{field_name}不能为负数")
        if numbers[-1] >= 60 or (len(numbers) == 3 and numbers[-2] >= 60):
            raise MediaCommandError(f"{field_name}中的分钟和秒必须小于 60")
        seconds = 0.0
        for number in numbers:
            seconds = seconds * 60 + number
        return seconds

    try:
        seconds = float(text)
    except ValueError as error:
        raise MediaCommandError(f"{field_name}格式无效") from error
    if not math.isfinite(seconds) or seconds < 0:
        raise MediaCommandError(f"{field_name}必须是非负数字")
    return seconds


def validate_dimensions(width: int, height: int) -> tuple[int, int]:
    if isinstance(width, bool) or isinstance(height, bool):
        raise MediaCommandError("视频宽高必须是正整数")
    if width <= 0 or height <= 0:
        raise MediaCommandError("视频宽高必须大于 0")
    if width > 7680 or height > 7680:
        raise MediaCommandError("视频宽高不能超过 7680")
    if width % 2 or height % 2:
        raise MediaCommandError("视频宽高必须是偶数")
    return width, height


def validate_volume_db(value: float) -> float:
    try:
        decibels = float(value)
    except (TypeError, ValueError) as error:
        raise MediaCommandError("音量分贝值无效") from error
    if not math.isfinite(decibels):
        raise MediaCommandError("音量分贝值无效")
    if decibels < -60 or decibels > 60:
        raise MediaCommandError("音量分贝值必须在 -60 dB 到 +60 dB 之间")
    return decibels


def conversion_request(
    source_path: str | Path,
    output_directory: str | Path,
    target_extension: str,
) -> MediaToolRequest:
    source = _source_path(source_path)
    directory = _output_directory(output_directory)
    source_extension = source.suffix.lower()
    source_kind = _media_kind(source_extension)
    target = normalize_extension(target_extension)
    target_kind = _media_kind(target)
    if target == source_extension:
        raise MediaCommandError("请选择与输入文件不同的目标格式")

    if source_kind == "video" and target_kind == "audio":
        operation = MediaOperation.EXTRACT_AUDIO
    elif source_kind == "audio" and target_kind == "audio":
        operation = MediaOperation.CONVERT_AUDIO
    elif source_kind == "video" and target_kind == "video":
        operation = MediaOperation.CONVERT_VIDEO
    else:
        raise MediaCommandError("音频不能转换为视频格式")

    return MediaToolRequest(
        operation=operation,
        source_path=str(source),
        output_directory=str(directory),
        output_extension=target,
    )


def trim_request(
    source_path: str | Path,
    output_directory: str | Path,
    start_time: str,
    end_time: str,
) -> MediaToolRequest:
    source = _source_path(source_path)
    directory = _output_directory(output_directory)
    extension = source.suffix.lower()
    source_kind = _media_kind(extension)
    start_seconds = parse_timecode(start_time, "开始时间")
    end_seconds = parse_timecode(end_time, "结束时间")
    if end_seconds <= start_seconds:
        raise MediaCommandError("结束时间必须大于开始时间")

    return MediaToolRequest(
        operation=(
            MediaOperation.TRIM_VIDEO
            if source_kind == "video"
            else MediaOperation.TRIM_AUDIO
        ),
        source_path=str(source),
        output_directory=str(directory),
        output_extension=extension,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )


def resize_request(
    source_path: str | Path,
    output_directory: str | Path,
    width: int,
    height: int,
) -> MediaToolRequest:
    source = _source_path(source_path)
    directory = _output_directory(output_directory)
    extension = source.suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise MediaCommandError("分辨率处理只支持视频文件")
    clean_width, clean_height = validate_dimensions(width, height)
    return MediaToolRequest(
        operation=MediaOperation.RESIZE_VIDEO,
        source_path=str(source),
        output_directory=str(directory),
        output_extension=extension,
        width=clean_width,
        height=clean_height,
    )


def volume_request(
    source_path: str | Path,
    output_directory: str | Path,
    volume_db: float,
) -> MediaToolRequest:
    source = _source_path(source_path)
    directory = _output_directory(output_directory)
    extension = source.suffix.lower()
    if extension not in AUDIO_EXTENSIONS:
        raise MediaCommandError("音量调整 v1 只支持音频文件")
    return MediaToolRequest(
        operation=MediaOperation.ADJUST_VOLUME,
        source_path=str(source),
        output_directory=str(directory),
        output_extension=extension,
        volume_db=validate_volume_db(volume_db),
    )


def validate_request(request: MediaToolRequest) -> None:
    source = _source_path(request.source_path)
    _output_directory(request.output_directory)
    extension = normalize_extension(request.output_extension)

    if request.operation in {
        MediaOperation.CONVERT_AUDIO,
        MediaOperation.CONVERT_VIDEO,
        MediaOperation.EXTRACT_AUDIO,
    }:
        if request.operation == MediaOperation.CONVERT_AUDIO:
            if source.suffix.lower() not in AUDIO_EXTENSIONS:
                raise MediaCommandError("音频转换需要音频输入文件")
            if extension not in AUDIO_EXTENSIONS:
                raise MediaCommandError("音频转换目标必须是 MP3、WAV、AAC 或 FLAC")
        elif request.operation == MediaOperation.CONVERT_VIDEO:
            if source.suffix.lower() not in VIDEO_EXTENSIONS:
                raise MediaCommandError("视频转换需要视频输入文件")
            if extension not in VIDEO_EXTENSIONS:
                raise MediaCommandError("视频转换目标必须是 MP4、MOV、MKV 或 WEBM")
        else:
            if source.suffix.lower() not in VIDEO_EXTENSIONS:
                raise MediaCommandError("音频提取需要视频输入文件")
            if extension not in AUDIO_EXTENSIONS:
                raise MediaCommandError("音频提取目标必须是 MP3、WAV、AAC 或 FLAC")
        return

    if request.operation in {MediaOperation.TRIM_VIDEO, MediaOperation.TRIM_AUDIO}:
        expected_kind = (
            VIDEO_EXTENSIONS
            if request.operation == MediaOperation.TRIM_VIDEO
            else AUDIO_EXTENSIONS
        )
        if source.suffix.lower() not in expected_kind or extension not in expected_kind:
            raise MediaCommandError("裁剪输入类型与处理方式不匹配")
        if request.start_seconds is None or request.end_seconds is None:
            raise MediaCommandError("裁剪需要开始时间和结束时间")
        if request.start_seconds < 0:
            raise MediaCommandError("开始时间不能为负数")
        if request.end_seconds <= request.start_seconds:
            raise MediaCommandError("结束时间必须大于开始时间")
        return

    if request.operation == MediaOperation.RESIZE_VIDEO:
        if source.suffix.lower() not in VIDEO_EXTENSIONS or extension not in VIDEO_EXTENSIONS:
            raise MediaCommandError("分辨率处理只支持视频文件")
        if request.width is None or request.height is None:
            raise MediaCommandError("分辨率处理需要宽高参数")
        validate_dimensions(request.width, request.height)
        return

    if request.operation == MediaOperation.ADJUST_VOLUME:
        if source.suffix.lower() not in AUDIO_EXTENSIONS or extension not in AUDIO_EXTENSIONS:
            raise MediaCommandError("音量调整 v1 只支持音频文件")
        if request.volume_db is None:
            raise MediaCommandError("音量调整需要分贝值")
        validate_volume_db(request.volume_db)
        return

    raise MediaCommandError(f"不支持的媒体处理操作：{request.operation}")


def _audio_codec_args(extension: str) -> list[str]:
    extension = normalize_extension(extension)
    if extension == ".mp3":
        return ["-c:a", "libmp3lame", "-q:a", "2"]
    if extension == ".wav":
        return ["-c:a", "pcm_s16le"]
    if extension == ".aac":
        return ["-c:a", "aac", "-b:a", "192k", "-f", "adts"]
    if extension == ".flac":
        return ["-c:a", "flac"]
    raise MediaCommandError(f"不支持的目标音频格式：{extension}")


def _video_codec_args(extension: str) -> list[str]:
    extension = normalize_extension(extension)
    if extension in {".mp4", ".mov", ".mkv"}:
        arguments = [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
        ]
        if extension in {".mp4", ".mov"}:
            arguments.extend(["-movflags", "+faststart"])
        return arguments
    if extension == ".webm":
        return [
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "32",
            "-b:v",
            "0",
            "-c:a",
            "libopus",
            "-b:a",
            "160k",
        ]
    raise MediaCommandError(f"不支持的目标视频格式：{extension}")


def _format_seconds(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def build_ffmpeg_command(
    request: MediaToolRequest,
    output_path: str | Path,
    executable: str = "ffmpeg",
) -> list[str]:
    validate_request(request)
    source = str(Path(request.source_path).expanduser().resolve())
    output = str(Path(output_path).expanduser().resolve())
    extension = normalize_extension(request.output_extension)

    command = [executable, "-hide_banner", "-loglevel", "error", "-y"]
    if request.operation in {MediaOperation.TRIM_VIDEO, MediaOperation.TRIM_AUDIO}:
        duration = request.end_seconds - request.start_seconds
        command.extend(
            [
                "-ss",
                _format_seconds(request.start_seconds),
                "-i",
                source,
                "-t",
                _format_seconds(duration),
            ]
        )
    else:
        command.extend(["-i", source])

    if request.operation in {
        MediaOperation.CONVERT_AUDIO,
        MediaOperation.EXTRACT_AUDIO,
        MediaOperation.TRIM_AUDIO,
    }:
        command.append("-vn")
        command.extend(_audio_codec_args(extension))
    elif request.operation in {
        MediaOperation.CONVERT_VIDEO,
        MediaOperation.TRIM_VIDEO,
    }:
        command.extend(_video_codec_args(extension))
    elif request.operation == MediaOperation.RESIZE_VIDEO:
        width = request.width
        height = request.height
        command.extend(["-map", "0:v:0", "-map", "0:a?"])
        command.extend(
            [
                "-vf",
                (
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
                ),
            ]
        )
        command.extend(_video_codec_args(extension))
    elif request.operation == MediaOperation.ADJUST_VOLUME:
        command.extend(
            [
                "-vn",
                "-af",
                f"volume={request.volume_db:+g}dB",
                *_audio_codec_args(extension),
            ]
        )

    command.append(output)
    return command


def output_stem(request: MediaToolRequest) -> str:
    source_stem = Path(request.source_path).stem
    if request.operation in {
        MediaOperation.TRIM_VIDEO,
        MediaOperation.TRIM_AUDIO,
    }:
        return f"{source_stem}_trimmed"
    if request.operation == MediaOperation.RESIZE_VIDEO:
        return f"{source_stem}_resized"
    if request.operation == MediaOperation.ADJUST_VOLUME:
        return f"{source_stem}_volume"
    return source_stem
