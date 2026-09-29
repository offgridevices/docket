"""`docket.api.app._load_route_module`: tolerate only a route module's own absence.

Written against a monkeypatched `importlib.import_module` rather than a real broken file
under `src/docket/api/routes/` — other agents are concurrently writing real modules into
that exact directory (`routes/settings.py`, `routes/kernel.py`), so a scratch/broken file
there risks colliding with their work; a monkeypatch is deterministic, isolated, and
pytest reverts it automatically at teardown.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import docket.api.app as app_module


def test_a_genuinely_absent_module_is_skipped():
    # No file named this exists under src/docket/api/routes/ — a real ModuleNotFoundError
    # whose .name is exactly "docket.api.routes.does_not_exist_xyz".
    assert app_module._load_route_module("does_not_exist_xyz") is None


def test_an_existing_module_imports_normally():
    module = app_module._load_route_module("health")
    assert hasattr(module, "router")


def test_an_import_time_bug_in_an_existing_module_fails_fast(monkeypatch):
    """Simulates the review's live finding: a route module that exists but raises a
    plain (non-`ModuleNotFoundError`) exception at import time — e.g. an invalid
    FastAPI response-model annotation — must crash loudly and name the module, not be
    swallowed as if the module were simply absent."""

    def fake_import(name: str):
        if name == "docket.api.routes.broken":
            raise ImportError("invalid response-model annotation")
        return real_import(name)

    real_import = app_module.importlib.import_module
    monkeypatch.setattr(app_module.importlib, "import_module", fake_import)

    with pytest.raises(RuntimeError, match="docket.api.routes.broken"):
        app_module._load_route_module("broken")


def test_a_module_not_found_error_for_a_different_name_also_fails_fast(monkeypatch):
    """A route module that exists but itself imports something ELSE that is missing (a
    typo'd import, an absent third-party dependency) must not be mistaken for "this
    route is simply not built yet" — the distinction has to be made on the missing
    name, not just the exception type."""
    real_import = app_module.importlib.import_module

    def fake_import(name: str):
        if name == "docket.api.routes.broken":
            raise ModuleNotFoundError(
                "No module named 'some_other_dependency'", name="some_other_dependency",
            )
        return real_import(name)

    monkeypatch.setattr(app_module.importlib, "import_module", fake_import)

    with pytest.raises(RuntimeError, match="docket.api.routes.broken"):
        app_module._load_route_module("broken")


def test_create_app_boots_with_at_least_health_and_session_present(env):
    """The end-to-end check: `create_app()` must boot and carry Task 1's own routes
    whether or not the other plan-07 tasks' route modules (`settings`, `agent`,
    `kernel`, `program`) have landed yet in this working tree — that's the whole point
    of tolerating a module's absence. Hits the routes over HTTP rather than
    introspecting `app.routes` directly, since an included router's internal shape is
    an implementation detail of the FastAPI/Starlette version in use.
    """
    with TestClient(app_module.create_app()) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/sessions").status_code == 200
