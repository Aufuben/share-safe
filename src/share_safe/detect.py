from __future__ import annotations

from pathlib import Path

import piexif

from share_safe.models import (
    GPS_COORD_TAGS,
    HEIC_EXT,
    JPEG_EXT,
    PDF_EXT,
    PNG_EXT,
    WEBP_EXT,
    XMP_GPS_MARKERS,
)


def _decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.split(b"\x00", 1)[0].decode("utf-8", "replace")
    if isinstance(value, tuple) and value and isinstance(value[0], tuple):
        return str(value)
    return str(value)


def gps_ifd_has_location(gps: dict | None) -> bool:
    if not gps:
        return False
    return any(tag in gps for tag in GPS_COORD_TAGS)


def exif_findings(exif: dict) -> tuple[bool, list[str]]:
    found: list[str] = []
    gps = exif.get("GPS") or {}
    had_gps = gps_ifd_has_location(gps)
    if had_gps:
        parts = []
        if piexif.GPSIFD.GPSLatitude in gps:
            parts.append("latitude")
        if piexif.GPSIFD.GPSLongitude in gps:
            parts.append("longitude")
        if piexif.GPSIFD.GPSAltitude in gps:
            parts.append("altitude")
        found.append("GPS (EXIF GPS IFD: " + ", ".join(parts or ["location tags"]) + ")")
    if exif.get("thumbnail"):
        found.append("embedded EXIF thumbnail (may contain its own GPS)")
        had_gps = had_gps or _thumbnail_has_gps(exif.get("thumbnail"))
    zeroth = exif.get("0th") or {}
    make = _decode(zeroth.get(piexif.ImageIFD.Make, b"")).strip()
    model = _decode(zeroth.get(piexif.ImageIFD.Model, b"")).strip()
    if make or model:
        found.append(f"device make/model ({(make + ' ' + model).strip()})")
    artist = zeroth.get(piexif.ImageIFD.Artist)
    if artist:
        found.append(f"artist ({_decode(artist)})")
    exif_ifd = exif.get("Exif") or {}
    serial = exif_ifd.get(piexif.ExifIFD.BodySerialNumber) or exif_ifd.get(
        piexif.ExifIFD.LensSerialNumber
    )
    if serial:
        found.append(f"camera serial number ({_decode(serial)})")
    if piexif.ExifIFD.MakerNote in exif_ifd:
        found.append("MakerNote (often contains serial / unique IDs)")
    return had_gps, found


def _thumbnail_has_gps(thumb: bytes | None) -> bool:
    if not thumb:
        return False
    try:
        nested = piexif.load(thumb)
    except Exception:
        return False
    return gps_ifd_has_location(nested.get("GPS") or {})


def load_jpeg_exif(path: Path) -> dict | None:
    try:
        return piexif.load(str(path))
    except Exception:
        try:
            return piexif.load(path.read_bytes())
        except Exception:
            return None


def bytes_have_xmp_gps(data: bytes) -> bool:
    return any(marker in data for marker in XMP_GPS_MARKERS)


def inspect_file(path: Path) -> tuple[bool, list[str], list[str]]:
    """Return (had_gps, found, remaining_hints)."""
    suffix = path.suffix.lower()
    remaining: list[str] = []
    if suffix in JPEG_EXT or _is_jpeg(path):
        return _inspect_jpeg(path)
    if suffix in PNG_EXT or _is_png(path):
        return _inspect_png(path)
    if suffix in WEBP_EXT or _is_webp(path):
        return _inspect_webp(path)
    if suffix in PDF_EXT or _is_pdf(path):
        from share_safe.pdfs import inspect_pdf

        return inspect_pdf(path)
    if suffix in HEIC_EXT:
        return _inspect_heic(path)
    return False, [f"unsupported file type ({suffix or 'unknown'})"], remaining


def _is_jpeg(path: Path) -> bool:
    try:
        return path.read_bytes()[:2] == b"\xff\xd8"
    except OSError:
        return False


