"""A local, token-guarded web viewer for the journal; lives while the terminal runs."""

from __future__ import annotations

import json
import secrets
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import TYPE_CHECKING, ClassVar, cast
from urllib.parse import parse_qs, urlsplit

from grillspec.config import load_config
from grillspec.state import compute_status, derive_phase, list_changes

from ._store import Entry, Journal, JournalError

if TYPE_CHECKING:
    from pathlib import Path

HOST = "127.0.0.1"
_LIMIT = 500
_MAX_BODY = 4096
_CSP_PARTS = (
    "default-src 'none'",
    "script-src 'nonce-{nonce}'",
    "style-src 'nonce-{nonce}'",
    "connect-src 'self'",
    "img-src data:",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
)
_CSP = "; ".join(_CSP_PARTS)


def _entry(entry: Entry) -> dict[str, object]:
    return {
        "id": entry.id,
        "ts": entry.ts,
        "kind": entry.kind,
        "change": entry.change,
        "text": entry.text,
        "pinned": entry.pinned,
    }


def _page(nonce: str) -> bytes:
    """Return the viewer page with its CSP nonce filled in.

    Args:
        nonce: str - The per-server nonce for the inline script and style.

    Returns:
        bytes - UTF-8 HTML.

    """
    html = (
        files("grillspec.journal").joinpath("viewer.html").read_text(encoding="utf-8")
    )
    return html.replace("{{NONCE}}", nonce).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    """Serves the page and the JSON API; every request carries the token."""

    root: ClassVar[Path]
    token: ClassVar[str]
    nonce: ClassVar[str]
    server_version: str = "grillspec"

    def log_message(self, format: str, *args: object) -> None:  # ruff: ignore[builtin-argument-shadowing]  # pyright: ignore[reportImplicitOverride]
        """Keep the terminal quiet."""

    def _allowed_host(self) -> bool:
        port = cast("tuple[str, int]", self.server.server_address)[1]
        host = self.headers.get("Host", "")
        return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", _CSP.format(nonce=self.nonce))
        self.end_headers()
        _ = self.wfile.write(body)

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _authorised(self, query: dict[str, list[str]]) -> bool:
        given = self.headers.get("X-Grillspec-Token") or (query.get("t") or [""])[0]
        return self._allowed_host() and secrets.compare_digest(given, self.token)

    def do_GET(self) -> None:
        """Serve the page or a read-only API call."""
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if not self._authorised(query):
            self._send(403, b"forbidden", "text/plain")
            return
        try:
            self._get(url.path, query)
        except JournalError as error:
            self._json(500, {"error": str(error)})

    def _get(self, path: str, query: dict[str, list[str]]) -> None:
        journal = Journal(self.root)
        if path == "/":
            self._send(200, _page(self.nonce), "text/html; charset=utf-8")
        elif path == "/api/entries":
            self._json(200, {"entries": [_entry(e) for e in journal.recent(_LIMIT)]})
        elif path == "/api/search":
            words = (query.get("q") or [""])[0]
            self._json(
                200, {"entries": [_entry(e) for e in journal.search(words, 100)]}
            )
        elif path == "/api/changes":
            self._json(200, self._changes())
        else:
            self._send(404, b"not found", "text/plain")

    def _changes(self) -> dict[str, object]:
        config = load_config(self.root).config
        status = compute_status(self.root, config)
        changes: list[dict[str, str]] = []
        if config.backend is not None:
            changes = [
                {"id": c.id, "phase": str(derive_phase(c))}
                for c in list_changes(self.root, config.backend)
            ]
        return {
            "project": self.root.name,
            "active": status.change_id,
            "phase": str(status.phase),
            "changes": changes,
        }

    def _apply(self, action: str, entry_id: int) -> int:
        """Pin, unpin or forget one entry.

        Returns:
            int - 200, or 404 when the entry does not exist.

        """
        journal = Journal(self.root)
        if journal.get(entry_id) is None:
            return HTTPStatus.NOT_FOUND
        if action == "forget":
            journal.forget(entry_id)
        else:
            journal.set_pinned(entry_id, flag=action == "pin")
        return HTTPStatus.OK

    def do_POST(self) -> None:
        """Pin, unpin or forget one entry."""
        url = urlsplit(self.path)
        if not self._authorised({}):
            self._send(403, b"forbidden", "text/plain")
            return
        action = {"/api/pin": "pin", "/api/unpin": "unpin", "/api/forget": "forget"}
        if url.path not in action:
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            data = cast("object", json.loads(self.rfile.read(min(length, _MAX_BODY))))
        except ValueError:
            data = None
        entry_id = (
            cast("dict[str, object]", data).get("id")
            if isinstance(data, dict)
            else None
        )
        if type(entry_id) is not int:
            self._json(400, {"error": 'expected {"id": <number>}'})
            return
        try:
            status = self._apply(action[url.path], entry_id)
        except JournalError as error:
            self._json(500, {"error": str(error)})
            return
        if status == HTTPStatus.NOT_FOUND:
            self._json(404, {"error": f"no entry {entry_id}"})
            return
        self._json(200, {"ok": True})


def make_server(root: Path, port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    """Build the viewer server bound to 127.0.0.1.

    Args:
        root: Path - Project root.
        port: int - Port; 0 picks a free one.

    Returns:
        tuple[ThreadingHTTPServer, str] - The server (not started) and its token.

    """
    token = secrets.token_urlsafe(24)
    handler = type(
        "Handler",
        (_Handler,),
        {"root": root, "token": token, "nonce": secrets.token_urlsafe(16)},
    )
    return ThreadingHTTPServer((HOST, port), handler), token


def serve(root: Path, *, port: int = 0, open_browser: bool = True) -> None:
    """Serve the viewer until Ctrl+C.

    Args:
        root: Path - Project root.
        port: int - Port; 0 picks a free one.
        open_browser: bool - Open the page in the default browser.

    """
    server, token = make_server(root, port)
    url = f"http://{HOST}:{server.server_address[1]}/?t={token}"
    _ = sys.stdout.write(f"grillspec memory viewer: {url}\n(Ctrl+C stops it)\n")
    _ = sys.stdout.flush()
    if open_browser:
        _ = webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
