from __future__ import annotations

from pathlib import Path

import piexif

from share_safe.detect import (
    bytes_have_xmp_gps,
    exif_findings,
    gps_ifd_has_location,
    load_exif_from_raw,
    load_jpeg_exif,
)
from share_safe.models import FileResult, HEIC_EXT

PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_DROP = {b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"}

KEEP_0TH = {
    piexif.ImageIFD.Orientation,
    piexif.ImageIFD.XResolution,
    piexif.ImageIFD.YResolution,
    piexif.ImageIFD.ResolutionUnit,
    piexif.ImageIFD.YCbCrPositioning,
    piexif.ImageIFD.YCbCrSubSampling,
    piexif.ImageIFD.Compression,
    piexif.ImageIFD.PhotometricInterpretation,
    piexif.ImageIFD.BitsPerSample,
    piexif.ImageIFD.SamplesPerPixel,
    piexif.ImageIFD.ImageWidth,
    piexif.ImageIFD.ImageLength,
    piexif.ImageIFD.Copyright,
}

KEEP_EXIF = {
    piexif.ExifIFD.ExifVersion,
    piexif.ExifIFD.FlashpixVersion,
    piexif.ExifIFD.ColorSpace,
    piexif.ExifIFD.PixelXDimension,
    piexif.ExifIFD.PixelYDimension,
    piexif.ExifIFD.DateTimeOriginal,
    piexif.ExifIFD.DateTimeDigitized,
    piexif.ExifIFD.ExposureTime,
    piexif.ExifIFD.FNumber,
    piexif.ExifIFD.ExposureProgram,
    piexif.ExifIFD.ISOSpeedRatings,
    piexif.ExifIFD.ShutterSpeedValue,
    piexif.ExifIFD.ApertureValue,
    piexif.ExifIFD.BrightnessValue,
    piexif.ExifIFD.ExposureBiasValue,
    piexif.ExifIFD.MaxApertureValue,
    piexif.ExifIFD.MeteringMode,
    piexif.ExifIFD.Flash,
    piexif.ExifIFD.FocalLength,
    piexif.ExifIFD.WhiteBalance,
    piexif.ExifIFD.FocalLengthIn35mmFilm,
    piexif.ExifIFD.SceneCaptureType,
    piexif.ExifIFD.Contrast,
    piexif.ExifIFD.Saturation,
    piexif.ExifIFD.Sharpness,
    piexif.ExifIFD.ComponentsConfiguration,
    piexif.ExifIFD.ExposureMode,
}

MODEL_0TH = {piexif.ImageIFD.Make, piexif.ImageIFD.Model}
MODEL_EXIF = {piexif.ExifIFD.LensMake, piexif.ExifIFD.LensModel}


def sanitize_image(src: Path, dest: Path, *, keep_model: bool = False) -> FileResult:
    suffix = src.suffix.lower()
    data = src.read_bytes()
    if suffix in HEIC_EXT:
        return sanitize_heic(src, dest, keep_model=keep_model)
    if data[:2] == b"\xff\xd8" or suffix in {".jpg", ".jpeg"}:
        return sanitize_jpeg(src, dest, data, keep_model=keep_model)
    if data[:8] == PNG_SIG or suffix == ".png":
        return sanitize_png(src, dest, data, keep_model=keep_model)
    if (data[:4] == b"RIFF" and data[8:12] == b"WEBP") or suffix == ".webp":
        return sanitize_webp(src, dest, data, keep_model=keep_model)
    return FileResult.skipped(src, f"unsupported image type ({suffix or 'unknown'}); skipped")


def sanitize_jpeg(src: Path, dest: Path, data: bytes, *, keep_model: bool) -> FileResult:
    original_exif = load_jpeg_exif(src) or {}
    had_gps, found = exif_findings(original_exif)
    extra_removed: list[str] = []
    if bytes_have_xmp_gps(data) or b"http://ns.adobe.com/xap/1.0/" in data:
        if bytes_have_xmp_gps(data):
            had_gps = True
        extra_removed.append("XMP packet")
    if _has_marker(data, 0xED):
        extra_removed.append("IPTC/Photoshop metadata (APP13)")
    if _has_marker(data, 0xFE):
        extra_removed.append("JPEG comment")

    cleaned_bytes, strip_notes = _rewrite_jpeg(data, keep_model=keep_model)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(cleaned_bytes)

    after = load_jpeg_exif(dest) or {}
    still_gps = gps_ifd_has_location(after.get("GPS") or {}) or bytes_have_xmp_gps(cleaned_bytes)
    removed = list(dict.fromkeys(found + extra_removed + strip_notes))
    remaining = _remaining_pixels_and_exif(dest, after, kind="JPEG")
    warning = "GPS tags still present after sanitizing" if still_gps else None
    status = "cleaned" if removed else "already_clean"
    if not removed:
        removed = []
    return FileResult(
        source=src,
        output=dest,
        status=status,
        removed=removed,
        remaining=remaining,
        found=found,
        warning=warning,
        had_gps=had_gps,
    )


def _has_marker(data: bytes, marker_type: int) -> bool:
    needle = bytes([0xFF, marker_type])
    return needle in data[: min(len(data), 512_000)]


def _rewrite_jpeg(data: bytes, *, keep_model: bool) -> tuple[bytes, list[str]]:
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG file")
    out = bytearray(b"\xff\xd8")
    notes: list[str] = []
    pos = 2
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            out.extend(data[pos:])
            break
        while pos < n and data[pos] == 0xFF:
            nxt = data[pos + 1] if pos + 1 < n else 0
            if nxt == 0xFF:
                pos += 1
                continue
            break
        if pos >= n:
            break
        if data[pos] != 0xFF:
            out.extend(data[pos:])
            break
        marker_type = data[pos + 1]
        pos += 2
        if marker_type in {0x01, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8}:
            out.extend(bytes([0xFF, marker_type]))
            continue
        if marker_type == 0xD9:
            out.extend(b"\xff\xd9")
            break
        if pos + 2 > n:
            out.extend(data[pos - 2 :])
            break
        seglen = int.from_bytes(data[pos : pos + 2], "big")
        if seglen < 2 or pos + seglen > n:
            out.extend(data[pos - 2 :])
            break
        payload = data[pos + 2 : pos + seglen]
        pos += seglen
        if marker_type == 0xDA:
            out.extend(bytes([0xFF, marker_type]))
            out.extend((seglen).to_bytes(2, "big"))
            out.extend(payload)
            out.extend(data[pos:])
            break
        if marker_type == 0xE1:
            rebuilt = _handle_app1(payload, keep_model=keep_model, notes=notes)
            if rebuilt is not None:
                out.extend(rebuilt)
            continue
        if marker_type == 0xED:
            notes.append("IPTC/Photoshop APP13")
            continue
        if marker_type == 0xFE:
            notes.append("JPEG COM comment")
            continue
        if marker_type == 0xE2 and not payload.startswith(b"ICC_PROFILE"):
            notes.append("APP2 metadata (non-ICC, e.g. MPF thumbnail)")
            continue
        out.extend(bytes([0xFF, marker_type]))
        out.extend(seglen.to_bytes(2, "big"))
        out.extend(payload)
    return bytes(out), list(dict.fromkeys(notes))


def _handle_app1(payload: bytes, *, keep_model: bool, notes: list[str]) -> bytes | None:
    if payload.startswith(b"http://ns.adobe.com/xap/1.0/") or payload.startswith(
        b"http://ns.adobe.com/xmp/extension/"
    ):
        notes.append("XMP")
        return None
    if b"<x:xmpmeta" in payload[:300]:
        notes.append("XMP")
        return None
    if not payload.startswith(b"Exif\x00\x00"):
        return _wrap_app1(payload)
    cleaned = _clean_exif_payload(payload, keep_model=keep_model)
    if cleaned is None:
        notes.append("EXIF (dropped; could not rewrite safely)")
        return None
    return _wrap_app1(cleaned)


def _wrap_app1(payload: bytes) -> bytes | None:
    length = len(payload) + 2
    if length > 65535:
        return None
    return b"\xff\xe1" + length.to_bytes(2, "big") + payload


def _clean_exif_payload(payload: bytes, *, keep_model: bool) -> bytes | None:
    exif = load_exif_from_raw(payload)
    if exif is None:
        return None
    cleaned = clean_exif_dict(exif, keep_model=keep_model)
    try:
        dumped = piexif.dump(cleaned)
    except Exception:
        try:
            dumped = piexif.dump({"0th": cleaned.get("0th") or {}, "Exif": {}, "1st": {}, "thumbnail": None})
        except Exception:
            return None
    return dumped


def clean_exif_dict(exif: dict, *, keep_model: bool) -> dict:
    keep0 = set(KEEP_0TH)
    keep_exif = set(KEEP_EXIF)
    if keep_model:
        keep0 |= MODEL_0TH
        keep_exif |= MODEL_EXIF
    new0 = {k: v for k, v in (exif.get("0th") or {}).items() if k in keep0}
    new_exif = {k: v for k, v in (exif.get("Exif") or {}).items() if k in keep_exif}
    out: dict = {"0th": new0, "Exif": new_exif, "1st": {}, "thumbnail": None}
    return out


def _remaining_pixels_and_exif(path: Path, exif: dict, *, kind: str) -> list[str]:
    items: list[str] = []
    try:
        from PIL import Image

        with Image.open(path) as im:
            items.append(f"image pixels ({im.size[0]}×{im.size[1]} {kind})")
    except Exception:
        items.append(f"image pixels ({kind})")
    zeroth = exif.get("0th") or {}
    if piexif.ImageIFD.Orientation in zeroth:
        items.append(f"Orientation ({zeroth[piexif.ImageIFD.Orientation]})")
    exif_ifd = exif.get("Exif") or {}
    dto = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
    if dto:
        if isinstance(dto, bytes):
            dto = dto.decode("utf-8", "replace")
        items.append(f"DateTimeOriginal: {dto}")
    if piexif.ImageIFD.Copyright in zeroth:
        copy = zeroth[piexif.ImageIFD.Copyright]
        if isinstance(copy, bytes):
            copy = copy.decode("utf-8", "replace")
        items.append(f"Copyright: {copy}")
    return items


def sanitize_png(src: Path, dest: Path, data: bytes, *, keep_model: bool) -> FileResult:
    del keep_model
    had_gps, found, remaining_in = png_metadata_findings_from_bytes(data, src)
    out = bytearray(PNG_SIG)
    pos = 8
    dropped: list[str] = []
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        ctype = data[pos + 4 : pos + 8]
        end = pos + 12 + length
        if end > len(data):
            break
        chunk = data[pos:end]
        pos = end
        if ctype in PNG_DROP:
            dropped.append(ctype.decode("ascii", "replace"))
            continue
        out.extend(chunk)
        if ctype == b"IEND":
            break
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(out))
    removed = list(dict.fromkeys(found + [f"PNG chunk {name}" for name in dropped]))
    remaining = remaining_in or [f"PNG pixels ({src.name})"]
    try:
        from PIL import Image

        with Image.open(dest) as im:
            remaining = [f"image pixels ({im.size[0]}×{im.size[1]} PNG)"]
    except Exception:
        pass
    return FileResult(
        source=src,
        output=dest,
        status="cleaned" if dropped or found else "already_clean",
        removed=removed,
        remaining=remaining,
        found=found,
        had_gps=had_gps,
    )


