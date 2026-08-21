from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from helpers import jpeg_has_gps_tags, jpeg_with_gps
from share_safe.gui import execute, resolve_display_path, suggest_output_path


def test_empty_path_stays_empty() -> None:
    assert resolve_display_path("") == ""
    assert resolve_display_path("   ") == ""


def test_relative_path_becomes_absolute(tmp_path: Path) -> None:
    got = resolve_display_path("photo.jpg", base=tmp_path)
    assert Path(got).is_absolute()
    assert Path(got) == (tmp_path / "photo.jpg").resolve()


def test_absolute_path_stays_absolute(tmp_path: Path) -> None:
    src = tmp_path / "inbox" / "a.jpg"
    got = resolve_display_path(str(src))
    assert Path(got).is_absolute()
    assert Path(got) == src.resolve()


def test_home_is_expanded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    got = resolve_display_path("~/Pictures/in.jpg")
    assert Path(got).is_absolute()
    assert Path(got) == (tmp_path / "Pictures" / "in.jpg").resolve()


def test_dotdot_is_normalized(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    got = resolve_display_path(str(nested / ".." / "out.jpg"))
    assert Path(got) == (tmp_path / "a" / "out.jpg").resolve()


def test_nonexistent_path_is_still_absolute(tmp_path: Path) -> None:
    got = resolve_display_path("missing.jpg", base=tmp_path)
    assert Path(got).is_absolute()
    assert got.endswith("missing.jpg")


def test_suggest_output_for_file(tmp_path: Path) -> None:
    src = tmp_path / "photo.jpg"
    suggested = suggest_output_path(str(src))
    assert Path(suggested).is_absolute()
    assert Path(suggested) == (tmp_path / "photo.safe.jpg").resolve()


def test_suggest_output_for_directory(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    suggested = suggest_output_path(str(inbox))
    assert Path(suggested).is_absolute()
    assert Path(suggested) == (tmp_path / "inbox.safe").resolve()


def test_execute_requires_input() -> None:
    code, text = execute(input_path="", output_path="")
    assert code == 2
    assert "输入路径" in text


def test_execute_same_path_as_cli(tmp_path: Path) -> None:
    src = jpeg_with_gps(tmp_path / "photo.jpg")
    original = src.read_bytes()
    out = tmp_path / "photo.safe.jpg"
    code, text = execute(input_path=str(src), output_path=str(out), check=False)
    assert code == 0, text
    assert out.is_file()
    assert not jpeg_has_gps_tags(out)
    assert src.read_bytes() == original
    assert "gps" in text.lower()
    assert "removed" in text.lower()


def test_execute_report_false_still_writes(tmp_path: Path) -> None:
    src = jpeg_with_gps(tmp_path / "photo.jpg")
    original = src.read_bytes()
    out = tmp_path / "photo.safe.jpg"
    code, text = execute(
        input_path=str(src),
        output_path=str(out),
        check=False,
        report=False,
    )
    assert code == 0, text
    assert out.is_file()
    assert not jpeg_has_gps_tags(out)
    assert src.read_bytes() == original
    assert "removed" not in text.lower()


def test_execute_check_does_not_write(tmp_path: Path) -> None:
    src = jpeg_with_gps(tmp_path / "photo.jpg")
    original = src.read_bytes()
    out = tmp_path / "should-not-exist.jpg"
    code, text = execute(input_path=str(src), output_path=str(out), check=True)
    assert code != 0
    assert "gps" in text.lower()
    assert src.read_bytes() == original
    assert not out.exists()
    assert list(tmp_path.glob("*.safe.*")) == []


def test_main_gui_dispatches_without_treating_gui_as_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import share_safe.gui as gui_mod
    from share_safe.cli import main

    called: list[int] = []
    monkeypatch.setattr(gui_mod, "launch", lambda: called.append(1) or 0)
    assert main(["gui"]) == 0
    assert called == [1]


def _skip_gui_window() -> bool:
    if os.environ.get("CI", "").lower() in {"1", "true", "yes"}:
        return True
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return True
    try:
        import tkinter  # noqa: F401
        import _tkinter  # noqa: F401
    except ImportError:
        return True
    return False


@pytest.mark.skipif(_skip_gui_window(), reason="skip GUI window in headless CI")
def test_gui_window_shows_absolute_path_fields() -> None:
    import tkinter as tk

    from share_safe.gui import build_window

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"tkinter cannot open a window: {exc}")
    try:
        root.withdraw()
        app = build_window(root)
        assert app.input_label.cget("text") == "输入路径"
        assert app.output_label.cget("text") == "输出路径"
        app.input_var.set("photo.jpg")
        app.resolve_fields()
        assert Path(app.input_var.get()).is_absolute()
        assert Path(app.output_var.get()).is_absolute()
    finally:
        root.destroy()
