from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from share_safe import __version__
from share_safe.core import run
from share_safe.models import UsageError
from share_safe.report import print_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="share-safe",
        description=(
            "Strip GPS and other identifying metadata from images (JPEG/PNG/WebP/HEIC) "
            "and PDFs before sharing. Runs entirely on your machine. Originals are never overwritten."
        ),
        epilog="Examples:\n"
        "  share-safe photo.jpg -o photo.safe.jpg\n"
        "  share-safe *.jpg -o ./safe/ --report\n"
        "  share-safe scan.pdf -o scan.safe.pdf\n"
        "  share-safe photo.jpg --check\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="image/PDF files or directories to process",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="output file (single input) or directory (batch / directory input)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether files still have GPS; do not write anything",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing OUTPUT files (never overwrites inputs)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print a human-readable report of what was removed and what remains (always on)",
    )
    parser.add_argument(
        "--keep-model",
        action="store_true",
        help="keep camera make/model tags (GPS is still always removed)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="recurse into directories",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"share-safe {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 0

    try:
        results = run(
            args.paths,
            output=args.output,
            check=args.check,
            force=args.force,
            keep_model=args.keep_model,
            recursive=args.recursive,
        )
    except UsageError as exc:
        print(f"share-safe: {exc}", file=sys.stderr)
        return 2

    report = print_summary(results, check=args.check)
    sys.stdout.write(report)

    if args.check:
        if any(r.status == "error" for r in results):
            return 1
        return 1 if any(r.had_gps for r in results) else 0
    if any(r.status == "error" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
