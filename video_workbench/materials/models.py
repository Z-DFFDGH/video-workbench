from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    UNKNOWN = "unknown"


class MaterialStatus(str, Enum):
    READY = "ready"
    ERROR = "error"


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        clean_tag = tag.strip()
        key = clean_tag.casefold()
        if not clean_tag or key in seen:
            continue
        seen.add(key)
        normalized.append(clean_tag)
    return normalized


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    media_type: MediaType
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    codec: str | None = None
    format_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "media_type": self.media_type.value,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "codec": self.codec,
            "format_name": self.format_name,
        }


@dataclass(slots=True)
class MaterialRecord:
    material_id: str
    name: str
    path: str
    media_type: MediaType
    status: MaterialStatus = MaterialStatus.READY
    size_bytes: int = 0
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    codec: str | None = None
    format_name: str | None = None
    thumbnail_path: str | None = None
    tags: list[str] = field(default_factory=list)
    error: str | None = None
    imported_at: str = ""
    copied: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "material_id": self.material_id,
            "name": self.name,
            "path": self.path,
            "media_type": self.media_type.value,
            "status": self.status.value,
            "size_bytes": self.size_bytes,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "codec": self.codec,
            "format_name": self.format_name,
            "thumbnail_path": self.thumbnail_path,
            "tags": list(self.tags),
            "error": self.error,
            "imported_at": self.imported_at,
            "copied": self.copied,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "MaterialRecord":
        if not isinstance(payload, dict):
            raise ValueError("素材记录必须是 JSON 对象")

        required_string_fields = ("material_id", "name", "path", "imported_at")
        for field_name in required_string_fields:
            value = payload.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"素材记录缺少有效字段：{field_name}")

        tags = payload.get("tags", [])
        if not isinstance(tags, list) or any(
            not isinstance(tag, str) for tag in tags
        ):
            raise ValueError("素材 tags 必须是字符串列表")

        thumbnail_path = payload.get("thumbnail_path")
        if thumbnail_path is not None and not isinstance(thumbnail_path, str):
            raise ValueError("thumbnail_path 必须是字符串或 null")

        error = payload.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError("error 必须是字符串或 null")

        return cls(
            material_id=str(payload["material_id"]),
            name=str(payload["name"]),
            path=str(payload["path"]),
            media_type=MediaType(str(payload.get("media_type", ""))),
            status=MaterialStatus(str(payload.get("status", ""))),
            size_bytes=int(payload.get("size_bytes", 0)),
            duration_seconds=_optional_float(payload.get("duration_seconds")),
            width=_optional_int(payload.get("width")),
            height=_optional_int(payload.get("height")),
            codec=_optional_string(payload.get("codec")),
            format_name=_optional_string(payload.get("format_name")),
            thumbnail_path=thumbnail_path,
            tags=normalize_tags(tags),
            error=error,
            imported_at=str(payload["imported_at"]),
            copied=bool(payload.get("copied", False)),
        )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("可空文本字段格式无效")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("浮点字段格式无效")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("浮点字段格式无效") from error


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("整数字段格式无效")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("整数字段格式无效") from error
