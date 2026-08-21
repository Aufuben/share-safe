from __future__ import annotations

from pathlib import Path

from helpers import jpeg_has_gps_tags, jpeg_with_gps, run_cli


def test_cli_help_exits_zero() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "share-safe" in combined.lower() or "usage:" in combined.lower()
    assert "-o" in combined or "--output" in combined
    assert "--check" in combined


def test_cli_version() -> None:
    result = run_cli("--version")
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1.0" in result.stderr


def test_check_detects_gps(tmp_path: Path) -> None:
    src = jpeg_with_gps(tmp_path / "photo.jpg")
    original = src.read_bytes()
    result = run_cli("--check", str(src))
    assert result.returncode != 0
    text = (result.stdout + result.stderr).lower()
    assert "gps" in text
    assert src.read_bytes() == original
    # --check must not write an output file
    assert list(tmp_path.glob("*.safe.*")) == []
    assert not (tmp_path / "photo.safe.jpg").exists()


def test_check_clean_file_exits_zero(tmp_path: Path) -> None:
    from helpers import jpeg_without_gps

    src = jpeg_without_gps(tmp_path / "clean.jpg")
    result = run_cli("--check", str(src))
    assert result.returncode == 0
    text = (result.stdout + result.stderr).lower()
    assert "gps" in text or "clean" in text


def test_jpeg_gps_stripped(tmp_path: Path) -> None:
    src = jpeg_with_gps(tmp_path / "photo.jpg")
    assert jpeg_has_gps_tags(src)
    out = tmp_path / "photo.safe.jpg"
    result = run_cli(str(src), "-o", str(out), "--report")
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.is_file()
    assert not jpeg_has_gps_tags(out)
    report = (result.stdout + result.stderr).lower()
    assert "gps" in report
    assert "removed" in report


def test_input_file_bytes_unchanged(tmp_path: Path) -> None:
    src = jpeg_with_gps(tmp_path / "original.jpg")
    before = src.read_bytes()
    out = tmp_path / "original.safe.jpg"
    result = run_cli(str(src), "-o", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    assert src.read_bytes() == before
    assert out.read_bytes() != before


def test_refuses_to_overwrite_input(tmp_path: Path) -> None:
    src = jpeg_with_gps(tmp_path / "photo.jpg")
    before = src.read_bytes()
    result = run_cli(str(src), "-o", str(src), "--force")
    assert result.returncode != 0
    assert src.read_bytes() == before


def test_force_only_overwrites_output(tmp_path: Path) -> None:
    src = jpeg_with_gps(tmp_path / "photo.jpg")
    original = src.read_bytes()
    out = tmp_path / "out.jpg"
    out.write_bytes(b"EXISTING-OUTPUT")
    blocked = run_cli(str(src), "-o", str(out))
    assert blocked.returncode != 0
    assert out.read_bytes() == b"EXISTING-OUTPUT"
    forced = run_cli(str(src), "-o", str(out), "--force")
    assert forced.returncode == 0, forced.stdout + forced.stderr
    assert src.read_bytes() == original
    assert out.read_bytes() != b"EXISTING-OUTPUT"
    assert not jpeg_has_gps_tags(out)
