"""``pagewright`` command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pagewright",
        description=(
            "Local-first book editor for Markdown: CodeMirror on the left, "
            "true paged A4 preview on the right (paged.js)."
        ),
    )
    parser.add_argument(
        "book_dir",
        nargs="?",
        default=".",
        help="Path to the book directory (containing pagewright.yaml).",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=5566,
        help="Port to bind on 127.0.0.1 (default: 5566).",
    )
    parser.add_argument(
        "--theme",
        "-t",
        default=None,
        help=(
            "Override the theme set in pagewright.yaml. Either a built-in "
            "theme name (currently: default) or an absolute path to a "
            "directory containing theme.css."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)

    book_dir = Path(args.book_dir).expanduser().resolve()
    try:
        return serve(book_dir, port=args.port, theme=args.theme)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
