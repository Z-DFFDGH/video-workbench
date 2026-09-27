from .importer import (
    MaterialImportError,
    MaterialLibrary,
    MaterialNotFoundError,
    copy_material_file,
    unique_destination,
)
from .metadata import FFprobeDetector, MediaDetectionError
from .models import (
    MaterialRecord,
    MaterialStatus,
    MediaMetadata,
    MediaType,
    normalize_tags,
)
from .repository import (
    MATERIAL_INDEX_FILE_NAME,
    MATERIAL_INDEX_SCHEMA_VERSION,
    MaterialRepository,
    MaterialRepositoryError,
)
from .thumbnails import FFmpegThumbnailGenerator, ThumbnailGenerationError

__all__ = [
    "FFmpegThumbnailGenerator",
    "FFprobeDetector",
    "MATERIAL_INDEX_FILE_NAME",
    "MATERIAL_INDEX_SCHEMA_VERSION",
    "MaterialImportError",
    "MaterialLibrary",
    "MaterialNotFoundError",
    "MaterialRecord",
    "MaterialRepository",
    "MaterialRepositoryError",
    "MaterialStatus",
    "MediaDetectionError",
    "MediaMetadata",
    "MediaType",
    "ThumbnailGenerationError",
    "copy_material_file",
    "normalize_tags",
    "unique_destination",
]