def png_metadata_findings(path: Path) -> tuple[bool, list[str], list[str]]:
    return png_metadata_findings_from_bytes(path.read_bytes(), path)


def png_metadata_findings_from_bytes(data: bytes, path: Path) -> tuple[bool, list[str], list[str]]:
    found: list[str] = []
    had_gps = False
    if data[:8] != PNG_SIG:
        return False, ["not a PNG"], []
    pos = 8
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        ctype = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"eXIf":
            exif = load_exif_from_raw(chunk_data)
            if exif:
                g, items = exif_findings(exif)
                had_gps = had_gps or g
                found.extend(items)
            else:
                found.append("PNG eXIf chunk")
        elif ctype in {b"tEXt", b"zTXt", b"iTXt"}:
            if any(m in chunk_data for m in (b"GPS", b"gps", b"location", b"Location")):
                had_gps = True
                found.append(f"PNG text chunk with location ({ctype.decode()})")
            else:
                found.append(f"PNG text metadata ({ctype.decode()})")
        if ctype == b"IEND":
            break
    remaining = [f"image pixels (PNG {path.name})"]
    return had_gps, found, remaining


def sanitize_webp(src: Path, dest: Path, data: bytes, *, keep_model: bool) -> FileResult:
    del keep_model
    had_gps, found, remaining = webp_metadata_findings_from_bytes(data, src)
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return FileResult.failed(src, "not a WebP file")
    chunks: list[tuple[bytes, bytes]] = []
    pos = 12
    dropped = False
    while pos + 8 <= len(data):
        fourcc = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        payload = data[pos + 8 : pos + 8 + size]
        pad = size % 2
        pos += 8 + size + pad
        if fourcc in {b"EXIF", b"XMP "}:
            dropped = True
            continue
        chunks.append((fourcc, payload))
    body = bytearray()
    for fourcc, payload in chunks:
        body.extend(fourcc)
        body.extend(len(payload).to_bytes(4, "little"))
        body.extend(payload)
        if len(payload) % 2:
            body.append(0)
    out = b"RIFF" + (4 + len(body)).to_bytes(4, "little") + b"WEBP" + bytes(body)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out)
    remaining_out = remaining
    try:
        from PIL import Image

        with Image.open(dest) as im:
            remaining_out = [f"image pixels ({im.size[0]}×{im.size[1]} WebP)"]
    except Exception:
        pass
    return FileResult(
        source=src,
        output=dest,
        status="cleaned" if dropped or found else "already_clean",
        removed=found or (["WebP EXIF/XMP"] if dropped else []),
        remaining=remaining_out,
        found=found,
        had_gps=had_gps,
    )


