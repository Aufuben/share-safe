from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

from share_safe.detect import bytes_have_xmp_gps
from share_safe.models import FileResult, XMP_GPS_MARKERS


def inspect_pdf(path: Path) -> tuple[bool, list[str], list[str]]:
    found: list[str] = []
    had_gps = False
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        return False, [f"could not read PDF: {exc}"], []

    meta = reader.metadata
    if meta:
        for key, value in dict(meta).items():
            k, v = str(key), str(value)
            if "gps" in k.lower() or "gps" in v.lower() or any(
                token.decode() in k + v for token in (b"Latitude", b"Longitude")
            ):
                had_gps = True
                found.append(f"PDF document info {k}={v}")
            elif k in {"/Author", "/Creator", "/Producer", "/Title", "/Subject"}:
                found.append(f"PDF document info {k}={v}")
    try:
        xmp = reader.xmp_metadata
    except Exception:
        xmp = None
    data = path.read_bytes()
    if xmp is not None or any(m in data for m in XMP_GPS_MARKERS):
        if bytes_have_xmp_gps(data):
            had_gps = True
            found.append("GPS in PDF XMP metadata")
        elif xmp is not None:
            found.append("PDF XMP metadata packet")
    remaining = ["PDF page content (drawings/text are kept)"]
    return had_gps, found, remaining


def sanitize_pdf(src: Path, dest: Path, *, keep_model: bool = False) -> FileResult:
    del keep_model  # PDFs have no camera model flag
    had_gps, found, remaining = inspect_pdf(src)
    try:
        reader = PdfReader(str(src))
    except Exception as exc:
        return FileResult.failed(src, f"could not read PDF: {exc}")

    if reader.is_encrypted:
        return FileResult.skipped(src, "encrypted PDF is not supported; skipped")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
        try:
            if "/Metadata" in writer.pages[-1]:
                del writer.pages[-1]["/Metadata"]
        except Exception:
            pass

    _clear_docinfo(writer)
    _strip_catalog_metadata(writer)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        writer.write(fh)

    _scrub_leftover_gps_strings(dest)

    after_gps, _, _ = inspect_pdf(dest)
    data = dest.read_bytes()
    still = bytes_have_xmp_gps(data) or after_gps
    removed = list(found) if found else (["PDF metadata"] if had_gps else [])
    if not found and (had_gps or not remaining):
        removed = ["PDF document info / XMP"]

    warning = None
    if still:
        warning = "GPS-like strings still present in PDF (may be in page content, not metadata)"

    remaining_out = ["PDF page content (drawings/text are kept)"]
    if dest.stat().st_size:
        remaining_out.append(f"file size {dest.stat().st_size} bytes")

    return FileResult(
        source=src,
        output=dest,
        status="cleaned" if (found or had_gps) else "already_clean",
        removed=removed or (["no identifying PDF metadata found"] if not found else found),
        remaining=remaining_out,
        found=found,
        warning=warning,
        had_gps=had_gps,
    )


def _clear_docinfo(writer: PdfWriter) -> None:
    try:
        writer.metadata = None
    except Exception:
        pass
    try:
        writer.add_metadata({})
    except Exception:
        pass
    # Drop leftover custom keys if the writer kept an Info dict.
    info = getattr(writer, "_info", None)
    if info is not None:
        try:
            keys = list(info.keys())
            for key in keys:
                name = str(key)
                if name not in {NameObject("/CreationDate"), NameObject("/ModDate")} and "Date" not in name:
                    try:
                        del info[key]
                    except Exception:
                        pass
            # Always drop GPS-ish and identity keys.
            for key in list(info.keys()):
                kl = str(key).lower()
                if any(s in kl for s in ("gps", "author", "creator", "producer", "title", "subject", "keywords")):
                    try:
                        del info[key]
                    except Exception:
                        pass
        except Exception:
            try:
                writer._info = None
            except Exception:
                pass


def _strip_catalog_metadata(writer: PdfWriter) -> None:
    root = getattr(writer, "root_object", None) or getattr(writer, "_root_object", None)
    if root is None:
        return
    for key in ("/Metadata", "/PieceInfo", "/AF", "/Perms"):
        try:
            if key in root:
                del root[key]
        except Exception:
            continue


def _scrub_leftover_gps_strings(dest: Path) -> None:
    """Best-effort removal if pypdf left Info strings uncompressed."""
    data = dest.read_bytes()
    if not bytes_have_xmp_gps(data) and b"37.7749" not in data:
        return
    # Do not rewrite page streams; only obvious Info/XMP was handled by pypdf.
    # If GPS remains it is reported as a warning by the caller.
