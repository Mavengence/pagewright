"""Pagewright Flask server.

Serves the editor UI and a small JSON/HTML API:

- ``GET  /``                — editor shell (single-page app)
- ``GET  /api/health``      — liveness probe
- ``GET  /api/tree``        — book + chapters index
- ``GET  /api/file``        — load a chapter's markdown source (+ETag)
- ``POST /api/file``        — atomic save with ETag conflict detection
- ``GET  /api/preview``     — rendered chapter HTML for the iframe
- ``GET  /asset/<path>``    — sandboxed proxy for theme + book assets

The server is single-tenant: it serves exactly one book directory at a
time (the directory passed to ``serve()``).
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from .config import BookConfig, load_book_config
from .renderer import render_chapter_html
from .theme import Theme, load_theme

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"


def create_app(book_dir: Path, theme_name: str | None = None) -> Flask:
    """Build and return a Flask app serving the given book directory."""
    book_dir = Path(book_dir).resolve()
    if not book_dir.is_dir():
        raise NotADirectoryError(f"Book directory not found: {book_dir}")

    book = load_book_config(book_dir)
    theme = load_theme(theme_name or book.theme)

    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
    )
    app.config["BOOK"] = book
    app.config["THEME"] = theme
    app.config["BOOK_DIR"] = book_dir
    app.config["THEME_NAME"] = theme_name or book.theme

    _register_routes(app)
    return app


def _register_routes(app: Flask) -> None:
    @app.after_request
    def _no_cache(response):
        path = request.path
        if path.startswith("/static/") or path == "/" or path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    def _safe_book_path(rel: str) -> Path:
        """Resolve ``rel`` to an absolute path inside the book directory."""
        book_dir: Path = app.config["BOOK_DIR"]
        p = (book_dir / rel).resolve()
        try:
            p.relative_to(book_dir.resolve())
        except ValueError:
            abort(404)
        return p

    def _safe_theme_asset(rel: str) -> Path:
        """Resolve ``rel`` to an absolute path inside the theme directory."""
        theme: Theme = app.config["THEME"]
        p = (theme.directory / rel).resolve()
        try:
            p.relative_to(theme.directory.resolve())
        except ValueError:
            abort(404)
        return p

    def _file_etag(path: Path) -> str:
        return str(path.stat().st_mtime_ns)

    def _atomic_write(path: Path, content: str) -> None:
        tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
        try:
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def _json_error(status: int, code: str, message: str, **extra) -> object:
        return (
            jsonify({"error": {"code": code, "message": message, **extra}}),
            status,
            {"Content-Type": "application/json"},
        )

    @app.route("/")
    def index() -> object:
        return send_from_directory(str(STATIC_DIR), "index.html")

    @app.route("/api/health")
    def api_health() -> object:
        return jsonify({"ok": True, "version": 1, "tool": "pagewright"})

    @app.route("/api/tree")
    def api_tree() -> object:
        book: BookConfig = app.config["BOOK"]
        theme: Theme = app.config["THEME"]
        parts = []
        counter = 0
        for part in book.parts:
            chapters = []
            for ch in part.chapters:
                counter += 1
                chapters.append(
                    {
                        "path": ch.file,
                        "filename": ch.file,
                        "number": counter,
                        "title": ch.title,
                        "description": ch.description,
                    }
                )
            parts.append({"title": part.title, "chapters": chapters})
        return jsonify(
            [
                {
                    "slug": book.directory.name,
                    "title": book.title,
                    "subtitle": book.raw.get("subtitle", ""),
                    "author": book.author,
                    "theme": theme.name,
                    "total_chapters": book.total_chapters,
                    "parts": parts,
                }
            ]
        )

    @app.route("/api/file", methods=["GET", "POST"])
    def api_file() -> object:
        if request.method == "GET":
            rel = request.args.get("path", "")
            if not rel:
                return _json_error(400, "missing_path", "`path` query param required")
            path = _safe_book_path(rel)
            if not path.exists() or not path.is_file():
                return _json_error(404, "not_found", f"file not found: {rel}")
            return (
                path.read_text(encoding="utf-8"),
                200,
                {
                    "Content-Type": "text/plain; charset=utf-8",
                    "ETag": _file_etag(path),
                },
            )

        payload = request.get_json(silent=True) or {}
        rel = payload.get("path")
        content = payload.get("content")
        if_match = payload.get("ifMatch")
        if not rel or content is None:
            return _json_error(400, "bad_request", "`path` and `content` required")
        path = _safe_book_path(rel)
        if if_match is not None and path.exists():
            current = _file_etag(path)
            if current != str(if_match):
                return _json_error(
                    409,
                    "conflict",
                    "file changed externally since last load",
                    currentEtag=current,
                )
        _atomic_write(path, content)
        return jsonify(
            {
                "saved": rel,
                "bytes": len(content.encode("utf-8")),
                "etag": _file_etag(path),
            }
        )

    @app.route("/api/preview")
    def api_preview() -> object:
        rel = request.args.get("path", "")
        if not rel:
            abort(400)
        path = _safe_book_path(rel)
        if not path.exists():
            abort(404)
        # Param name `theme` is for *color scheme* (light/dark) — distinct
        # from the book theme. Kept compatible with the existing UI client.
        color_scheme = request.args.get("theme") or request.args.get("color", "light")
        if color_scheme not in {"light", "dark"}:
            color_scheme = "light"
        mode = request.args.get("mode", "continuous")
        if mode not in {"continuous", "paged"}:
            mode = "continuous"
        book: BookConfig = app.config["BOOK"]
        theme: Theme = app.config["THEME"]
        html = render_chapter_html(
            path,
            book,
            theme,
            mode=mode,
            color_scheme=color_scheme,
        )
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/theme-asset/<path:rel>")
    def serve_theme_asset(rel: str) -> object:
        """Serve fonts / images / etc. from the active theme directory."""
        abs_path = _safe_theme_asset(rel)
        if not abs_path.exists() or not abs_path.is_file():
            abort(404)
        return send_file(str(abs_path))

    @app.route("/book-asset/<path:rel>")
    def serve_book_asset(rel: str) -> object:
        """Serve any file from the book directory (images, data tables, etc.)."""
        abs_path = _safe_book_path(rel)
        if not abs_path.exists() or not abs_path.is_file():
            abort(404)
        return send_file(str(abs_path))


def serve(book_dir: Path, port: int = 5566, theme: str | None = None) -> int:
    """Start the editor server. Returns the process exit code."""
    app = create_app(book_dir, theme_name=theme)
    book: BookConfig = app.config["BOOK"]
    active_theme: Theme = app.config["THEME"]
    print(f"Pagewright → http://127.0.0.1:{port}")
    print(f"  book:   {book.title} ({book.total_chapters} chapters)")
    print(f"  source: {book.directory}")
    print(f"  theme:  {active_theme.name}")
    print("  Ctrl+C to stop")
    app.run(host="127.0.0.1", port=port, debug=False)
    return 0
