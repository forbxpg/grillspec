"""Tests for the local session-memory viewer (spec JR-R5)."""

from __future__ import annotations

import http.client
import json
import re
import threading
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.config import load_config
from grillspec.journal import Journal, brief
from grillspec.journal._server import make_server
from grillspec.state import compute_status
from support import GATED_ID, phase_project

if TYPE_CHECKING:
    from collections.abc import Iterator
    from http.server import ThreadingHTTPServer
    from pathlib import Path


@pytest.fixture
def served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Path, ThreadingHTTPServer, str]]:
    monkeypatch.chdir(tmp_path)
    root = phase_project(tmp_path, "spec")
    server, token = make_server(root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield root, server, token
    finally:
        server.shutdown()
        server.server_close()


def _request(  # ruff: ignore[too-many-arguments] - keyword-only knobs
    server: ThreadingHTTPServer,
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, object] | None = None,
    host: str | None = None,
) -> tuple[int, bytes]:
    port = server.server_address[1]
    con = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if token is not None:
        headers["X-Grillspec-Token"] = token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    try:
        con.request(method, path, body=data, headers=headers)
        response = con.getresponse()
        return response.status, response.read()
    finally:
        con.close()


def test_server_binds_loopback(served: tuple[Path, ThreadingHTTPServer, str]):
    _, server, _ = served
    assert server.server_address[0] == "127.0.0.1"


@pytest.mark.parametrize("token", [None, "wrong"])
def test_token_required(
    served: tuple[Path, ThreadingHTTPServer, str], token: str | None
):  # JR-10
    root, server, _ = served
    entry = Journal(root).add("todo", "keep me", change=None)
    assert _request(server, "GET", "/api/entries", token=token)[0] == 403
    assert _request(server, "GET", "/")[0] == 403
    assert _request(server, "GET", "/?t=wrong")[0] == 403
    status, _ = _request(
        server, "POST", "/api/forget", token=token, body={"id": entry.id}
    )
    assert status == 403
    assert Journal(root).get(entry.id) is not None


def test_foreign_host_refused(served: tuple[Path, ThreadingHTTPServer, str]):
    _, server, token = served
    status, _ = _request(
        server, "GET", "/api/entries", token=token, host="evil.example"
    )
    assert status == 403


def test_page_is_self_contained(served: tuple[Path, ThreadingHTTPServer, str]):
    _, server, token = served
    status, page = _request(server, "GET", f"/?t={token}")
    assert status == 200
    html = page.decode()
    assert "<title>grillspec memory</title>" in html
    assert not re.search(r"(src|href)=[\"']https?://", html)  # nothing from the network


def test_entries_and_search(served: tuple[Path, ThreadingHTTPServer, str]):
    root, server, token = served
    journal = Journal(root)
    _ = journal.add("discovery", "the CI runner caches uv", change=GATED_ID)
    _ = journal.add("todo", "document the cache expiry", change=GATED_ID)
    status, body = _request(server, "GET", "/api/entries", token=token)
    assert status == 200
    data = cast("dict[str, object]", json.loads(body))
    texts = [
        cast("dict[str, str]", e)["text"] for e in cast("list[object]", data["entries"])
    ]
    assert texts == ["document the cache expiry", "the CI runner caches uv"]
    status, body = _request(server, "GET", "/api/search?q=runner", token=token)
    found = cast("list[dict[str, str]]", json.loads(body)["entries"])
    assert [e["text"] for e in found] == ["the CI runner caches uv"]


def test_changes_and_phase(served: tuple[Path, ThreadingHTTPServer, str]):
    _, server, token = served
    status, body = _request(server, "GET", "/api/changes", token=token)
    assert status == 200
    data = cast("dict[str, object]", json.loads(body))
    assert data["active"] == GATED_ID
    changes = cast("list[dict[str, str]]", data["changes"])
    assert {"id": GATED_ID, "phase": "spec"} in changes


def test_pin_from_the_page(served: tuple[Path, ThreadingHTTPServer, str]):  # JR-11
    root, server, token = served
    journal = Journal(root)
    old = journal.add(
        "discovery", "the pinned fact", change=None, ts="2026-01-01T00:00:00Z"
    )
    for n in range(10):
        _ = journal.add("event", f"newer {n}", change=GATED_ID)
    status, _ = _request(server, "POST", "/api/pin", token=token, body={"id": old.id})
    assert status == 200
    text = brief(root, compute_status(root, load_config(root).config))
    assert text.index("the pinned fact") < text.index("newer 9")


def test_get_never_writes(served: tuple[Path, ThreadingHTTPServer, str]):
    root, server, token = served
    entry = Journal(root).add("todo", "stay", change=None)
    assert _request(server, "GET", f"/api/forget?id={entry.id}", token=token)[0] == 404
    assert Journal(root).get(entry.id) is not None


def test_forget_and_bad_requests(served: tuple[Path, ThreadingHTTPServer, str]):
    root, server, token = served
    entry = Journal(root).add("todo", "drop me", change=None)
    assert (
        _request(server, "POST", "/api/forget", token=token, body={"id": entry.id})[0]
        == 200
    )
    assert Journal(root).get(entry.id) is None
    assert _request(server, "POST", "/api/pin", token=token, body={"id": "x"})[0] == 400
    assert (
        _request(server, "POST", "/api/pin", token=token, body={"id": 99999})[0] == 404
    )
    assert _request(server, "GET", "/../../etc/passwd", token=token)[0] == 404
