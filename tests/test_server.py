"""Flask server tests using the in-process test client."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pagewright.server import create_app


@pytest.fixture
def client(tmp_book: Path):
    app = create_app(tmp_book, theme_name="default")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestEndpoints:
    def test_health(self, client) -> None:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json["ok"] is True
        assert r.json["tool"] == "pagewright"

    def test_index_returns_html(self, client) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert b"Pagewright" in r.data
        assert "no-store" in r.headers.get("Cache-Control", "")

    def test_tree_returns_book_metadata(self, client) -> None:
        r = client.get("/api/tree")
        assert r.status_code == 200
        books = r.json
        assert len(books) == 1
        assert books[0]["title"] == "Tmp Book"
        assert books[0]["total_chapters"] == 1

    def test_file_get_returns_content_and_etag(self, client) -> None:
        r = client.get("/api/file?path=01.md")
        assert r.status_code == 200
        assert "Chapter One" in r.data.decode()
        assert "ETag" in r.headers

    def test_file_get_missing_path_returns_400(self, client) -> None:
        r = client.get("/api/file")
        assert r.status_code == 400

    def test_file_get_nonexistent_returns_404(self, client) -> None:
        r = client.get("/api/file?path=does_not_exist.md")
        assert r.status_code == 404

    def test_file_get_path_traversal_returns_404(self, client) -> None:
        r = client.get("/api/file?path=../../../etc/passwd")
        assert r.status_code == 404

    def test_preview_continuous_mode(self, client) -> None:
        r = client.get("/api/preview?path=01.md&mode=continuous")
        assert r.status_code == 200
        assert b"<!DOCTYPE html>" in r.data
        assert b"continuous" in r.data
        assert b"paged.polyfill" not in r.data

    def test_preview_paged_mode(self, client) -> None:
        r = client.get("/api/preview?path=01.md&mode=paged")
        assert r.status_code == 200
        assert b"paged.polyfill" in r.data


class TestSaveAndConflict:
    def test_save_writes_file_and_returns_new_etag(self, client, tmp_book: Path) -> None:
        # First load — get the etag.
        r = client.get("/api/file?path=01.md")
        original_etag = r.headers["ETag"]

        # Save with the etag — should succeed.
        r = client.post(
            "/api/file",
            data=json.dumps({"path": "01.md", "content": "# Updated\n", "ifMatch": original_etag}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.json["saved"] == "01.md"
        new_etag = r.json["etag"]
        assert new_etag != original_etag

        # File on disk reflects the change.
        assert (tmp_book / "01.md").read_text() == "# Updated\n"

    def test_stale_etag_returns_409_conflict(self, client, tmp_book: Path) -> None:
        # Touch the file directly to advance its mtime — simulates an
        # external editor saving over us.
        (tmp_book / "01.md").write_text("# External edit\n")

        r = client.post(
            "/api/file",
            data=json.dumps({"path": "01.md", "content": "# My edit\n", "ifMatch": "stale-etag"}),
            content_type="application/json",
        )
        assert r.status_code == 409
        assert r.json["error"]["code"] == "conflict"
        assert "currentEtag" in r.json["error"]

    def test_save_without_ifmatch_succeeds(self, client, tmp_book: Path) -> None:
        # First-load saves omit ifMatch and should always be allowed.
        r = client.post(
            "/api/file",
            data=json.dumps({"path": "01.md", "content": "# new\n"}),
            content_type="application/json",
        )
        assert r.status_code == 200