def webp_metadata_findings(path: Path) -> tuple[bool, list[str], list[str]]:
    return webp_metadata_findings_from_bytes(path.read_bytes(), path)


def webp_metadata_findings_from_bytes(data: bytes, path: Path) -> tuple[bool, list[str], list[str]]:
    found: list[str] = []
    had_gps = False
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False, ["not a WebP"], []
    pos = 12
    while pos + 8 <= len(data):
        fourcc = data[pos : pos + 4]
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        payload = data[pos + 8 : pos + 8 + size]
        pos += 8 + size + (size % 2)
        if fourcc == b"EXIF":
            exif = load_exif_from_raw(payload)
            if exif:
                g, items = exif_findings(exif)
                had_gps = had_gps or g
                found.extend(items)
            else:
                found.append("WebP EXIF chunk")
                if bytes_have_xmp_gps(payload) or gps_ifd_has_location(
                    (load_exif_from_raw(payload) or {}).get("GPS")
                ):
                    had_gps = True
        elif fourcc == b"XMP ":
            found.append("WebP XMP chunk")
            if bytes_have_xmp_gps(payload):
                had_gps = True
                found.append("GPS in WebP XMP")
    remaining = [f"image pixels (WebP {path.name})"]
    return had_gps, found, remaining


def sanitize_heic(src: Path, dest: Path, *, keep_model: bool) -> FileResult:
    del keep_model
    try:
        import pillow_heif
    except ImportError:
        return FileResult.skipped(
            src,
            'HEIC/HEIF is not supported in this install (pip install "share-safe[heic]"). Skipping.',
        )
    try:
        from PIL import Image

        pillow_heif.register_heif_opener()
        with Image.open(src) as im:
            im.load()
            had_gps, found, remaining = _heic_findings(im)
            dest.parent.mkdir(parents=True, exist_ok=True)
            save_im = im.convert(im.mode) if im.mode else im
            save_im.save(dest, format="HEIF")
        return FileResult(
            source=src,
            output=dest,
            status="cleaned",
            removed=found or ["HEIC metadata (best-effort strip on save)"],
            remaining=remaining or ["image pixels (HEIC)"],
            found=found,
            had_gps=had_gps,
            warning="HEIC sanitizing re-encodes the image via pillow-heif",
        )
    except Exception as exc:
        return FileResult.skipped(src, f"could not read HEIC/HEIF ({exc}). Skipping.")


def _heic_findings(im) -> tuple[bool, list[str], list[str]]:
    found: list[str] = []
    had_gps = False
    try:
        exif = im.getexif()
        gps = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else {}
        if gps:
            had_gps = True
            found.append("GPS (HEIC EXIF)")
        make, model = exif.get(271), exif.get(272)
        if make or model:
            found.append(f"device make/model ({make or ''} {model or ''})".strip())
    except Exception:
        pass
    remaining = [f"image pixels ({im.size[0]}×{im.size[1]} HEIC)"]
    return had_gps, found, remaining
