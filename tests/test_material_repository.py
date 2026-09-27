from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from video_workbench.materials import (
    MATERIAL_INDEX_FILE_NAME,
    MaterialRecord,
    MaterialRepository,
    MaterialRepositoryError,
    MaterialStatus,
    MediaType,
)
from video_workbench.project import create_project


def make_record(
    material_id: str = "material-1",
    path: str = "I:\\素材\\clip.mp4",
    media_type: MediaType = MediaType.VIDEO,
) -> MaterialRecord:
    return MaterialRecord(
        material_id=material_id,
        name=Path(path).name,
        path=path,
        media_type=media_type,
        status=MaterialStatus.READY,
        size_bytes=1024,
        duration_seconds=12.5,
        width=1920,
        height=1080,
        codec="h264",
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        tags=["口播", "待剪辑"],
        imported_at="2026-09-27T20:00:00+08:00",
    )


class MaterialRepositoryTests(unittest.TestCase):
    def test_create_read_and_update_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = create_project(Path(temporary_directory) / "素材项目")
            repository = MaterialRepository(project)

            repository.save([make_record()])
            loaded = repository.load()
            self.assertEqual(loaded, [make_record()])
            self.assertTrue(repository.index_path.is_file())
            self.assertEqual(
                repository.index_path.name,
                MATERIAL_INDEX_FILE_NAME,
            )
            self.assertFalse(
                repository.index_path.with_suffix(".json.tmp").exists()
            )

            repository.add(
                make_record(
                    material_id="material-2",
                    path="I:\\素材\\music.wav",
                    media_type=MediaType.AUDIO,
                )
            )
            self.assertEqual(len(repository.load()), 2)

            records, removed = repository.remove("material-1")
            self.assertTrue(removed)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].material_id, "material-2")

    def test_index_is_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = create_project(Path(temporary_directory) / "中文项目")
            repository = MaterialRepository(project)
            repository.save([make_record()])

            raw_text = repository.index_path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)

            self.assertIn("待剪辑", raw_text)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["materials"][0]["name"], "clip.mp4")

    def test_invalid_index_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = create_project(Path(temporary_directory) / "损坏索引项目")
            repository = MaterialRepository(project)
            repository.index_path.write_text("{not json", encoding="utf-8")

            with self.assertRaises(MaterialRepositoryError):
                repository.load()

    def test_remove_record_does_not_delete_media_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "素材项目")
            source = root / "保留在磁盘.mp4"
            source.write_bytes(b"test")
            repository = MaterialRepository(project)
            repository.save([make_record(path=str(source))])

            repository.remove("material-1")

            self.assertTrue(source.is_file())


if __name__ == "__main__":
    unittest.main()
