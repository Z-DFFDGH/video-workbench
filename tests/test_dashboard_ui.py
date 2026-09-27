from __future__ import annotations

import unittest

from tests._ui import application
from PySide6.QtTest import QTest

from video_workbench.ui.components.dashboard import (
    DashboardCard,
    MetricCard,
    PlanetIllustration,
    Sparkline,
)
from video_workbench.ui.shell import AppShell
from video_workbench.ui.styles import APP_STYLE, COLORS


class DashboardUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def test_project_page_builds_dashboard_card_modules(self) -> None:
        shell = AppShell(animations_enabled=False)
        shell.resize(1440, 900)

        self.assertIsNotNone(shell.dashboard)
        self.assertEqual(len(shell.dashboard.findChildren(MetricCard)), 3)
        self.assertGreaterEqual(
            len(shell.dashboard.findChildren(DashboardCard)),
            6,
        )
        shell.close()

    def test_dashboard_project_labels_update_with_current_project(self) -> None:
        shell = AppShell(animations_enabled=False)

        shell.set_project("示例项目", "I:\\示例项目")

        self.assertEqual(shell.dashboard.project_name.text(), "示例项目")
        self.assertEqual(shell.dashboard.profile.name.text(), "示例项目")
        self.assertEqual(shell.dashboard.profile.state.text(), "示例项目")
        shell.close()

    def test_dark_theme_contains_neon_dashboard_tokens(self) -> None:
        self.assertIn("#070A14", APP_STYLE)
        self.assertEqual(COLORS["accent"], "#8B6CFF")
        self.assertIn("QFrame#DashboardCard", APP_STYLE)
        self.assertIn("#70E4FF", APP_STYLE)
        self.assertIn("QComboBox#RangeSelector", APP_STYLE)

    def test_activity_range_selector_provides_visual_feedback(self) -> None:
        shell = AppShell(animations_enabled=False)
        chart = shell.dashboard.activity_chart

        self.assertEqual(chart.range_selector.currentText(), "近 7 天")
        self.assertEqual(chart.range_selector.count(), 3)
        chart.range_selector.setCurrentText("近 30 天")
        self.assertEqual(chart.status_label.text(), "近 30 天 · 等待数据")
        shell.close()

    def test_dashboard_card_hover_animates_soft_glow(self) -> None:
        card = MetricCard("素材", "cyan", animations_enabled=True)

        card.set_hovered(True)
        QTest.qWait(220)
        self.assertTrue(card.property("hovered"))
        self.assertEqual(card._blur_animation.endValue(), 40)
        self.assertEqual(card._shadow.blurRadius(), 40)
        self.assertEqual(card._hover_animation.duration(), 170)
        self.assertIsNotNone(card.graphicsEffect())

        card.set_hovered(False)
        self.assertFalse(card.property("hovered"))
        self.assertEqual(card._blur_animation.endValue(), 28)
        card.close()

    def test_sparkline_and_planet_render_non_blank(self) -> None:
        for widget in (Sparkline(), PlanetIllustration()):
            widget.resize(320, 140)
            image = widget.grab().toImage()
            colors = {
                image.pixelColor(x, y).getRgb()
                for x in range(0, image.width(), 20)
                for y in range(0, image.height(), 20)
            }
            self.assertGreater(len(colors), 2)
            widget.close()


if __name__ == "__main__":
    unittest.main()
