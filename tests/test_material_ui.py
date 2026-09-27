from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QListView
from PySide6.QtTest import QTest

from tests._ui import application

from video_workbench.materials import (
    MaterialRecord,
    MaterialStatus,
    MediaType,
)
from video_workbench.project import create_project
from video_workbench.ui.pages import MaterialLibraryPage


def make_record(
    material_id: str,
    name: str,
    path: str,
    media_type: MediaType,
    tags: list[str] | None = None,
) -> MaterialRecord:
    return MaterialRecord(
        material_id=material_id,
        name=name,
        path=path,
        media_type=media_type,
        status=MaterialStatus.READY,
        size_bytes=2048,
        duration_seconds=12.0 if media_type != MediaType.IMAGE else None,
        width=1280 if media_type == MediaType.VIDEO else None,
        height=720 if media_type == MediaType.VIDEO else None,
        tags=list(tags or []),
        imported_at="2026-09-27T20:00:00+08:00",
    )


class FakeMaterialLibrary:
    def __init__(self, records: list[MaterialRecord] | None = None) -> None:
        self.records = list(records or [])
        self.last_import_kwargs: dict[str, object] = {}

    def materials(self) -> list[MaterialRecord]:
        return list(self.records)

    def get_material(self, material_id: str) -> MaterialRecord:
        for record in self.records:
            if record.material_id == material_id:
                return record
        raise ValueError("not found")

    def search(self, query: str) -> list[MaterialRecord]:
        needle = query.strip().casefold()
        if not needle:
            return list(self.records)
        return [
            record
            for record in self.records
            if needle in record.name.casefold()
            or any(needle in tag.casefold() for tag in record.tags)
        ]

    def import_file(
        self,
        source_path: str | Path,
        copy_to_project: bool = False,
        generate_thumbnail: bool = True,
    ) -> MaterialRecord:
        path = Path(source_path)
        self.last_import_kwargs = {
            "copy_to_project": copy_to_project,
            "generate_thumbnail": generate_thumbnail,
        }
        if path.suffix.lower() not in {".mp4", ".mp3", ".png"}:
            record = MaterialRecord(
                material_id=f"error-{len(self.records)}",
                name=path.name,
                path=str(path.resolve()),
                media_type=MediaType.UNKNOWN,
                status=MaterialStatus.ERROR,
                size_bytes=path.stat().st_size,
                error="测试不支持的文件格式",
                imported_at="2026-09-27T20:00:00+08:00",
            )
        else:
            media_type = {
                ".mp4": MediaType.VIDEO,
                ".mp3": MediaType.AUDIO,
                ".png": MediaType.IMAGE,
            }[path.suffix.lower()]
            record = make_record(
                f"import-{len(self.records)}",
                path.name,
                str(path.resolve()),
                media_type,
            )
        self.records.append(record)
        return record

    def add_tag(self, material_id: str, tag: str) -> MaterialRecord:
        record = self.get_material(material_id)
        if tag.casefold() not in {item.casefold() for item in record.tags}:
            record.tags.append(tag)
        return record

    def remove_tag(self, material_id: str, tag: str) -> MaterialRecord:
        record = self.get_material(material_id)
        record.tags = [
            item for item in record.tags if item.casefold() != tag.casefold()
        ]
        return record

    def remove_material(self, material_id: str) -> bool:
        before = len(self.records)
        self.records = [
            record for record in self.records if record.material_id != material_id
        ]
        return len(self.records) != before


class MaterialLibraryUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.project = create_project(self.root / "project")
        self.video_path = self.root / "clip.mp4"
        self.image_path = self.root / "cover.png"
        self.audio_path = self.root / "voice.mp3"
        for path in (self.video_path, self.image_path, self.audio_path):
            path.write_bytes(b"media")
        self.video = make_record(
            "video-1",
            "clip.mp4",
            str(self.video_path),
            MediaType.VIDEO,
            ["口播"],
        )
        self.image = make_record(
            "image-1",
            "cover.png",
            str(self.image_path),
            MediaType.IMAGE,
            ["封面"],
        )
        self.audio = make_record(
            "audio-1",
            "voice.mp3",
            str(self.audio_path),
            MediaType.AUDIO,
        )
        self.library = FakeMaterialLibrary([self.video, self.image, self.audio])
        self.page = MaterialLibraryPage(
            library_factory=lambda _: self.library,
        )
        self.page.set_project(self.project.root)

    def test_view_modes_search_and_result_count(self) -> None:
        self.assertEqual(self.page.material_list.count(), 3)
        self.assertEqual(self.page.result_label.text(), "共 3 个素材")

        self.page.thumbnail_view_button.click()
        self.assertEqual(
            self.page.material_list.viewMode(),
            QListView.ViewMode.IconMode,
        )

        self.page.search_input.setText("口播")
        QTest.qWait(320)

        self.assertEqual(self.page.material_list.count(), 1)
        self.assertEqual(self.page.result_label.text(), "找到 1 个素材")
        self.assertEqual(
            self.page.material_list.item(0).data(Qt.ItemDataRole.UserRole),
            "video-1",
        )

    def test_tag_update_reflects_in_search_immediately(self) -> None:
        self.page._select_material("image-1")
        self.page.tag_input.setText("横版")

        self.page.add_tag()

        self.page.search_input.setText("横版")
        self.page.perform_search()
        self.assertEqual(self.page.material_list.count(), 1)
        self.assertEqual(
            self.page.current_record.material_id,
            "image-1",
        )

    def test_drop_highlights_and_unsupported_file_shows_reason(self) -> None:
        unsupported = self.root / "notes.txt"
        unsupported.write_text("not media", encoding="utf-8")
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(str(unsupported))])
        drag_event = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.page.drop_zone.dragEnterEvent(drag_event)
        self.assertTrue(self.page.drop_zone.property("dragActive"))

        drop_event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.page.drop_zone.dropEvent(drop_event)

        self.assertFalse(self.page.drop_zone.property("dragActive"))
        self.assertIn("无法识别", self.page.message.text_label.text())
        self.assertIn("测试不支持的文件格式", self.page.message.text_label.text())

    def test_drop_is_forwarded_from_child_labels(self) -> None:
        source = self.root / "child-drop.mp4"
        source.write_bytes(b"video")
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(str(source))])

        drag_event = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.app.sendEvent(self.page.drop_zone.title_label, drag_event)
        self.assertTrue(drag_event.isAccepted())
        self.assertTrue(self.page.drop_zone.property("dragActive"))

        drop_event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.app.sendEvent(self.page.drop_zone.title_label, drop_event)

        self.assertTrue(drop_event.isAccepted())
        self.assertFalse(self.page.drop_zone.property("dragActive"))
        self.assertTrue(
            any(record.name == source.name for record in self.library.records)
        )

    def test_no_project_keeps_import_entry_enabled_with_guidance(self) -> None:
        self.page.set_project(None)

        self.assertTrue(self.page.drop_zone.isEnabled())
        self.assertIn("打开项目", self.page.message.text_label.text())

        with patch(
            "video_workbench.ui.pages.materials.QFileDialog.getOpenFileNames"
        ) as dialog:
            self.page.drop_zone.choose_button.click()

        dialog.assert_not_called()
        self.assertIn("请先打开项目", self.page.message.text_label.text())

    def test_copy_switch_defaults_off_and_is_passed_to_import(self) -> None:
        source = self.root / "new.mp4"
        source.write_bytes(b"video")

        self.assertFalse(self.page.copy_checkbox.isChecked())
        self.page.import_paths([source])
        self.assertFalse(self.library.last_import_kwargs["copy_to_project"])

        second = self.root / "second.mp4"
        second.write_bytes(b"video")
        self.page.copy_checkbox.setChecked(True)
        self.page.import_paths([second])
        self.assertTrue(self.library.last_import_kwargs["copy_to_project"])

    def test_missing_image_thumbnail_uses_placeholder(self) -> None:
        record = make_record(
            "missing-image",
            "missing.png",
            str(self.root / "missing.png"),
            MediaType.IMAGE,
        )

        icon = self.page._material_icon(record)

        self.assertFalse(icon.isNull())

    def test_ffplay_missing_has_clear_error(self) -> None:
        self.page._select_material("audio-1")
        self.page._update_selected_detail()

        with patch(
            "video_workbench.ui.pages.materials.subprocess.Popen",
            side_effect=FileNotFoundError("ffplay"),
        ):
            self.page.preview_selected()

        self.assertIn(
            "找不到 FFplay",
            self.page.message.text_label.text(),
        )

    def test_remove_record_keeps_disk_file_and_updates_ui(self) -> None:
        self.page._select_material("image-1")
        self.page._update_selected_detail()

        with patch(
            "video_workbench.ui.pages.materials.confirm",
            return_value=True,
        ):
            self.page.remove_selected()

        self.assertEqual(self.page.material_list.count(), 2)
        self.assertTrue(self.image_path.is_file())
        self.assertIn("磁盘文件没有删除", self.page.message.text_label.text())

    def test_image_preview_opens_for_image_record(self) -> None:
        self.page._select_material("image-1")
        self.page._update_selected_detail()

        with patch.object(self.page, "_open_image_preview") as preview:
            self.page.preview_selected()

        preview.assert_called_once_with(self.image)

    def test_context_panel_text_follows_selection(self) -> None:
        received: list[tuple[str, str]] = []
        self.page.context_changed.connect(
            lambda title, message: received.append((title, message))
        )

        self.page._select_material("video-1")
        self.page._update_selected_detail()

        self.assertEqual(received[-1][0], "clip.mp4")
        self.assertIn("口播", received[-1][1])
        self.assertIn("视频", received[-1][1])


if __name__ == "__main__":
    unittest.main()
