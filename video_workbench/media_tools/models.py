from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum


class MediaOperation(str, Enum):
    CONVERT_AUDIO = "convert_audio"
    CONVERT_VIDEO = "convert_video"
    EXTRACT_AUDIO = "extract_audio"
    TRIM_VIDEO = "trim_video"
    TRIM_AUDIO = "trim_audio"
    RESIZE_VIDEO = "resize_video"
    ADJUST_VOLUME = "adjust_volume"


class MediaTaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True, slots=True)
class MediaToolRequest:
    operation: MediaOperation
    source_path: str
    output_directory: str
    output_extension: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    volume_db: float | None = None


@dataclass(frozen=True, slots=True)
class MediaTask:
    task_id: str
    title: str
    request: MediaToolRequest
    command: tuple[str, ...]
    output_path: str
    status: MediaTaskStatus = MediaTaskStatus.QUEUED
    error: str | None = None
    material_id: str | None = None
    library_error: str | None = None
    add_to_library: bool = False
    project_root: str | None = None
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None

    def changed(self, **changes: object) -> "MediaTask":
        return replace(self, **changes)


def now_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
