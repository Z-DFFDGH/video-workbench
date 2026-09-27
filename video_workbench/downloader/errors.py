from __future__ import annotations


class DownloadError(Exception):
    """Base exception for download failures."""


class DownloadCanceled(DownloadError):
    """Raised when the active download is canceled by the user."""


class SourceResolutionError(DownloadError):
    """Raised when a source URL cannot be resolved to downloadable media."""
