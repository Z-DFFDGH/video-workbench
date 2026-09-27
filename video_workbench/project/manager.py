from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from send2trash import send2trash

PROJECT_FILE_NAME = "project.json"
PROJECT_SCHEMA_VERSION = 1
MAX_RECENT_PROJECTS = 12

PROJECT_DIRECTORIES = {
    "source_materials": "原素材",
    "scripts": "脚本文档",
    "audio": "音频文件",
    "images": "图片封面",
    "output": "输出成品",
}


class ProjectError(Exception):
    """Base exception for project lifecycle errors."""


class ProjectAlreadyExistsError(ProjectError):
    """Raised when the selected directory already contains a project."""


class ProjectNotFoundError(ProjectError):
    """Raised when a project directory or metadata file cannot be found."""


class ProjectValidationError(ProjectError):
    """Raised when project metadata is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    name: str
    root: Path
    project_file: Path


def _path_key(path: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(Path(path).expanduser().resolve())))


def normalize_project_root(root_path: str | Path) -> Path:
    return Path(root_path).expanduser().resolve()


def normalize_recent_projects(paths: Iterable[str | Path]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if not isinstance(path, (str, Path)) or not str(path).strip():
            continue
        resolved = str(normalize_project_root(path))
        key = _path_key(resolved)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(resolved)
    return normalized[:MAX_RECENT_PROJECTS]


def remember_recent_project(
    recent_projects: Iterable[str | Path],
    root_path: str | Path,
) -> list[str]:
    normalized = normalize_recent_projects(recent_projects)
    root = str(normalize_project_root(root_path))
    key = _path_key(root)
    return [root] + [path for path in normalized if _path_key(path) != key]


def forget_recent_project(
    recent_projects: Iterable[str | Path],
    root_path: str | Path,
) -> list[str]:
    key = _path_key(root_path)
    return [
        path
        for path in normalize_recent_projects(recent_projects)
        if _path_key(path) != key
    ]


def _project_file_and_root(path_value: str | Path) -> tuple[Path, Path]:
    candidate = Path(path_value).expanduser()
    if candidate.name.lower() == PROJECT_FILE_NAME:
        project_file = candidate.resolve()
        root = project_file.parent
    else:
        root = candidate.resolve()
        project_file = root / PROJECT_FILE_NAME
    return root, project_file


def _read_project_payload(project_file: Path) -> dict[str, object]:
    try:
        payload = json.loads(project_file.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProjectNotFoundError(f"项目文件不存在：{project_file}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProjectValidationError(f"无法读取项目文件：{project_file}") from error

    if not isinstance(payload, dict):
        raise ProjectValidationError("project.json 根节点必须是 JSON 对象")

    if payload.get("schema_version") != PROJECT_SCHEMA_VERSION:
        raise ProjectValidationError(
            f"不支持的项目版本：{payload.get('schema_version')!r}"
        )

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProjectValidationError("project.json 缺少有效的 name")

    created_at = payload.get("created_at")
    if not isinstance(created_at, str) or not created_at.strip():
        raise ProjectValidationError("project.json 缺少有效的 created_at")

    directories = payload.get("directories")
    if not isinstance(directories, dict):
        raise ProjectValidationError("project.json 缺少有效的 directories")
    if set(directories) != set(PROJECT_DIRECTORIES):
        raise ProjectValidationError("project.json 的目录配置不完整")
    if any(
        not isinstance(value, str) or not value.strip()
        for value in directories.values()
    ):
        raise ProjectValidationError("project.json 包含无效的目录名称")

    return payload


def load_project(project_path: str | Path) -> ProjectInfo:
    """Load and validate an existing project directory or project.json file."""
    root, project_file = _project_file_and_root(project_path)
    if not project_file.is_file():
        raise ProjectNotFoundError(f"项目文件不存在：{project_file}")

    payload = _read_project_payload(project_file)
    return ProjectInfo(
        name=str(payload["name"]).strip(),
        root=root,
        project_file=project_file,
    )


def _write_project_payload(project_file: Path, payload: dict[str, object]) -> None:
    temporary_file = project_file.with_suffix(".json.tmp")
    try:
        temporary_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_file, project_file)
    except OSError as error:
        raise ProjectError(f"无法写入项目文件：{project_file}") from error


def create_project(root_path: str | Path) -> ProjectInfo:
    """Create the fixed project directories and project.json in a directory."""
    root = normalize_project_root(root_path)
    root.mkdir(parents=True, exist_ok=True)

    if not root.is_dir():
        raise ProjectError(f"项目根目录不是文件夹：{root}")

    project_file = root / PROJECT_FILE_NAME
    if project_file.exists():
        raise ProjectAlreadyExistsError(f"该目录已包含 {PROJECT_FILE_NAME}：{root}")

    for directory_name in PROJECT_DIRECTORIES.values():
        (root / directory_name).mkdir(exist_ok=True)

    project_name = root.name or str(root)
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "name": project_name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "directories": PROJECT_DIRECTORIES,
    }
    _write_project_payload(project_file, payload)

    return ProjectInfo(name=project_name, root=root, project_file=project_file)


def rename_project(project: ProjectInfo | str | Path, new_name: str) -> ProjectInfo:
    """Change only the display name stored in project.json."""
    info = project if isinstance(project, ProjectInfo) else load_project(project)
    clean_name = new_name.strip()
    if not clean_name:
        raise ProjectValidationError("项目名称不能为空")
    if any(character in clean_name for character in ("\0", "\r", "\n")):
        raise ProjectValidationError("项目名称不能包含换行或空字符")

    payload = _read_project_payload(info.project_file)
    payload["name"] = clean_name
    _write_project_payload(info.project_file, payload)
    return ProjectInfo(
        name=clean_name,
        root=info.root,
        project_file=info.project_file,
    )


def delete_project(project: ProjectInfo | str | Path) -> None:
    """Move a validated project directory to the Windows Recycle Bin."""
    info = project if isinstance(project, ProjectInfo) else load_project(project)
    try:
        send2trash(str(info.root))
    except OSError as error:
        raise ProjectError(f"无法将项目移入回收站：{info.root}") from error
