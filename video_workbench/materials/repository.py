from __future__ import annotations

import json
import os
from pathlib import Path

from video_workbench.project import ProjectInfo

from .models import MaterialRecord

MATERIAL_INDEX_FILE_NAME = "materials.json"
MATERIAL_INDEX_SCHEMA_VERSION = 1
THUMBNAIL_CACHE_DIRECTORY = Path(".cache") / "thumbnails"


class MaterialRepositoryError(Exception):
    """Raised when the material index cannot be read or written."""


class MaterialRepository:
    """Persist material records in UTF-8 JSON inside a project directory."""

    def __init__(self, project: ProjectInfo | str | Path) -> None:
        self.project_root = (
            project.root if isinstance(project, ProjectInfo) else Path(project)
        ).expanduser().resolve()
        self.index_path = self.project_root / MATERIAL_INDEX_FILE_NAME
        self.thumbnail_directory = (
            self.project_root / THUMBNAIL_CACHE_DIRECTORY
        )

    def load(self) -> list[MaterialRecord]:
        if not self.index_path.exists():
            return []

        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise MaterialRepositoryError(
                f"无法读取素材索引：{self.index_path}"
            ) from error

        if not isinstance(payload, dict):
            raise MaterialRepositoryError("素材索引根节点必须是 JSON 对象")
        if payload.get("schema_version") != MATERIAL_INDEX_SCHEMA_VERSION:
            raise MaterialRepositoryError(
                f"不支持的素材索引版本：{payload.get('schema_version')!r}"
            )

        records_payload = payload.get("materials")
        if not isinstance(records_payload, list):
            raise MaterialRepositoryError("素材索引缺少 materials 列表")

        records: list[MaterialRecord] = []
        for index, record_payload in enumerate(records_payload):
            try:
                records.append(MaterialRecord.from_dict(record_payload))
            except ValueError as error:
                raise MaterialRepositoryError(
                    f"第 {index + 1} 条素材记录无效：{error}"
                ) from error
        return records

    def save(self, records: list[MaterialRecord]) -> None:
        payload = {
            "schema_version": MATERIAL_INDEX_SCHEMA_VERSION,
            "materials": [record.to_dict() for record in records],
        }
        temporary_path = self.index_path.with_suffix(".json.tmp")
        try:
            self.project_root.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, self.index_path)
        except OSError as error:
            raise MaterialRepositoryError(
                f"无法保存素材索引：{self.index_path}"
            ) from error

    def add(self, record: MaterialRecord) -> list[MaterialRecord]:
        records = self.load()
        records.append(record)
        self.save(records)
        return records

    def remove(self, material_id: str) -> tuple[list[MaterialRecord], bool]:
        records = self.load()
        filtered = [
            record
            for record in records
            if record.material_id != material_id
        ]
        removed = len(filtered) != len(records)
        if removed:
            self.save(filtered)
        return filtered, removed

    def replace(self, records: list[MaterialRecord]) -> None:
        self.save(records)
