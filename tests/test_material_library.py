from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from video_workbench.materials import (
    MaterialLibrary,
    MaterialRepository,
    MaterialStatus,
    MediaDetectionError,
    MediaMetadata,
    MediaType,
)
from video_workbench.project import create_project


class StubDetector:
    def detect(self, media_path: str | Path) -> MediaMetadata:
        suffix = Path(media_path).suffix.lower()
        if suffix == ".bad":
            raise MediaDetectionError("测试损坏媒体")
        if suffix in {".mp4", ".mov", ".mkv", ".webm"}:
            return MediaMetadata(
                media_type=MediaType.VIDEO,
                duration_seconds=3.0,
                width=1280,
                height=720,
                codec="h264",
                format_name="mov,mp4",
            )
        if suffix in {".mp3", ".wav", ".aac", ".flac"}:
            return MediaMetadata(
                media_type=MediaType.AUDIO,
                duration_seconds=5.0,
                codec="pcm_s16le",
                format_name="wav",
            )
        return MediaMetadata(
            media_type=MediaType.IMAGE,
            width=800,
            height=600,
            codec="png",
            format_name="png_pipe",
        )


class StubThumbnailGenerator:
    def generate(
        self,
        video_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"thumbnail")
        return output


class MaterialLibraryTests(unittest.TestCase):
    def make_library(self, project) -> MaterialLibrary:
        return MaterialLibrary(
            project,
            detector=StubDetector(),
            thumbnail_generator=StubThumbnailGenerator(),
        )

    def test_import_defaults_to_path_only_and_generates_thumbnail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "项目")
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            library = self.make_library(project)

            record = library.import_file(source)

            self.assertFalse(record.copied)
            self.assertEqual(record.path, str(source.resolve()))
            self.assertEqual(record.status, MaterialStatus.READY)
            self.assertEqual(record.media_type, MediaType.VIDEO)
            self.assertIsNotNone(record.thumbnail_path)
            self.assertTrue(Path(record.thumbnail_path).is_file())
            self.assertTrue(source.is_file())

    def test_copy_mode_uses_type_directory_and_unique_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "项目")
            first_source = root / "one" / "clip.mp4"
            second_source = root / "two" / "clip.mp4"
            first_source.parent.mkdir()
            second_source.parent.mkdir()
            first_source.write_bytes(b"first")
            second_source.write_bytes(b"second")
            library = self.make_library(project)

            first = library.import_file(
                first_source,
                copy_to_project=True,
                generate_thumbnail=False,
            )
            second = library.import_file(
                second_source,
                copy_to_project=True,
                generate_thumbnail=False,
            )

            source_directory = project.root / "原素材"
            self.assertEqual(
                Path(first.path).parent,
                source_directory.resolve(),
            )
            self.assertEqual(Path(first.path).name, "clip.mp4")
            self.assertEqual(Path(second.path).name, "clip_1.mp4")
            self.assertEqual(Path(second.path).read_bytes(), b"second")
            self.assertTrue(first.copied)
            self.assertTrue(second.copied)

    def test_tag_search_is_case_insensitive_substring_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "项目")
            first_source = root / "clip_final.mp4"
            second_source = root / "cover.png"
            first_source.write_bytes(b"video")
            second_source.write_bytes(b"image")
            library = self.make_library(project)
            first = library.import_file(first_source, generate_thumbnail=False)
            second = library.import_file(second_source)
            library.add_tag(first.material_id, "口播")
            library.add_tag(first.material_id, "Interview")
            library.add_tag(second.material_id, "封面")

            self.assertEqual(library.search("interview"), [first])
            self.assertEqual(library.search("口播"), [first])
            self.assertEqual(len(library.search("cover")), 1)

            library.remove_tag(first.material_id, "INTERVIEW")
            self.assertEqual(library.search("interview"), [])
            self.assertEqual(first.tags, ["口播"])

    def test_remove_record_keeps_source_and_copied_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "项目")
            source = root / "voice.wav"
            source.write_bytes(b"audio")
            library = self.make_library(project)
            record = library.import_file(source, copy_to_project=True)
            copied_path = Path(record.path)

            removed = library.remove_material(record.material_id)

            self.assertTrue(removed)
            self.assertTrue(source.is_file())
            self.assertTrue(copied_path.is_file())
            self.assertEqual(library.materials, [])

    def test_corrupt_media_is_recorded_without_blocking_others(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = create_project(root / "项目")
            broken = root / "broken.bad"
            valid = root / "cover.png"
            broken.write_bytes(b"broken")
            valid.write_bytes(b"image")
            library = self.make_library(project)

            broken_record = library.import_file(broken)
            valid_record = library.import_file(valid)

            self.assertEqual(broken_record.status, MaterialStatus.ERROR)
            self.assertEqual(broken_record.media_type, MediaType.UNKNOWN)
            self.assertIn("测试损坏媒体", broken_record.error)
            self.assertEqual(valid_record.status, MaterialStatus.READY)
            self.assertEqual(
                MaterialRepository(project).load(),
                [broken_record, valid_record],
            )


if __name__ == "__main__":
    unittest.main()
