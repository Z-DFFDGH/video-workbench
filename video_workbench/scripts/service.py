from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

SUPPORTED_SCRIPT_EXTENSIONS = frozenset({".txt", ".md"})
SCRIPTS_DIRECTORY_NAME = "脚本文档"
_INVALID_FILENAME_CHARACTERS = frozenset('<>:"/\\|?*')


class ScriptError(Exception):
    """Base exception for script document errors."""


class ScriptNotFoundError(ScriptError):
    """Raised when a script document cannot be found."""


class ScriptValidationError(ScriptError):
    """Raised when a script path or filename is invalid."""


@dataclass(frozen=True, slots=True)
class ScriptDocument:
    path: Path
    content: str

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()


def scripts_directory(project_root: str | Path) -> Path:
    return (Path(project_root).expanduser().resolve() / SCRIPTS_DIRECTORY_NAME)


def _validate_extension(path: Path) -> None:
    if path.suffix.lower() not in SUPPORTED_SCRIPT_EXTENSIONS:
        raise ScriptValidationError("脚本文档仅支持 .txt 和 .md 格式")


def _validate_filename(filename: str) -> str:
    clean_name = filename.strip()
    if not clean_name or clean_name in {".", ".."}:
        raise ScriptValidationError("脚本文件名不能为空")
    if Path(clean_name).name != clean_name:
        raise ScriptValidationError("脚本文件名不能包含路径")
    if any(character in _INVALID_FILENAME_CHARACTERS for character in clean_name):
        raise ScriptValidationError("脚本文件名包含 Windows 不允许的字符")
    if any(ord(character) < 32 for character in clean_name):
        raise ScriptValidationError("脚本文件名不能包含控制字符")
    if clean_name.endswith((" ", ".")):
        raise ScriptValidationError("脚本文件名不能以空格或句点结尾")

    candidate = Path(clean_name)
    if not candidate.suffix:
        clean_name += ".txt"
        candidate = Path(clean_name)
    _validate_extension(candidate)
    return clean_name


def _read_text(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            return stream.read()
    except FileNotFoundError as error:
        raise ScriptNotFoundError(f"脚本文件不存在：{path}") from error
    except (OSError, UnicodeError) as error:
        raise ScriptValidationError(f"无法读取脚本文件：{path}") from error


def _write_atomic(path: Path, content: str) -> None:
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary_path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(content)
        os.replace(temporary_path, path)
    except (OSError, UnicodeError) as error:
        raise ScriptError(f"无法保存脚本文件：{path}") from error
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        candidate = directory / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _path_from_value(document: ScriptDocument | str | Path) -> Path:
    value = document.path if isinstance(document, ScriptDocument) else document
    path = Path(value).expanduser().resolve()
    _validate_extension(path)
    return path


def _ensure_scripts_directory(project_root: str | Path) -> Path:
    directory = scripts_directory(project_root)
    if not directory.is_dir():
        raise ScriptValidationError(f"项目脚本文档目录不存在：{directory}")
    return directory


def _ensure_inside_scripts_directory(
    project_root: str | Path,
    path: Path,
) -> Path:
    directory = _ensure_scripts_directory(project_root)
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(directory)
    except ValueError as error:
        raise ScriptValidationError("脚本文档必须保存在当前项目的“脚本文档”目录内") from error
    return resolved


class ScriptService:
    def list_documents(self, project_root: str | Path) -> list[Path]:
        directory = _ensure_scripts_directory(project_root)
        try:
            documents = [
                path.resolve()
                for path in directory.iterdir()
                if path.is_file()
                and path.suffix.lower() in SUPPORTED_SCRIPT_EXTENSIONS
            ]
        except OSError as error:
            raise ScriptError(f"无法读取脚本文档目录：{directory}") from error
        return sorted(documents, key=lambda path: path.name.casefold())

    def create_document(
        self,
        project_root: str | Path,
        filename: str,
        content: str = "",
    ) -> ScriptDocument:
        directory = _ensure_scripts_directory(project_root)
        clean_name = _validate_filename(filename)
        path = _unique_path(directory, clean_name)
        _write_atomic(path, content)
        return ScriptDocument(path=path, content=content)

    def read_document(
        self,
        path: str | Path,
    ) -> ScriptDocument:
        document_path = _path_from_value(path)
        return ScriptDocument(path=document_path, content=_read_text(document_path))

    def save_document(
        self,
        document: ScriptDocument | str | Path,
        content: str,
        project_root: str | Path,
    ) -> ScriptDocument:
        path = _path_from_value(document)
        path = _ensure_inside_scripts_directory(project_root, path)
        _write_atomic(path, content)
        return ScriptDocument(path=path, content=content)

    def save_as_document(
        self,
        project_root: str | Path,
        target_path: str | Path,
        content: str,
    ) -> ScriptDocument:
        target = Path(target_path)
        if not target.is_absolute():
            target = scripts_directory(project_root) / target
        target = _ensure_inside_scripts_directory(project_root, target)
        _validate_extension(target)
        _write_atomic(target, content)
        return ScriptDocument(path=target, content=content)

    def export_document(
        self,
        project_root: str | Path,
        source: ScriptDocument | str | Path,
        content: str,
        extension: str,
    ) -> ScriptDocument:
        source_path = _path_from_value(source)
        source_path = _ensure_inside_scripts_directory(project_root, source_path)
        normalized_extension = extension.strip().lower()
        if not normalized_extension.startswith("."):
            normalized_extension = f".{normalized_extension}"
        _validate_extension(Path(f"script{normalized_extension}"))

        target = source_path.with_suffix(normalized_extension)
        if target == source_path:
            return self.save_document(source_path, content, project_root)
        if target.exists():
            target = _unique_path(target.parent, target.name)
        _write_atomic(target, content)
        return ScriptDocument(path=target, content=content)
