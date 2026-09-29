from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docket.api.app import create_app

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Every API test runs against a temp state dir, a temp config, the RecordedBackend
    and no network. Nothing here may touch demos/*/out."""
    monkeypatch.setenv("DOCKET_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("DOCKET_LLM_CONFIG", str(tmp_path / "llm.json"))
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    monkeypatch.setenv("DOCKET_UI_ACTOR", "tester")
    # A seam of last resort so nothing under `docket.api.config` can reach the real
    # developer machine's `~/.config/docket` — see `config._config_path`'s docstring.
    # `DOCKET_UI_ACTOR` above already makes `actor_id()` never read the file in most
    # tests; this covers the ones that write it (`write_actor_id`) or delete the actor
    # env on purpose to exercise the file-reading path.
    monkeypatch.setenv("DOCKET_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("DOCKET_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DOCKET_LLM_ALLOW_DENYLISTED", raising=False)
    # [ruling I6, plan 07 T2 fix round] Without these, a developer's shell environment
    # (a live Ollama base URL, a locally cached model that happens to be denylisted, a
    # custom timeout or recording path) leaks into every API test — R9 says no test may
    # reach the network, ever, and a stray `DOCKET_LLM_BASE_URL` is enough to break that.
    monkeypatch.delenv("DOCKET_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("DOCKET_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOCKET_LLM_TIMEOUT", raising=False)
    monkeypatch.delenv("DOCKET_LLM_RECORDING", raising=False)
    return tmp_path


@pytest.fixture()
def client(env):
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture()
def demo_a_present():
    p = REPO / "demos" / "a_cbo_gcv_2013" / "out" / "graph"
    if not (p / "log.jsonl").is_file():
        pytest.skip("Demo A store not built yet (plan 03b Task 7)")
    return p


@pytest.fixture()
def demo_b_present():
    """Plan 07 Task 7 fix round (C1): Demo B is every episode's `gao-23-106549`
    tailoring, the one fixture that exercises `standardsCaptions.tailoringNote`."""
    p = REPO / "demos" / "b_omfv_2019_2023" / "out" / "graph"
    if not (p / "log.jsonl").is_file():
        pytest.skip("Demo B store not built yet")
    return p
