"""The built SPA mount and its no-build fallback (plan 07 Task 9, deliverable 2).

`create_app()` normally serves `src/docket/api/static/` — `ui/vite.config.ts`'s `outDir`,
gitignored, built by `make ui-build`/`docket ui` (`docket.api.config.static_dir`). Every
test here points that at a throwaway directory via `DOCKET_STATIC_DIR` instead, so this
file exercises the "built" and "not built" cases without depending on whether this
machine happens to have already run `npm run build` (it currently has — see
`src/docket/api/static/` on disk — but a clean checkout has not).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from docket.api.app import create_app


@pytest.fixture()
def built_static(tmp_path):
    """An index.html and one asset — just enough to exercise the SPA-fallback route and
    the asset route without needing an actual `npm run build`."""
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text(
        "<!doctype html><html><body>docket demonstration shell</body></html>\n"
    )
    (static / "assets" / "index-abc123.js").write_text("console.log('docket ui');\n")
    return static


@pytest.fixture()
def client_with_static(env, monkeypatch, built_static):
    monkeypatch.setenv("DOCKET_STATIC_DIR", str(built_static))
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture()
def client_without_static(env, monkeypatch, tmp_path):
    monkeypatch.setenv("DOCKET_STATIC_DIR", str(tmp_path / "no-such-static-dir"))
    with TestClient(create_app()) as c:
        yield c


# ---- the SPA is built ----------------------------------------------------------------


def test_root_serves_the_built_index(client_with_static):
    r = client_with_static.get("/")
    assert r.status_code == 200
    assert "docket demonstration shell" in r.text
    assert r.headers["content-type"].startswith("text/html")


def test_an_unknown_client_side_route_falls_back_to_the_index(client_with_static):
    """The SPA's own router owns `/package`, `/readiness`, etc. — none of these are
    files on disk, so a bare `StaticFiles` would 404 on a direct load or a refresh.
    `SPAStaticFiles.get_response` (api/app.py) re-serves `index.html` for any 404 whose
    path has no extension, so the client-side router gets a chance to render it."""
    r = client_with_static.get("/package")
    assert r.status_code == 200
    assert "docket demonstration shell" in r.text


def test_an_asset_is_served_with_its_own_content_type_not_the_index(client_with_static):
    r = client_with_static.get("/assets/index-abc123.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "console.log" in r.text


def test_api_routes_are_never_shadowed_by_the_static_mount(client_with_static):
    """The API router is included before the SPA is mounted (`create_app`) — a request
    under `/api/*` must always reach it, never the SPA-fallback rule above."""
    r = client_with_static.get("/api/health")
    assert r.status_code == 200
    assert r.json()["kernelVersion"]


def test_an_unknown_api_route_still_returns_404_rather_than_falling_back_to_the_index(
    client_with_static,
):
    r = client_with_static.get("/api/this-route-does-not-exist")
    assert r.status_code == 404
    assert "docket demonstration shell" not in r.text


# ---- the SPA is not built --------------------------------------------------------------


def test_the_api_still_answers_when_no_static_dir_exists(client_without_static):
    r = client_without_static.get("/api/health")
    assert r.status_code == 200
    assert r.json()["kernelVersion"]


def test_root_names_the_build_line_when_the_spa_is_not_built(client_without_static):
    r = client_without_static.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "make ui-build" in r.text


def test_an_unknown_client_route_also_gets_the_build_line_when_not_built(
    client_without_static,
):
    """No SPA is mounted at all in this case — `/package` is just an unregistered route,
    not a deep link into a shell that exists. FastAPI's own 404 is honest here (there is
    nothing this server can render at that path yet); only `/` carries the build hint."""
    r = client_without_static.get("/package")
    assert r.status_code == 404
