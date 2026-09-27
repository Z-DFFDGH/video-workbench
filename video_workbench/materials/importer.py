from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from video_workbench.project import PROJECT_DIRECTORIES, ProjectInfo

from .metadata import FFprobeDetector, MediaDetectionError
from .models import (
    MaterialRecord,
    MaterialStatus,
    MediaType,
    normalize_tags,
)
from .repository import MaterialRepository
from .thumbnails import FFmpegThumbnailGenerator, ThumbnailGenerationError

MATERIAL_DIRECTORIES = {
    MediaType.VIDEO: PROJECT_DIRECTORIES["source_materials"],
    MediaType.AUDIO: PROJECT_DIRECTORIES["audio"],
    MediaType.IMAGE: PROJECT_DIRECTORIES["images"],
}


class MaterialImportError(Exception):
    """Raised when a local file cannot be added to the material library."""


class MaterialNotFoundError(Exception):
    """Raised when a material record does not exist."""


def unique_destination(directory: str | Path, file_name: str) -> Path:
    directory_path = Path(directory)
    original = Path(file_name)
    candidate = directory_path / original.name
    counter = 1
    while candidate.exists():
        candidate = directory_path / (
            f"{original.stem}_{counter}{original.suffix}"
        )
        counter += 1
    return candidate


def copy_material_file(
    source_path: str | Path,
    media_type: MediaType,
    project_root: str | Path,
) -> Path:
    directory_name = MATERIAL_DIRECTORIES.get(media_type)
    if directory_name is None:
        raise MaterialImportError("无法为未知素材类型选择项目目录")

    source = Path(source_path).expanduser().resolve()
    destination_directory = Path(project_root).expanduser().resolve() / directory_name
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(destination_directory, source.name)
    try:
        shutil.copy2(source, destination)
    except OSError as error:
        raise MaterialImportError(f"无法复制素材：{source}") from error
    return destination.resolve()


class MaterialLibrary:
    def __init__(
        self,
        project: ProjectInfo | str | Path,
        detector: FFprobeDetector | None = None,
        thumbnail_generator: FFmpegThumbnailGenerator | None = None,
        repository: MaterialRepository | None = None,
    ) -> None:
        self.project_root = (
            project.root if isinstance(project, ProjectInfo) else Path(project)
        ).expanduser().resolve()
        self.repository = repository or MaterialRepository(self.project_root)
        self.detector = detector or FFprobeDetector()
        self.thumbnail_generator = (
            thumbnail_generator or FFmpegThumbnailGenerator()
        )
        self._materials = self.repository.load()

    @property
    def materials(self) -> list[MaterialRecord]:
        return list(self._materials)

    def get_material(self, material_id: str) -> MaterialRecord:
        for material in self._materials:
            if material.material_id == material_id:
                return material
        raise MaterialNotFoundError(f"素材记录不存在：{material_id}")

    def import_file(
        self,
        source_path: str | Path,
        copy_to_project: bool = False,
        generate_thumbnail: bool = True,
    ) -> MaterialRecord:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise MaterialImportError(f"素材文件不存在：{source}")

        try:
            size_bytes = source.stat().st_size
        except OSError as error:
            raise MaterialImportError(f"无法读取素材信息：{source}") from error

        material_id = uuid4().hex
        imported_at = datetime.now().astimezone().isoformat(timespec="seconds")

        try:
            metadata = self.detector.detect(source)
        except MediaDetectionError as error:
            record = MaterialRecord(
                material_id=material_id,
                name=source.name,
                path=str(source),
                media_type=MediaType.UNKNOWN,
                status=MaterialStatus.ERROR,
                size_bytes=size_bytes,
                error=str(error)[:1000],
                imported_at=imported_at,
            )
            self._append(record)
            return record

        record_path = source
        copied = False
        if copy_to_project:
            record_path = copy_material_file(
                source,
                metadata.media_type,
                self.project_root,
            )
            copied = True

        record = MaterialRecord(
            material_id=material_id,
            name=record_path.name,
            path=str(record_path),
            media_type=metadata.media_type,
            status=MaterialStatus.READY,
            size_bytes=size_bytes,
            duration_seconds=metadata.duration_seconds,
            width=metadata.width,
            height=metadata.height,
            codec=metadata.codec,
            format_name=metadata.format_name,
            imported_at=imported_at,
            copied=copied,
        )

        if metadata.media_type == MediaType.VIDEO and generate_thumbnail:
            thumbnail_path = (
                self.repository.thumbnail_directory
                / f"{material_id}.jpg"
            )
            try:
                generated = self.thumbnail_generator.generate(
                    record_path,
                    thumbnail_path,
                )
            except ThumbnailGenerationError as error:
                record.error = f"缩略图生成失败：{error}"[:1000]
            else:
                record.thumbnail_path = str(generated.resolve())

        self._append(record)
        return record

    def remove_material(self, material_id: str) -> bool:
        records, removed = self.repository.remove(material_id)
        if removed:
            self._materials = records
        return removed

    def add_tag(self, material_id: str, tag: str) -> MaterialRecord:
        clean_tag = tag.strip()
        if not clean_tag:
            raise ValueError("标签不能为空")

        record = self.get_material(material_id)
        record.tags = normalize_tags([*record.tags, clean_tag])
        self._save()
        return record

    def remove_tag(self, material_id: str, tag: str) -> MaterialRecord:
        key = tag.strip().casefold()
        record = self.get_material(material_id)
        record.tags = [
            existing_tag
            for existing_tag in record.tags
            if existing_tag.casefold() != key
        ]
        self._save()
        return record

    def search(self, query: str) -> list[MaterialRecord]:
        needle = query.strip().casefold()
        if not needle:
            return list(self._materials)
        return [
            material
            for material in self._materials
            if needle in material.name.casefold()
            or any(needle in tag.casefold() for tag in material.tags)
        ]

    def _append(self, record: MaterialRecord) -> None:
        self._materials.append(record)
        self._save()

    def _save(self) -> None:
        self.repository.replace(self._materials)
