from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".hif"}
JPEG_EXT = {".jpg", ".jpeg"}
PNG_EXT = {".png"}
WEBP_EXT = {".webp"}
HEIC_EXT = {".heic", ".heif", ".hif"}
PDF_EXT = {".pdf"}
SUPPORTED_EXT = IMAGE_EXT | PDF_EXT

GPS_COORD_TAGS = {1, 2, 3, 4, 5, 6, 17, 18, 19, 20, 22, 23, 24}
XMP_GPS_MARKERS = (b"GPSLatitude", b"GPSLongitude", b"gps:GPSLatitude", b"exif:GPS")


class UsageError(ValueError):
    """Invalid CLI usage."""


@dataclass
class FileResult:
    source: Path
    output: Path | None = None
    status: str = "cleaned"
    removed: list[str] = field(default_factory=list)
    remaining: list[str] = field(default_factory=list)
    found: list[str] = field(default_factory=list)
    warning: str | None = None
    error: str | None = None
    had_gps: bool = False

    @classmethod
    def skipped(cls, source: Path, warning: str) -> FileResult:
        return cls(source=source, status="skipped", warning=warning)

    @classmethod
    def failed(cls, source: Path, error: str) -> FileResult:
        return cls(source=source, status="error", error=error)
