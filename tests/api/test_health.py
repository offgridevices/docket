import json

FAKE_KEY = "fake key for tests only (spaces keep it out of secret scanners)"


def test_health_reports_kernel_version_and_no_key(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    b = r.json()
    assert b["kernelVersion"] and b["keyPresent"] is False
    assert b["denylistActive"] is True
    assert set(b["demoStores"]) == {"demo-a", "demo-b"}
    assert b["mode"] in ("live", "recorded")
    assert "apiKey" not in r.text and "Bearer" not in r.text


def test_health_never_leaks_a_key(client, monkeypatch):
    monkeypatch.setenv("DOCKET_LLM_API_KEY", FAKE_KEY)
    b = client.get("/api/health").json()
    assert b["keyPresent"] is True
    assert FAKE_KEY not in client.get("/api/health").text


def test_health_does_not_fail_when_the_backend_is_unreachable(client):
    """`_probe` degrades to `reachable: false` instead of raising past the route — a
    health check that can itself fail is worse than none."""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["backend"]["reachable"] is False


def test_health_demo_a_store_is_reported_present(client, demo_a_present):
    b = client.get("/api/health").json()
    assert b["demoStores"]["demo-a"] is True


def test_health_does_not_409_on_a_refused_config_file(client, env):
    """[ruling I4, plan 07 T2 fix round] `GET /api/health` is the one endpoint the UI
    polls to decide whether anything is working at all — a hand-edited or otherwise
    malformed config file (here, one that inlines a credential) must not take it down.
    The refusal is reported in a field instead of hidden (honesty rule 8), and the
    status stays 200."""
    (env / "llm.json").write_text(json.dumps({
        "provider": "openai-compatible", "model": {"apiKey": "sk-secret"}}))
    r = client.get("/api/health")
    assert r.status_code == 200
    b = r.json()
    assert b["configRefused"] is True
    assert "sk-secret" not in r.text
    assert b["configRefusedMessage"] and "sk-secret" not in b["configRefusedMessage"]
