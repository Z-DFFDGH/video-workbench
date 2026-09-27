from __future__ import annotations

import unittest

from video_workbench.downloader import DownloadStatus, parse_link_input


class DownloadModelTests(unittest.TestCase):
    def test_parse_link_input_keeps_valid_lines_and_reports_invalid_lines(self) -> None:
        result = parse_link_input(
            "\n".join(
                [
                    "https://example.com/video/1",
                    "这不是链接",
                    "https://example.com/a https://example.com/b",
                    "标题 https://example.com/video/2。",
                    "https://example.com/video/1",
                ]
            )
        )

        self.assertEqual(
            result.urls,
            (
                "https://example.com/video/1",
                "https://example.com/video/2",
            ),
        )
        self.assertEqual(
            [line.line_number for line in result.invalid_lines],
            [2, 3],
        )
        self.assertEqual(result.invalid_lines[0].reason, "未检测到链接")
        self.assertEqual(
            result.invalid_lines[1].reason,
            "每行只能包含一个链接",
        )

    def test_download_task_changed_returns_an_immutable_snapshot(self) -> None:
        task = __import__(
            "video_workbench.downloader.models",
            fromlist=["DownloadTask"],
        ).DownloadTask(
            task_id="task-1",
            source_url="https://example.com/video",
            output_directory="C:\\downloads",
            mode=__import__(
                "video_workbench.downloader.models",
                fromlist=["DownloadMode"],
            ).DownloadMode.VIDEO,
        )

        changed = task.changed(
            status=DownloadStatus.RUNNING,
            attempt_count=1,
        )

        self.assertEqual(task.status, DownloadStatus.QUEUED)
        self.assertEqual(task.attempt_count, 0)
        self.assertEqual(changed.status, DownloadStatus.RUNNING)
        self.assertEqual(changed.attempt_count, 1)


if __name__ == "__main__":
    unittest.main()
