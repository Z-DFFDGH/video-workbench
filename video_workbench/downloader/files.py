from __future__ import annotations

import re
from pathlib import Path

INVALID_FILENAME_CHARACTERS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def sanitize_filename(value: str, default: str = "download") -> str:
    clean = INVALID_FILENAME_CHARACTERS.sub("_", value).strip(" .")
    if not clean:
        clean = default
    return clean[:120]


def unique_destination(directory: str | Path, file_name: str) -> Path:
    directory_path = Path(directory).expanduser().resolve()
    original = Path(file_name)
    candidate = directory_path / original.name
    counter = 1
    while candidate.exists():
        candidate = directory_path / (
            f"{original.stem}_{counter}{original.suffix}"
        )
        counter += 1
    return candidate
