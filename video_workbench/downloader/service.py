from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from video_workbench.materials import MaterialLibrary

from .adapter import DefaultDownloadAdapter
from .errors import DownloadCanceled
from .models import (
    DownloadMode,
    DownloadStatus,
    DownloadTask,
    now_timestamp,
)


class DownloadService(QObject):
    task_added = Signal(str)
    task_updated = Signal(str)
    queue_changed = Signal()

    def __init__(
        self,
        adapter: DefaultDownloadAdapter | None = None,
        library_factory: Callable[[str | Path], object] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._adapter = adapter or DefaultDownloadAdapter()
        self._library_factory = library_factory or MaterialLibrary
        self._tasks: dict[str, DownloadTask] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.RLock()
        self._stop_requested = threading.Event()
        self._worker_thread: threading.Thread | None = None

    def enqueue_many(
        self,
        urls: Iterable[str],
        output_directory: str | Path,
        mode: DownloadMode,
        *,
        add_to_library: bool = False,
        project_root: str | Path | None = None,
    ) -> list[DownloadTask]:
        clean_urls = [url.strip() for url in urls if url.strip()]
        if not clean_urls:
            raise ValueError("没有可下载的链接")
        if add_to_library and project_root is None:
            raise ValueError("加入素材库前需要先打开项目")

        output_path = Path(output_directory).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        created: list[DownloadTask] = []
        self._ensure_worker()

        with self._lock:
            for url in clean_urls:
                task = DownloadTask(
                    task_id=uuid4().hex,
                    source_url=url,
                    output_directory=str(output_path),
                    mode=mode,
                    add_to_library=add_to_library,
                    project_root=(
                        str(Path(project_root).expanduser().resolve())
                        if project_root is not None
                        else None
                    ),
                    created_at=now_timestamp(),
                )
                self._tasks[task.task_id] = task
                self._cancel_events[task.task_id] = threading.Event()
                created.append(task)

            for task in created:
                self._queue.put(task.task_id)

        for task in created:
            self.task_added.emit(task.task_id)
        self.queue_changed.emit()
        return created

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status in {
                DownloadStatus.COMPLETED,
                DownloadStatus.FAILED,
                DownloadStatus.CANCELED,
            }:
                return False

            cancel_event = self._cancel_events[task_id]
            cancel_event.set()
            if task.status == DownloadStatus.QUEUED:
                task = task.changed(
                    status=DownloadStatus.CANCELED,
                    finished_at=now_timestamp(),
                )
                self._tasks[task_id] = task

        self.task_updated.emit(task_id)
        self.queue_changed.emit()
        return True

    def get_task(self, task_id: str) -> DownloadTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def tasks(self) -> list[DownloadTask]:
        with self._lock:
            return list(self._tasks.values())

    def active_count(self) -> int:
        with self._lock:
            return sum(
                task.status
                in {DownloadStatus.QUEUED, DownloadStatus.RUNNING}
                for task in self._tasks.values()
            )

    def failed_count(self) -> int:
        with self._lock:
            return sum(
                task.status == DownloadStatus.FAILED
                for task in self._tasks.values()
            )

    def shutdown(self, wait_seconds: float = 5.0) -> None:
        with self._lock:
            task_ids = list(self._tasks)
        for task_id in task_ids:
            self.cancel(task_id)

        self._stop_requested.set()
        self._queue.put(None)
        thread = self._worker_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=wait_seconds)

    def _ensure_worker(self) -> None:
        if (
            self._worker_thread is not None
            and self._worker_thread.is_alive()
        ):
            return
        self._stop_requested.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="download-queue",
            daemon=True,
        )
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        while not self._stop_requested.is_set():
            task_id = self._queue.get()
            if task_id is None:
                return
            self._run_task(task_id)

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks[task_id]
            cancel_event = self._cancel_events[task_id]
            if task.status == DownloadStatus.CANCELED:
                self._cancel_events.pop(task_id, None)
                return
            task = task.changed(
                status=DownloadStatus.RUNNING,
                started_at=now_timestamp(),
                error=None,
            )
            self._tasks[task_id] = task

        self.task_updated.emit(task_id)
        self.queue_changed.emit()

        try:
            result = self._adapter.download(
                task.source_url,
                task.output_directory,
                task.mode,
                cancel_event,
            )
            if cancel_event.is_set():
                raise DownloadCanceled("下载已取消")

            material_id = None
            library_error = None
            if task.add_to_library and task.project_root is not None:
                try:
                    library = self._library_factory(task.project_root)
                    record = library.import_file(
                        result.path,
                        copy_to_project=False,
                    )
                    material_id = record.material_id
                except Exception as error:
                    library_error = str(error)

            task = task.changed(
                status=DownloadStatus.COMPLETED,
                output_path=str(result.path),
                attempt_count=result.attempts,
                material_id=material_id,
                library_error=library_error,
                finished_at=now_timestamp(),
            )
        except DownloadCanceled:
            task = task.changed(
                status=DownloadStatus.CANCELED,
                finished_at=now_timestamp(),
            )
        except Exception as error:
            task = task.changed(
                status=DownloadStatus.FAILED,
                error=str(error),
                finished_at=now_timestamp(),
            )
        finally:
            with self._lock:
                self._tasks[task_id] = task
                self._cancel_events.pop(task_id, None)

        self.task_updated.emit(task_id)
        self.queue_changed.emit()
