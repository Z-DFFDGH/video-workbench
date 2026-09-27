from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse

URL_PATTERN = re.compile(r"https?://[^\s,，；;]+", re.IGNORECASE)
TRAILING_URL_CHARACTERS = "。．.！？!?）)]}】》>\"'"


class DownloadMode(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True, slots=True)
class InvalidInputLine:
    line_number: int
    content: str
    reason: str


@dataclass(frozen=True, slots=True)
class InputValidation:
    urls: tuple[str, ...]
    invalid_lines: tuple[InvalidInputLine, ...]


@dataclass(frozen=True, slots=True)
class DownloadTask:
    task_id: str
    source_url: str
    output_directory: str
    mode: DownloadMode
    status: DownloadStatus = DownloadStatus.QUEUED
    output_path: str | None = None
    error: str | None = None
    material_id: str | None = None
    library_error: str | None = None
    add_to_library: bool = False
    project_root: str | None = None
    attempt_count: int = 0
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None

    def changed(self, **changes: object) -> "DownloadTask":
        return replace(self, **changes)


def now_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean_url(value: str) -> str:
    return value.strip().rstrip(TRAILING_URL_CHARACTERS)


def parse_link_input(raw_text: str) -> InputValidation:
    """Parse one HTTP(S) URL per non-empty input line."""
    urls: list[str] = []
    invalid_lines: list[InvalidInputLine] = []
    seen: set[str] = set()

    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        matches = URL_PATTERN.findall(line)
        if len(matches) != 1:
            reason = "未检测到链接" if not matches else "每行只能包含一个链接"
            invalid_lines.append(
                InvalidInputLine(
                    line_number=line_number,
                    content=line,
                    reason=reason,
                )
            )
            continue

        url = clean_url(matches[0])
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            invalid_lines.append(
                InvalidInputLine(
                    line_number=line_number,
                    content=line,
                    reason="链接格式无效",
                )
            )
            continue

        if url not in seen:
            seen.add(url)
            urls.append(url)

    return InputValidation(
        urls=tuple(urls),
        invalid_lines=tuple(invalid_lines),
    )
