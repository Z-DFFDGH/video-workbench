from __future__ import annotations

import os
import queue
import threading
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from video_workbench.materials import MaterialLibrary

from .commands import (
    build_ffmpeg_command,
    normalize_extension,
    output_stem,
    validate_request,
)
from .models import (
    MediaOperation,
    MediaTask,
    MediaTaskStatus,
    MediaToolRequest,
    now_timestamp,
)
from .runner import FFmpegCanceled, FFmpegRunner


class MediaToolService(QObject):
    task_added = Signal(str)
    task_updated = Signal(str)
    queue_changed = Signal()

    def __init__(
        self,
        runner: FFmpegRunner | None = None,
        library_factory: Callable[[str | Path], object] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner or FFmpegRunner()
        self._library_factory = library_factory or MaterialLibrary
        self._tasks: dict[str, MediaTask] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.RLock()
        self._stop_requested = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._reserved_outputs: set[str] = set()

    def enqueue(
        self,
        request: MediaToolRequest,
        *,
        add_to_library: bool = False,
        project_root: str | Path | None = None,
    ) -> MediaTask:
        validate_request(request)
        if add_to_library and project_root is None:
            raise ValueError("加入素材库前需要先打开项目")

        output_directory = Path(request.output_directory).expanduser().resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        extension = normalize_extension(request.output_extension)
        source = Path(request.source_path).expanduser().resolve()

        self._ensure_worker()
        with self._lock:
            output_path = self._unique_output_path(
                output_directory,
                output_stem(request),
                extension,
            )
            command = tuple(
                build_ffmpeg_command(request, output_path)
            )
            task = MediaTask(
                task_id=uuid4().hex,
                title=self._task_title(request, extension),
                request=request,
                command=command,
                output_path=str(output_path),
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
            self._reserved_outputs.add(self._path_key(output_path))
            self._queue.put(task.task_id)

        self.task_added.emit(task.task_id)
        self.queue_changed.emit()
        return task

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status in {
                MediaTaskStatus.COMPLETED,
                MediaTaskStatus.FAILED,
                MediaTaskStatus.CANCELED,
            }:
                return False
            cancel_event = self._cancel_events[task_id]
            cancel_event.set()
            if task.status == MediaTaskStatus.QUEUED:
                task = task.changed(
                    status=MediaTaskStatus.CANCELED,
                    finished_at=now_timestamp(),
                )
                self._tasks[task_id] = task
                self._release_output(task.output_path)

        self.task_updated.emit(task_id)
        self.queue_changed.emit()
        return True

    def get_task(self, task_id: str) -> MediaTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def tasks(self) -> list[MediaTask]:
        with self._lock:
            return list(self._tasks.values())

    def active_count(self) -> int:
        with self._lock:
            return sum(
                task.status in {MediaTaskStatus.QUEUED, MediaTaskStatus.RUNNING}
                for task in self._tasks.values()
            )

    def failed_count(self) -> int:
        with self._lock:
            return sum(
                task.status == MediaTaskStatus.FAILED
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
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_requested.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="media-tool-queue",
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
            if task.status == MediaTaskStatus.CANCELED:
                self._cancel_events.pop(task_id, None)
                return
            task = task.changed(
                status=MediaTaskStatus.RUNNING,
                started_at=now_timestamp(),
                error=None,
            )
            self._tasks[task_id] = task

        self.task_updated.emit(task_id)
        self.queue_changed.emit()

        try:
            self._runner.run(
                task.command,
                cancel_event,
                task.output_path,
            )
            if cancel_event.is_set():
                raise FFmpegCanceled("FFmpeg 任务已取消")

            material_id = None
            library_error = None
            if task.add_to_library and task.project_root is not None:
                try:
                    library = self._library_factory(task.project_root)
                    record = library.import_file(
                        task.output_path,
                        copy_to_project=False,
                        generate_thumbnail=True,
                    )
                    material_id = record.material_id
                except Exception as error:
                    library_error = str(error)

            task = task.changed(
                status=MediaTaskStatus.COMPLETED,
                material_id=material_id,
                library_error=library_error,
                finished_at=now_timestamp(),
            )
        except FFmpegCanceled:
            self._delete_output(task.output_path)
            task = task.changed(
                status=MediaTaskStatus.CANCELED,
                finished_at=now_timestamp(),
            )
        except Exception as error:
            self._delete_output(task.output_path)
            task = task.changed(
                status=MediaTaskStatus.FAILED,
                error=str(error),
                finished_at=now_timestamp(),
            )
        finally:
            with self._lock:
                self._tasks[task_id] = task
                self._cancel_events.pop(task_id, None)
                self._release_output(task.output_path)

        self.task_updated.emit(task_id)
        self.queue_changed.emit()

    def _unique_output_path(
        self,
        directory: Path,
        stem: str,
        extension: str,
    ) -> Path:
        candidate = directory / f"{stem}{extension}"
        counter = 1
        while (
            candidate.exists()
            or self._path_key(candidate) in self._reserved_outputs
        ):
            candidate = directory / f"{stem}_{counter}{extension}"
            counter += 1
        return candidate

    @staticmethod
    def _path_key(path: str | Path) -> str:
        return os.path.normcase(os.path.normpath(str(path)))

    def _release_output(self, output_path: str | Path) -> None:
        self._reserved_outputs.discard(self._path_key(output_path))

    @staticmethod
    def _delete_output(output_path: str | Path) -> None:
        try:
            Path(output_path).unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _task_title(request: MediaToolRequest, extension: str) -> str:
        source_name = Path(request.source_path).name
        labels = {
            MediaOperation.CONVERT_AUDIO: "音频转换",
            MediaOperation.CONVERT_VIDEO: "视频转换",
            MediaOperation.EXTRACT_AUDIO: "提取音频",
            MediaOperation.TRIM_VIDEO: "视频裁剪",
            MediaOperation.TRIM_AUDIO: "音频裁剪",
            MediaOperation.RESIZE_VIDEO: "分辨率处理",
            MediaOperation.ADJUST_VOLUME: "音量调整",
        }
        return f"{labels[request.operation]}：{source_name} → {extension.upper()}"
