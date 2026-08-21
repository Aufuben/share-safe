from __future__ import annotations

from pathlib import Path

from share_safe.detect import inspect_file
from share_safe.images import sanitize_heic, sanitize_image
from share_safe.models import (
    HEIC_EXT,
    IMAGE_EXT,
    PDF_EXT,
    SUPPORTED_EXT,
    FileResult,
    UsageError,
)
from share_safe.pdfs import sanitize_pdf


def collect_inputs(paths: list[Path], *, recursive: bool) -> list[Path]:
    files: list[Path] = []
    missing: list[Path] = []
    for raw in paths:
        path = raw.expanduser()
        if not path.exists():
            missing.append(path)
            continue
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            children = sorted(p for p in iterator if p.is_file() and p.suffix.lower() in SUPPORTED_EXT)
            files.extend(children)
        elif path.is_file():
            files.append(path)
        else:
            missing.append(path)
    if missing:
        names = ", ".join(str(p) for p in missing)
        raise UsageError(f"path not found: {names}")
    unique: list[Path] = []
    seen: set[Path] = set()
    for f in files:
        key = f.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    if not unique:
        raise UsageError("no files to process (directories need JPEG/PNG/WebP/HEIC/PDF files)")
    return unique


def resolve_destination(
    src: Path,
    *,
    output: Path | None,
    file_count: int,
    inputs_include_dir: bool,
) -> Path:
    if output is None:
        return src.with_name(f"{src.stem}.safe{src.suffix}")

    output_is_dir = _is_dir_output(output, file_count=file_count, inputs_include_dir=inputs_include_dir)
    if output_is_dir:
        return output / src.name
    return output


def _is_dir_output(output: Path, *, file_count: int, inputs_include_dir: bool) -> bool:
    text = str(output)
    if text.endswith(("/", "\\")):
        return True
    if output.exists() and output.is_dir():
        return True
    if file_count > 1 or inputs_include_dir:
        return True
    if output.suffix.lower() in SUPPORTED_EXT:
        return False
    if output.suffix == "":
        return True
    return False


def ensure_writable(src: Path, dest: Path, *, force: bool) -> str | None:
    src_res = src.resolve()
    dest_res = dest.resolve()
    if dest_res == src_res:
        return "refusing to overwrite input (share-safe never overwrites originals, even with --force)"
    if dest.exists():
        try:
            if dest.samefile(src):
                return "refusing to overwrite input (share-safe never overwrites originals, even with --force)"
        except OSError:
            pass
        if dest.is_file() and not force:
            return f"output exists: {dest} (pass --force to overwrite the output file only)"
        if dest.is_dir():
            return f"output path is a directory: {dest}"
    return None


def process_file(
    src: Path,
    dest: Path | None,
    *,
    check: bool,
    force: bool,
    keep_model: bool,
) -> FileResult:
    suffix = src.suffix.lower()
    if check:
        if suffix in HEIC_EXT:
            try:
                import pillow_heif  # noqa: F401
            except ImportError:
                return FileResult.skipped(
                    src,
                    'HEIC/HEIF is not supported in this install (pip install "share-safe[heic]"). Skipping.',
                )
        if suffix not in SUPPORTED_EXT:
            return FileResult.skipped(src, f"unsupported file type ({suffix or 'unknown'}); skipped")
        had_gps, found, remaining = inspect_file(src)
        status = "has_gps" if had_gps else "clean"
        return FileResult(
            source=src,
            output=None,
            status=status,
            found=found,
            remaining=remaining,
            had_gps=had_gps,
        )

    if dest is None:
        return FileResult.failed(src, "internal error: missing output path")

    err = ensure_writable(src, dest, force=force)
    if err:
        return FileResult.failed(src, err)

    if suffix not in SUPPORTED_EXT:
        return FileResult.skipped(src, f"unsupported file type ({suffix or 'unknown'}); skipped")

    try:
        if suffix in PDF_EXT:
            return sanitize_pdf(src, dest, keep_model=keep_model)
        if suffix in IMAGE_EXT:
            return sanitize_image(src, dest, keep_model=keep_model)
        return FileResult.skipped(src, f"unsupported file type ({suffix}); skipped")
    except Exception as exc:
        if suffix in HEIC_EXT:
            return sanitize_heic(src, dest, keep_model=keep_model)
        return FileResult.failed(src, str(exc))


def run(
    paths: list[str],
    *,
    output: str | None,
    check: bool,
    force: bool,
    keep_model: bool,
    recursive: bool,
) -> list[FileResult]:
    in_paths = [Path(p) for p in paths]
    inputs_include_dir = any(p.exists() and p.is_dir() for p in in_paths)
    files = collect_inputs(in_paths, recursive=recursive)
    out_arg = Path(output) if output else None

    if not check and out_arg is not None:
        dir_mode = _is_dir_output(out_arg, file_count=len(files), inputs_include_dir=inputs_include_dir)
        if dir_mode:
            out_arg.mkdir(parents=True, exist_ok=True)
        elif len(files) > 1:
            raise UsageError("-o must be a directory when processing multiple files")

    results: list[FileResult] = []
    for src in files:
        dest = None
        if not check:
            dest = resolve_destination(
                src,
                output=out_arg,
                file_count=len(files),
                inputs_include_dir=inputs_include_dir,
            )
        results.append(
            process_file(src, dest, check=check, force=force, keep_model=keep_model)
        )
    return results
