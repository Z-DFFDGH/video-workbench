from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_SCHEMA_VERSION = 4
CONFIG_FILE_NAME = "config.json"


class ConfigError(Exception):
    """Raised when the application configuration cannot be written."""


def _normalize_recent_projects(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        path = str(Path(item).expanduser().resolve())
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(path)
    return normalized


@dataclass(slots=True)
class AppConfig:
    schema_version: int = CONFIG_SCHEMA_VERSION
    wallpaper_path: str | None = None
    recent_projects: list[str] = field(default_factory=list)
    download_directory: str | None = None
    media_output_directory: str | None = None

    @classmethod
    def from_dict(cls, payload: object) -> "AppConfig":
        if not isinstance(payload, dict):
            return cls()

        wallpaper_path = payload.get("wallpaper_path")
        if not isinstance(wallpaper_path, str) or not wallpaper_path.strip():
            wallpaper_path = None

        download_directory = payload.get("download_directory")
        if not isinstance(download_directory, str) or not download_directory.strip():
            download_directory = None

        media_output_directory = payload.get("media_output_directory")
        if (
            not isinstance(media_output_directory, str)
            or not media_output_directory.strip()
        ):
            media_output_directory = None

        return cls(
            schema_version=CONFIG_SCHEMA_VERSION,
            wallpaper_path=wallpaper_path,
            download_directory=download_directory,
            media_output_directory=media_output_directory,
            recent_projects=_normalize_recent_projects(
                payload.get("recent_projects", [])
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "LocalVideoWorkbench" / CONFIG_FILE_NAME
    return Path.home() / ".local_video_workbench" / CONFIG_FILE_NAME


class ConfigStore:
    """Read and atomically write the local application configuration."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            config = AppConfig()
            try:
                self.save(config)
            except ConfigError:
                pass
            return config

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return AppConfig()

        return AppConfig.from_dict(payload)

    def save(self, config: AppConfig) -> None:
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise ConfigError(f"无法保存应用配置：{error}") from error
