"""Generate known GPS fixtures in-memory / tmp dirs. No network, no committed binaries."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import piexif
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

SRC = Path(__file__).resolve().parents[1] / "src"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "share_safe", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )

GPS_LAT = 37.7749
GPS_LON = -122.4194


def jpeg_with_gps(path: Path, *, serial: str = "SN123456789", model: str = "TestCam 9000") -> Path:
    """Write a small JPEG whose EXIF GPS IFD has known coordinates."""
    img = Image.new("RGB", (32, 24), (220, 40, 40))
    gps_ifd = {
        piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0),
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((37, 1), (46, 1), (2964, 100)),
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLongitude: ((122, 1), (25, 1), (984, 100)),
        piexif.GPSIFD.GPSAltitudeRef: 0,
        piexif.GPSIFD.GPSAltitude: (15, 1),
    }
    zeroth = {
        piexif.ImageIFD.Make: b"TestBrand",
        piexif.ImageIFD.Model: model.encode("utf-8"),
        piexif.ImageIFD.Software: b"share-safe-fixture",
        piexif.ImageIFD.Orientation: 1,
        piexif.ImageIFD.XResolution: (72, 1),
        piexif.ImageIFD.YResolution: (72, 1),
        piexif.ImageIFD.ResolutionUnit: 2,
        piexif.ImageIFD.Artist: b"Fixture Photographer",
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: b"2024:01:15 12:00:00",
        piexif.ExifIFD.BodySerialNumber: serial.encode("utf-8"),
        piexif.ExifIFD.ColorSpace: 1,
        piexif.ExifIFD.PixelXDimension: 32,
        piexif.ExifIFD.PixelYDimension: 24,
    }
    thumb = Image.new("RGB", (8, 8), (0, 255, 0))
    thumb_buf = io.BytesIO()
    thumb_exif = piexif.dump(
        {
            "0th": {piexif.ImageIFD.Make: b"ThumbCam"},
            "GPS": dict(gps_ifd),
            "Exif": {},
            "1st": {},
            "thumbnail": None,
        }
    )
    thumb.save(thumb_buf, format="JPEG", exif=thumb_exif)
    exif_bytes = piexif.dump(
        {
            "0th": zeroth,
            "Exif": exif_ifd,
            "GPS": gps_ifd,
            "1st": {
                piexif.ImageIFD.Compression: 6,
                piexif.ImageIFD.Make: b"TestBrand",
            },
            "thumbnail": thumb_buf.getvalue(),
        }
    )
    img.save(path, format="JPEG", quality=90, exif=exif_bytes)
    return path


def jpeg_without_gps(path: Path) -> Path:
    img = Image.new("RGB", (16, 16), (10, 20, 200))
    zeroth = {
        piexif.ImageIFD.Orientation: 1,
        piexif.ImageIFD.XResolution: (72, 1),
        piexif.ImageIFD.YResolution: (72, 1),
        piexif.ImageIFD.ResolutionUnit: 2,
    }
    exif_bytes = piexif.dump({"0th": zeroth, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None})
    img.save(path, format="JPEG", quality=85, exif=exif_bytes)
    return path


def png_with_gps(path: Path) -> Path:
    img = Image.new("RGB", (20, 20), (0, 180, 80))
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((37, 1), (46, 1), (0, 1)),
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLongitude: ((122, 1), (25, 1), (0, 1)),
    }
    exif_bytes = piexif.dump(
        {
            "0th": {piexif.ImageIFD.Make: b"PNGCam", piexif.ImageIFD.Model: b"PNG-1"},
            "Exif": {},
            "GPS": gps_ifd,
            "1st": {},
            "thumbnail": None,
        }
    )
    img.save(path, format="PNG", exif=exif_bytes)
    return path


def webp_with_gps(path: Path) -> Path:
    img = Image.new("RGB", (20, 20), (80, 0, 180))
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"S",
        piexif.GPSIFD.GPSLatitude: ((33, 1), (52, 1), (0, 1)),
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLongitude: ((151, 1), (12, 1), (0, 1)),
    }
    exif_bytes = piexif.dump(
        {
            "0th": {piexif.ImageIFD.Make: b"WebPCam"},
            "GPS": gps_ifd,
            "Exif": {},
            "1st": {},
            "thumbnail": None,
        }
    )
    img.save(path, format="WEBP", exif=exif_bytes)
    return path


XMP_GPS = """<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:exif="http://ns.adobe.com/exif/1.0/"
        exif:GPSLatitude="37,46.494N"
        exif:GPSLongitude="122,25.161W"
        exif:GPSAltitude="15"/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
""".encode("utf-8")


def pdf_with_gps(path: Path) -> Path:
    """PDF whose Info dict and XMP both contain GPS."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata(
        {
            "/Title": "Test Scan",
            "/Author": "Fixture Author",
            "/GPSLatitude": str(GPS_LAT),
            "/GPSLongitude": str(GPS_LON),
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(XMP_GPS)
    stream.update(
        {
            NameObject("/Type"): NameObject("/Metadata"),
            NameObject("/Subtype"): NameObject("/XML"),
        }
    )
    writer._root_object[NameObject("/Metadata")] = writer._add_object(stream)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        writer.write(fh)
    return path


def jpeg_has_gps_tags(path: Path) -> bool:
    """Verify GPS using piexif (same approach CI must use)."""
    exif = piexif.load(str(path))
    gps = exif.get("GPS") or {}
    return any(
        tag in gps
        for tag in (
            piexif.GPSIFD.GPSLatitude,
            piexif.GPSIFD.GPSLongitude,
            piexif.GPSIFD.GPSAltitude,
            piexif.GPSIFD.GPSDestLatitude,
            piexif.GPSIFD.GPSDestLongitude,
            piexif.GPSIFD.GPSImgDirection,
        )
    )


def file_bytes_mention_gps_xmp(path: Path) -> bool:
    data = Path(path).read_bytes()
    return b"GPSLatitude" in data or b"GPSLongitude" in data
