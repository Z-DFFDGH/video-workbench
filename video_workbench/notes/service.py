from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

NOTES_FILE_NAME = "notes.md"


class NotesError(Exception):
    """Base exception for project note errors."""


class NotesNotFoundError(NotesError):
    """Raised when the project notes file cannot be found."""


class NotesValidationError(NotesError):
    """Raised when project notes cannot be read or written."""


def notes_path(project_root: str | Path) -> Path:
    return Path(project_root).expanduser().resolve() / NOTES_FILE_NAME


def _validate_project_root(project_root: str | Path) -> Path:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise NotesValidationError(f"项目目录不存在：{root}")
    return root


def _write_atomic(path: Path, content: str) -> None:
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary_path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(content)
        os.replace(temporary_path, path)
    except (OSError, UnicodeError) as error:
        raise NotesValidationError(f"无法保存项目笔记：{path}") from error
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


class NotesService:
    """Read and atomically save the notes.md file inside a project."""

    def load_or_create(self, project_root: str | Path) -> str:
        root = _validate_project_root(project_root)
        path = notes_path(root)
        if not path.exists():
            _write_atomic(path, "")
        return self.read(root)

    def read(self, project_root: str | Path) -> str:
        root = _validate_project_root(project_root)
        path = notes_path(root)
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise NotesNotFoundError(f"项目笔记不存在：{path}") from error
        except (OSError, UnicodeError) as error:
            raise NotesValidationError(f"无法读取项目笔记：{path}") from error

    def save(self, project_root: str | Path, content: str) -> None:
        root = _validate_project_root(project_root)
        _write_atomic(notes_path(root), content)
