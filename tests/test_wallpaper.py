from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._ui import application

from PySide6.QtGui import QColor, QImage
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtTest import QTest

from video_workbench.app import AppConfig, ConfigStore
from video_workbench.ui.animations import animations_enabled_for_setting
from video_workbench.ui.components.wallpaper import WallpaperBackground
from video_workbench.ui.main_window import MainWindow


def create_test_image(path: Path) -> None:
    image = QImage(160, 100, QImage.Format.Format_RGB32)
    image.fill(QColor("#2A6F97"))
    if not image.save(str(path)):
        raise RuntimeError(f"无法创建测试图片：{path}")


class WallpaperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def test_default_and_invalid_wallpaper_fall_back_to_builtin(self) -> None:
        wallpaper = WallpaperBackground()

        self.assertTrue(wallpaper.is_default)
        self.assertTrue(wallpaper.set_wallpaper_path(None))
        self.assertTrue(wallpaper.is_default)

        self.assertFalse(wallpaper.set_wallpaper_path("missing-wallpaper.png"))
        self.assertTrue(wallpaper.is_default)
        self.assertIsNone(wallpaper.wallpaper_path)

    def test_valid_wallpaper_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "wallpaper.png"
            create_test_image(image_path)
            wallpaper = WallpaperBackground()

            self.assertTrue(wallpaper.set_wallpaper_path(image_path))
            self.assertFalse(wallpaper.is_default)
            self.assertEqual(wallpaper.wallpaper_path, str(image_path))

    def test_main_window_persists_and_restores_wallpaper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image_path = root / "wallpaper.png"
            create_test_image(image_path)
            store = ConfigStore(root / "config.json")

            window = MainWindow(config_store=store, animations_enabled=False)
            window._apply_wallpaper(str(image_path))
            self.assertEqual(store.load().wallpaper_path, str(image_path))
            self.assertEqual(
                window.shell.wallpaper.wallpaper_path,
                str(image_path),
            )

            window._restore_default_wallpaper()
            self.assertIsNone(store.load().wallpaper_path)
            self.assertTrue(window.shell.wallpaper.is_default)
            window.close()

    def test_invalid_startup_wallpaper_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = ConfigStore(root / "config.json")
            store.save(AppConfig(wallpaper_path=str(root / "missing.png")))

            window = MainWindow(config_store=store, animations_enabled=False)

            self.assertTrue(window.shell.wallpaper.is_default)
            self.assertIsNone(window.shell.wallpaper.wallpaper_path)
            window.close()

    def test_window_renders_non_blank_offscreen_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = ConfigStore(Path(temporary_directory) / "config.json")
            window = MainWindow(config_store=store, animations_enabled=False)
            window.resize(1280, 800)
            window.show()
            self.app.processEvents()

            image = window.grab().toImage()

            self.assertEqual(image.width(), 1280)
            self.assertEqual(image.height(), 800)
            sampled_colors = {
                image.pixelColor(x, y).getRgb()
                for x in range(0, image.width(), 80)
                for y in range(0, image.height(), 60)
            }
            self.assertGreater(len(sampled_colors), 4)
            window.close()

    def test_animation_setting_parser_matches_windows_flag(self) -> None:
        self.assertTrue(animations_enabled_for_setting(1))
        self.assertFalse(animations_enabled_for_setting(0))

    def test_wallpaper_panel_closes_with_escape_and_outside_click(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = ConfigStore(Path(temporary_directory) / "config.json")
            window = MainWindow(config_store=store, animations_enabled=False)
            window.resize(1280, 800)
            window.show()
            self.app.processEvents()

            window._toggle_wallpaper_panel()
            self.assertTrue(window.wallpaper_panel.isVisible())

            escape_event = QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Escape,
                Qt.KeyboardModifier.NoModifier,
            )
            self.app.sendEvent(window, escape_event)
            self.assertFalse(window.wallpaper_panel.isVisible())

            window._toggle_wallpaper_panel()
            self.assertTrue(window.wallpaper_panel.isVisible())
            QTest.mouseClick(
                window.shell.content_frame,
                Qt.MouseButton.LeftButton,
            )
            self.assertFalse(window.wallpaper_panel.isVisible())
            window.close()


if __name__ == "__main__":
    unittest.main()
