from __future__ import annotations

from pathlib import Path

from helpers import (
    file_bytes_mention_gps_xmp,
    jpeg_has_gps_tags,
    jpeg_with_gps,
    jpeg_without_gps,
    pdf_with_gps,
    png_with_gps,
    run_cli,
)


def test_batch_mixed_files(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    gps = jpeg_with_gps(inbox / "with_gps.jpg")
    clean = jpeg_without_gps(inbox / "clean.jpg")
    pdf = pdf_with_gps(inbox / "scan.pdf")
    notes = inbox / "readme.txt"
    notes.write_text("not an image", encoding="utf-8")
    dummy_heic = inbox / "phone.heic"
    dummy_heic.write_bytes(b"not-a-real-heic-file")
    png = png_with_gps(inbox / "shot.png")

    outdir = tmp_path / "safe"
    gps_bytes = gps.read_bytes()
    clean_bytes = clean.read_bytes()
    pdf_bytes = pdf.read_bytes()
    png_bytes = png.read_bytes()
    heic_bytes = dummy_heic.read_bytes()

    result = run_cli(str(inbox), "-o", str(outdir), "--report")
    assert result.returncode == 0, result.stdout + result.stderr
    text = result.stdout + result.stderr
    lower = text.lower()

    assert (outdir / "with_gps.jpg").is_file()
    assert (outdir / "clean.jpg").is_file()
    assert (outdir / "scan.pdf").is_file()
    assert (outdir / "shot.png").is_file()
    assert not (outdir / "readme.txt").exists()
    assert not (outdir / "phone.heic").exists()

    assert not jpeg_has_gps_tags(outdir / "with_gps.jpg")
    assert not jpeg_has_gps_tags(outdir / "clean.jpg")
    assert gps.read_bytes() == gps_bytes
    assert clean.read_bytes() == clean_bytes
    assert pdf.read_bytes() == pdf_bytes
    assert png.read_bytes() == png_bytes
    assert dummy_heic.read_bytes() == heic_bytes

    assert "heic" in lower
    assert "skip" in lower or "not support" in lower or "unsupported" in lower
    assert "gps" in lower


def test_directory_and_globs_do_not_crash_on_heic(tmp_path: Path) -> None:
    folder = tmp_path / "mix"
    folder.mkdir()
    jpeg_with_gps(folder / "a.jpg")
    (folder / "b.heic").write_bytes(b"ftypheic-placeholder")
    jpeg_with_gps(folder / "c.jpg")
    out = tmp_path / "out"
    result = run_cli(str(folder / "a.jpg"), str(folder / "b.heic"), str(folder / "c.jpg"), "-o", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out / "a.jpg").is_file()
    assert (out / "c.jpg").is_file()
    assert not jpeg_has_gps_tags(out / "a.jpg")
    assert not jpeg_has_gps_tags(out / "c.jpg")


def test_pdf_gps_stripped(tmp_path: Path) -> None:
    src = pdf_with_gps(tmp_path / "scan.pdf")
    assert file_bytes_mention_gps_xmp(src)
    out = tmp_path / "scan.safe.pdf"
    original = src.read_bytes()
    result = run_cli(str(src), "-o", str(out), "--report")
    assert result.returncode == 0, result.stdout + result.stderr
    assert src.read_bytes() == original
    from pypdf import PdfReader

    meta = PdfReader(str(out)).metadata
    if meta is not None:
        info = {str(k).lower(): str(v) for k, v in dict(meta).items()}
        assert not any("gps" in k or "37.7749" in v for k, v in info.items())
    data = out.read_bytes()
    assert b"GPSLatitude" not in data
    assert b"37.7749" not in data
    assert b"122.4194" not in data


def test_png_gps_stripped(tmp_path: Path) -> None:
    src = png_with_gps(tmp_path / "shot.png")
    out = tmp_path / "shot.safe.png"
    result = run_cli(str(src), "-o", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    from PIL import Image

    im = Image.open(out)
    exif = im.getexif()
    gps = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else {}
    assert not gps
    assert 0x8825 not in exif