def _is_png(path: Path) -> bool:
    try:
        return path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def _is_webp(path: Path) -> bool:
    try:
        data = path.read_bytes()[:12]
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    except OSError:
        return False


def _is_pdf(path: Path) -> bool:
    try:
        return path.read_bytes()[:4] == b"%PDF"
    except OSError:
        return False


def _inspect_jpeg(path: Path) -> tuple[bool, list[str], list[str]]:
    data = path.read_bytes()
    exif = load_jpeg_exif(path) or {}
    had_gps, found = exif_findings(exif)
    if bytes_have_xmp_gps(data):
        had_gps = True
        if not any("XMP" in item for item in found):
            found.append("GPS in XMP packet")
    if b"\xff\xed" in data[: min(len(data), 256_000)]:
        found.append("IPTC/Photoshop APP13 metadata (may include location)")
    remaining = _remaining_from_exif(exif, kind="JPEG", size=_image_size_label(path))
    return had_gps, found, remaining


def _inspect_png(path: Path) -> tuple[bool, list[str], list[str]]:
    from share_safe.images import png_metadata_findings

    return png_metadata_findings(path)


def _inspect_webp(path: Path) -> tuple[bool, list[str], list[str]]:
    from share_safe.images import webp_metadata_findings

    return webp_metadata_findings(path)


def _inspect_heic(path: Path) -> tuple[bool, list[str], list[str]]:
    try:
        import pillow_heif
        from PIL import Image

        pillow_heif.register_heif_opener()
        with Image.open(path) as im:
            exif = im.getexif()
            gps = {}
            try:
                gps = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else {}
            except Exception:
                gps = {}
            had = bool(gps)
            found = ["GPS (HEIC EXIF)"] if had else []
            make = exif.get(271)
            model = exif.get(272)
            if make or model:
                found.append(f"device make/model ({make or ''} {model or ''})".strip())
            remaining = [f"image pixels ({im.size[0]}×{im.size[1]} HEIC)"]
            return had, found, remaining
    except ImportError:
        return False, [], ["HEIC support not installed"]
    except Exception:
        return False, [], ["could not parse HEIC"]


def _image_size_label(path: Path) -> str:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return f"{im.size[0]}×{im.size[1]} {im.format or path.suffix.lstrip('.').upper()}"
    except Exception:
        return path.suffix.lstrip(".").upper() or "image"


def _remaining_from_exif(exif: dict, *, kind: str, size: str) -> list[str]:
    items = [f"image pixels ({size})"]
    zeroth = exif.get("0th") or {}
    if piexif.ImageIFD.Orientation in zeroth:
        items.append(f"Orientation ({zeroth[piexif.ImageIFD.Orientation]})")
    exif_ifd = exif.get("Exif") or {}
    dto = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
    if dto:
        items.append(f"DateTimeOriginal: {_decode(dto)}")
    if piexif.ImageIFD.Copyright in zeroth:
        items.append(f"Copyright: {_decode(zeroth[piexif.ImageIFD.Copyright])}")
    settings = []
    for tag, name in (
        (piexif.ExifIFD.ExposureTime, "ExposureTime"),
        (piexif.ExifIFD.FNumber, "FNumber"),
        (piexif.ExifIFD.ISOSpeedRatings, "ISO"),
        (piexif.ExifIFD.FocalLength, "FocalLength"),
    ):
        if tag in exif_ifd:
            settings.append(name)
    if settings:
        items.append("camera exposure tags (" + ", ".join(settings) + ")")
    return items


def load_exif_from_raw(payload: bytes) -> dict | None:
    """Load piexif dict from an APP1 Exif payload (starts with Exif\\x00\\x00) or raw TIFF."""
    body = payload
    if body.startswith(b"Exif\x00\x00"):
        inner = body
    else:
        inner = b"Exif\x00\x00" + body
    if len(inner) + 2 > 65535:
        inner = inner[:65533]
    dummy = b"\xff\xd8\xff\xe1" + (len(inner) + 2).to_bytes(2, "big") + inner + b"\xff\xd9"
    try:
        return piexif.load(dummy)
    except Exception:
        return None
