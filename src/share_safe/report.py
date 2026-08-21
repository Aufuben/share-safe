from __future__ import annotations

from pathlib import Path

from share_safe.models import FileResult


def format_result(result: FileResult, *, check: bool = False) -> str:
    src = str(result.source)
    if result.status == "skipped":
        return f"SKIP     {src}\n  {result.warning or 'skipped'}"
    if result.status == "error":
        return f"ERROR    {src}\n  {result.error or 'failed'}"

    if check:
        flag = "HAS GPS" if result.had_gps else "CLEAN"
        lines = [f"{flag:8} {src}"]
        if result.found:
            lines.append("  Found:")
            lines.extend(f"    - {item}" for item in result.found)
        if result.remaining and not result.had_gps:
            lines.append("  Remaining:")
            lines.extend(f"    - {item}" for item in result.remaining)
        return "\n".join(lines)

    dest = str(result.output) if result.output else "(not written)"
    header = f"{result.status.upper():8} {src} → {dest}"
    lines = [header]
    if result.removed:
        lines.append("  Removed:")
        lines.extend(f"    - {item}" for item in result.removed)
    else:
        lines.append("  Removed: (nothing identifying found)")
    if result.remaining:
        lines.append("  Remaining:")
        lines.extend(f"    - {item}" for item in result.remaining)
    if result.warning:
        lines.append(f"  Warning: {result.warning}")
    return "\n".join(lines)


def print_summary(results: list[FileResult], *, check: bool) -> str:
    blocks = [format_result(r, check=check) for r in results]
    n = len(results)
    gps = sum(1 for r in results if r.had_gps)
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")
    if check:
        footer = f"Checked {n} file(s): {gps} with GPS, {skipped} skipped, {errors} error(s)."
    else:
        cleaned = sum(1 for r in results if r.status in {"cleaned", "already_clean"})
        footer = f"Processed {n} file(s): {cleaned} written, {skipped} skipped, {errors} error(s)."
    return "\n\n".join(blocks) + "\n\n" + footer + "\n"
