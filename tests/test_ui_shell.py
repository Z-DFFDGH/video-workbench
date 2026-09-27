from __future__ import annotations

import unittest

from tests._ui import application

from video_workbench.ui.shell import AppShell, Sidebar, TaskDrawer


class UiShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = application()

    def setUp(self) -> None:
        self.shell = AppShell(animations_enabled=False)
        self.shell.resize(1440, 900)

    def tearDown(self) -> None:
        self.shell.close()
        self.shell.deleteLater()
        self.app.processEvents()

    def test_sidebar_starts_expanded_and_toggles(self) -> None:
        sidebar = self.shell.sidebar

        self.assertFalse(sidebar.is_collapsed)
        self.assertEqual(sidebar.maximumWidth(), Sidebar.EXPANDED_WIDTH)

        self.shell.toggle_sidebar()
        self.assertTrue(sidebar.is_collapsed)
        self.assertEqual(sidebar.maximumWidth(), Sidebar.COLLAPSED_WIDTH)

        self.shell.toggle_sidebar()
        self.assertFalse(sidebar.is_collapsed)
        self.assertEqual(sidebar.maximumWidth(), Sidebar.EXPANDED_WIDTH)

    def test_navigation_changes_page_selection_and_context_panel(self) -> None:
        self.shell.select_page("materials")

        self.assertEqual(self.shell.current_page_key, "materials")
        self.assertEqual(self.shell.sidebar.selected_key(), "materials")
        self.assertTrue(self.shell.context_panel.isVisibleTo(self.shell))

        self.shell.select_page("scripts")
        self.assertEqual(self.shell.current_page_key, "scripts")
        self.assertFalse(self.shell.context_panel.isVisibleTo(self.shell))

    def test_task_drawer_expands_and_collapses(self) -> None:
        drawer = self.shell.task_drawer

        self.assertFalse(drawer.is_expanded)
        self.assertEqual(drawer.maximumHeight(), TaskDrawer.COLLAPSED_HEIGHT)

        self.shell.toggle_task_drawer()
        self.assertTrue(drawer.is_expanded)
        self.assertEqual(drawer.maximumHeight(), TaskDrawer.EXPANDED_HEIGHT)

        self.shell.toggle_task_drawer()
        self.assertFalse(drawer.is_expanded)
        self.assertEqual(drawer.maximumHeight(), TaskDrawer.COLLAPSED_HEIGHT)

    def test_project_display_updates_top_bar_and_sidebar(self) -> None:
        self.shell.set_project("示例项目", "I:\\示例项目")

        self.assertEqual(self.shell.top_bar.project_title.text(), "示例项目")
        self.assertEqual(self.shell.sidebar.path_label.text(), "I:\\示例项目")

    def test_project_actions_follow_current_project_state(self) -> None:
        top_bar = self.shell.top_bar

        self.assertTrue(top_bar.new_project_action.isEnabled())
        self.assertTrue(top_bar.open_project_action.isEnabled())
        self.assertFalse(top_bar.rename_project_action.isEnabled())
        self.assertFalse(top_bar.delete_project_action.isEnabled())

        self.shell.set_project("示例项目", "I:\\示例项目")
        self.assertTrue(top_bar.rename_project_action.isEnabled())
        self.assertTrue(top_bar.delete_project_action.isEnabled())

        self.shell.set_project(None)
        self.assertFalse(top_bar.rename_project_action.isEnabled())
        self.assertFalse(top_bar.delete_project_action.isEnabled())

    def test_open_and_recent_project_actions_emit_paths(self) -> None:
        opened = []
        recent = []
        self.shell.open_project_requested.connect(lambda: opened.append(True))
        self.shell.recent_project_requested.connect(recent.append)

        self.shell.dashboard.open_button.click()
        self.shell.set_recent_projects([("项目一", "I:\\项目一")])
        self.shell.top_bar.recent_projects_menu.actions()[0].trigger()

        self.assertEqual(opened, [True])
        self.assertEqual(recent, ["I:\\项目一"])

    def test_toast_feedback_is_visible_inside_shell(self) -> None:
        self.shell.show()
        self.app.processEvents()

        toast = self.shell.show_message("界面反馈已就绪", "success", 0)
        self.app.processEvents()

        self.assertTrue(toast.isVisible())
        host_geometry = self.shell.toast_host.geometry()
        self.assertGreaterEqual(
            self.shell.toast_host.width(),
            toast.minimumSizeHint().width(),
        )
        self.assertGreaterEqual(
            self.shell.toast_host.height(),
            toast.sizeHint().height(),
        )
        toast_geometry = toast.geometry()
        self.assertGreaterEqual(toast_geometry.left(), 0)
        self.assertGreaterEqual(toast_geometry.top(), 0)
        self.assertLessEqual(toast_geometry.right(), host_geometry.width() - 1)
        self.assertLessEqual(toast_geometry.bottom(), host_geometry.height() - 1)
        self.assertGreaterEqual(host_geometry.left(), 0)
        self.assertGreaterEqual(host_geometry.top(), 0)
        self.assertLessEqual(host_geometry.right(), self.shell.width())
        self.assertLessEqual(host_geometry.bottom(), self.shell.height())


if __name__ == "__main__":
    unittest.main()
