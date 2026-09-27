from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video_workbench.project import (
    PROJECT_DIRECTORIES,
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    ProjectValidationError,
    create_project,
    delete_project,
    forget_recent_project,
    load_project,
    remember_recent_project,
    rename_project,
)


class ProjectManagerTests(unittest.TestCase):
    def test_create_project_creates_fixed_structure_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "示例项目"
            project_root.mkdir()

            project = create_project(project_root)

            self.assertEqual(project.name, "示例项目")
            self.assertEqual(project.root, project_root.resolve())
            self.assertTrue(project.project_file.is_file())

            for directory_name in PROJECT_DIRECTORIES.values():
                self.assertTrue((project_root / directory_name).is_dir())

            metadata = json.loads(project.project_file.read_text(encoding="utf-8"))
            self.assertEqual(metadata["schema_version"], 1)
            self.assertEqual(metadata["name"], "示例项目")
            self.assertEqual(metadata["directories"], PROJECT_DIRECTORIES)

    def test_create_project_rejects_existing_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "重复项目"
            project_root.mkdir()
            create_project(project_root)

            with self.assertRaises(ProjectAlreadyExistsError):
                create_project(project_root)

    def test_load_project_accepts_root_or_metadata_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "已有项目"
            created = create_project(project_root)

            from_root = load_project(project_root)
            from_file = load_project(created.project_file)

            self.assertEqual(from_root, created)
            self.assertEqual(from_file, created)

    def test_load_project_rejects_missing_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ProjectNotFoundError):
                load_project(Path(temporary_directory) / "missing-project")

    def test_load_project_rejects_invalid_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "损坏项目"
            project = create_project(project_root)
            payload = json.loads(project.project_file.read_text(encoding="utf-8"))
            del payload["name"]
            project.project_file.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaises(ProjectValidationError):
                load_project(project_root)

    def test_rename_project_only_changes_display_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory) / "原目录名"
            project = create_project(project_root)
            before = json.loads(project.project_file.read_text(encoding="utf-8"))

            renamed = rename_project(project, "新的显示名称")
            after = json.loads(project.project_file.read_text(encoding="utf-8"))

            self.assertEqual(renamed.name, "新的显示名称")
            self.assertEqual(renamed.root, project.root)
            self.assertEqual(after["name"], "新的显示名称")
            self.assertEqual(
                {key: value for key, value in after.items() if key != "name"},
                {key: value for key, value in before.items() if key != "name"},
            )
            self.assertTrue(project_root.is_dir())

    def test_rename_project_rejects_empty_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = create_project(Path(temporary_directory) / "项目")

            with self.assertRaises(ProjectValidationError):
                rename_project(project, "   ")

    def test_delete_project_uses_send2trash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = create_project(Path(temporary_directory) / "待删除项目")

            with patch("video_workbench.project.manager.send2trash") as trash:
                delete_project(project)

            trash.assert_called_once_with(str(project.root))
            self.assertTrue(project.root.is_dir())

    def test_delete_missing_project_has_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ProjectNotFoundError):
                delete_project(Path(temporary_directory) / "missing-project")

    def test_recent_projects_are_deduplicated_and_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "项目一"
            second = root / "项目二"

            recent = remember_recent_project([first, second], second)
            self.assertEqual(recent, [str(second.resolve()), str(first.resolve())])

            recent = remember_recent_project(recent, second)
            self.assertEqual(recent, [str(second.resolve()), str(first.resolve())])

            recent = forget_recent_project(recent, second)
            self.assertEqual(recent, [str(first.resolve())])


if __name__ == "__main__":
    unittest.main()
