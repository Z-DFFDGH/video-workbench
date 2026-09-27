from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from video_workbench.app import (
    CONFIG_SCHEMA_VERSION,
    AppConfig,
    ConfigError,
    ConfigStore,
)


class AppConfigTests(unittest.TestCase):
    def test_missing_config_creates_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "config.json"
            store = ConfigStore(path)

            config = store.load()

            self.assertEqual(config.schema_version, CONFIG_SCHEMA_VERSION)
            self.assertIsNone(config.wallpaper_path)
            self.assertEqual(config.recent_projects, [])
            self.assertIsNone(config.download_directory)
            self.assertIsNone(config.media_output_directory)
            self.assertTrue(path.is_file())

    def test_config_round_trip_preserves_recent_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "config.json"
            store = ConfigStore(path)
            expected = AppConfig(
                wallpaper_path="C:\\wallpaper.png",
                download_directory=str((root / "downloads").resolve()),
                media_output_directory=str((root / "media-output").resolve()),
                recent_projects=[
                    str((root / "项目一").resolve()),
                    str((root / "项目二").resolve()),
                ],
            )

            store.save(expected)

            self.assertEqual(store.load(), expected)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 4)
            self.assertEqual(
                payload["recent_projects"],
                expected.recent_projects,
            )

    def test_legacy_v1_config_migrates_without_losing_wallpaper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "wallpaper_path": "C:\\legacy.png",
                    }
                ),
                encoding="utf-8",
            )

            config = ConfigStore(path).load()

            self.assertEqual(config.schema_version, 4)
            self.assertEqual(config.wallpaper_path, "C:\\legacy.png")
            self.assertEqual(config.recent_projects, [])
            self.assertIsNone(config.download_directory)
            self.assertIsNone(config.media_output_directory)

    def test_legacy_v2_config_migrates_without_losing_recent_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "wallpaper_path": "C:\\legacy.png",
                        "recent_projects": ["C:\\project"],
                    }
                ),
                encoding="utf-8",
            )

            config = ConfigStore(path).load()

            self.assertEqual(config.schema_version, 4)
            self.assertEqual(config.wallpaper_path, "C:\\legacy.png")
            self.assertEqual(len(config.recent_projects), 1)
            self.assertIsNone(config.download_directory)
            self.assertIsNone(config.media_output_directory)

    def test_recent_projects_are_normalized_and_deduplicated(self) -> None:

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project_path = root / "示例项目"
            payload = {
                "recent_projects": [
                    str(project_path),
                    "",
                    None,
                    str(project_path),
                ]
            }

            config = AppConfig.from_dict(payload)

            self.assertEqual(
                config.recent_projects,
                [str(project_path.resolve())],
            )

    def test_invalid_json_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "config.json"
            path.write_text("{not json", encoding="utf-8")

            config = ConfigStore(path).load()

        self.assertIsNone(config.wallpaper_path)
        self.assertEqual(config.recent_projects, [])
        self.assertIsNone(config.media_output_directory)

    def test_save_error_has_clear_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory_path = Path(temporary_directory) / "already-a-directory"
            directory_path.mkdir()
            store = ConfigStore(directory_path)

            with self.assertRaises(ConfigError):
                store.save(AppConfig())


if __name__ == "__main__":
    unittest.main()
