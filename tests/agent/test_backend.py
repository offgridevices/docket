import json
from pathlib import Path

import httpx
import pytest

from docket.agent.backend import (
    DENYLIST,
    DOC_SCAN_DENYLIST,
    KNOWN_UNCAUGHT,
    JsonBackendBase,
    RecordedBackend,
    backend_from_env,
    check_model_policy,
    is_denylisted,
    load_config,
    record,
    recording_key,
    resolve_settings,
    write_config,
)
from docket.errors import BackendError, PolicyRefusal, RecordingMissing

SCHEMA = {"type": "object", "properties": {"n": {"type": "integer"}},
          "required": ["n"], "additionalProperties": False}

# Repo root, anchored to this file's location rather than the process CWD [ruling I3].
ROOT = Path(__file__).resolve().parents[2]

# [ruling M1] No test may read the developer's real ~/.config/docket/llm.json or inherit
# a real DOCKET_LLM_* value left over in the shell. Every test starts from a clean slate
# with DOCKET_LLM_CONFIG pointed at a file that does not exist yet, in this test's own
# tmp_path; individual tests override whichever variables they're exercising.
_DOCKET_ENV_VARS = (
    "DOCKET_LLM_PROVIDER", "DOCKET_LLM_MODEL", "DOCKET_LLM_BASE_URL", "DOCKET_LLM_API_KEY",
    "DOCKET_LLM_RECORDING", "DOCKET_LLM_TIMEOUT", "DOCKET_LLM_CONFIG",
    "DOCKET_LLM_ALLOW_DENYLISTED",
)


@pytest.fixture(autouse=True)
def _isolated_docket_env(monkeypatch, tmp_path):
    for var in _DOCKET_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DOCKET_LLM_CONFIG", str(tmp_path / "unused-default-config.json"))


class Flaky(JsonBackendBase):
    name = "flaky"
    model_id = "flaky"

    def __init__(self):
        self.calls = []

    def _raw(self, system, user, schema, budget=None):
        self.calls.append(user)
        return '{"n": "one"}' if len(self.calls) == 1 else '{"n": 1}'


def test_retry_feeds_back_validation_errors():
    b = Flaky()
    assert b.complete_json(system="s", user="u", schema=SCHEMA) == {"n": 1}
    assert len(b.calls) == 2 and "is not of type 'integer'" in b.calls[1]


def test_gives_up_after_retries():
    class Bad(JsonBackendBase):
        name = "bad"
        model_id = "bad"

        def _raw(self, system, user, schema, budget=None):
            return "not json"

    with pytest.raises(BackendError):
        Bad().complete_json(system="s", user="u", schema=SCHEMA, max_retries=1)


def test_recorded_backend_roundtrip(tmp_path):
    p = tmp_path / "rec.json"
    key = recording_key("s", "u", SCHEMA)
    record(p, key, '{"n": 3}', note="test")
    b = RecordedBackend(p)
    assert b.complete_json(system="s", user="u", schema=SCHEMA) == {"n": 3}
    assert b.extractor == "recorded:recorded" and b.calls == [key]
    with pytest.raises(RecordingMissing) as exc:
        b.complete_json(system="s", user="other", schema=SCHEMA)
    assert "no recording" in str(exc.value) and str(p) in str(exc.value)


def test_recorded_backend_raises_at_construction_when_file_absent(tmp_path):
    # [ruling M7] fail fast at construction, not on the first missed lookup.
    with pytest.raises(RecordingMissing):
        RecordedBackend(tmp_path / "does-not-exist.json")


def test_default_recording_path_is_resolved_against_repo_root():
    # [ruling M7] a relative default meant "no recording, ever" once CWD != repo root.
    from docket.agent.backend import DEFAULT_RECORDING

    p = Path(DEFAULT_RECORDING)
    assert p.is_absolute()
    assert p.as_posix().endswith("tests/fixtures/recorded/default.json")


def test_backend_from_env_recorded_and_denylist(monkeypatch, tmp_path):
    p = tmp_path / "rec.json"
    p.write_text("{}")
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "recorded")
    monkeypatch.setenv("DOCKET_LLM_RECORDING", str(p))
    assert backend_from_env().name == "recorded"
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_MODEL", "deepseek-v3")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", "http://localhost:1/v1")
    monkeypatch.setenv("DOCKET_LLM_API_KEY", "x")
    with pytest.raises(PolicyRefusal):
        backend_from_env()


# [pre-flight defect 2] the old one-line regex let every id below through. Table-driven
# over ids that really exist on Ollama and OpenRouter today.
DENIED = ["deepseek-v3", "deepseek-r1:70b", "qwen3.8:27b-mlx", "Qwen2.5-72B",
          "qwen3.6:35b-mlx", "qwq:32b", "qvq-72b", "glm4:9b", "glm-4.5", "chatglm3",
          "THUDM/chatglm3-6b", "zhipu/glm-4", "yi:34b", "yi-34b", "internvl3",
          "internlm2.5", "minicpm-v", "seed-oss:36b", "skywork-r1", "longcat-flash",
          "dots.llm1", "kimi-k2", "moonshotai/kimi-k2", "hunyuan-a13b", "ernie-4.5",
          "doubao-pro", "baichuan2", "minimax-m1", "cogvlm2", "telechat2",
          "stepfun-ai/step3", "sparkdesk-v3", "pangu-alpha", "sensechat-5", "moss-moon",
          "xverse-13b", "Step3", "step-1v", "LING-1T"]
ALLOWED = ["llama-3.3-70b", "muse-glimmer:30b-mlx", "gemma4:e4b", "gpt-4o-mini",
           "mistral-large", "phi-4", "nemotron-70b", "command-r-plus", "olmo-2",
           "granite-3.1", "sparkle-7b", "openai/gpt-oss-120b", "o3-mini",
           "gemini-2.5-pro", "x-ai/grok-4", "sterling-x", "stepwise-1", "darling-13b",
           "stepping-stone", "glimmer"]


@pytest.mark.parametrize("model", DENIED)
def test_denylist_catches_real_prc_ids(model):
    assert is_denylisted(model), model


@pytest.mark.parametrize("model", ALLOWED)
def test_denylist_does_not_catch_innocent_ids(model):
    assert not is_denylisted(model), model


# [ruling I5] `step` and `moss` are ordinary English words; the model-id check must not
# fire on prose shaped like a sentence rather than a model id.
INNOCENT_PROSE = [
    "Step 1: read the charter",
    "a step-by-step walkthrough",
    "the next step.",
    "moss grows",
]


@pytest.mark.parametrize("text", INNOCENT_PROSE)
def test_model_id_check_ignores_innocent_prose(text):
    assert not is_denylisted(text), text


@pytest.mark.parametrize("text", INNOCENT_PROSE)
def test_doc_scan_denylist_ignores_innocent_prose(text):
    assert DOC_SCAN_DENYLIST.search(text) is None, text


@pytest.mark.parametrize("text", [
    "the model qwen3.8:27b-mlx is denylisted",
    "we saw deepseek-v3 mentioned in the log",
    "glm4:9b appeared in the model picker",
    "Step3 and step-1v are both StepFun ids",
])
def test_doc_scan_denylist_still_catches_real_model_tags(text):
    assert DOC_SCAN_DENYLIST.search(text) is not None, text


# [ruling N1] `step-N` with nothing after the digit run is this codebase's own
# Plan.steps / Result-id convention (see tests/test_store.py, tests/kernel/
# test_evaluate.py) — lexically identical to `step(?=[-_.:]?\d)` and so, before this
# fix, indistinguishable from a real StepFun tag by the document scan. Requiring a
# letter or another separator immediately after the digit run is what a real tag has.
STEP_ID_NOT_DOC_MATCHED = ["step-1", "step-2", "step-10", "step_3", "step.4", "Step-1"]
STEP_TAG_DOC_MATCHED = ["step-1v", "step-1-8k", "step-2-16k", "stepfun-ai/step3"]


@pytest.mark.parametrize("text", STEP_ID_NOT_DOC_MATCHED)
def test_doc_scan_denylist_does_not_flag_bare_step_ids(text):
    assert DOC_SCAN_DENYLIST.search(text) is None, text


@pytest.mark.parametrize("text", STEP_TAG_DOC_MATCHED)
def test_doc_scan_denylist_still_flags_real_step_tags(text):
    assert DOC_SCAN_DENYLIST.search(text) is not None, text


@pytest.mark.parametrize(
    "model", STEP_ID_NOT_DOC_MATCHED + STEP_TAG_DOC_MATCHED + ["Step3"]
)
def test_strict_denylist_still_refuses_every_step_id_at_resolution_points(model):
    # [ruling N1] the document scan is deliberately looser than the model-id check: a
    # bare `step-3` is not flagged in a document, but it is still refused as a model id
    # wherever one is actually resolved — that's where a refusal matters.
    assert is_denylisted(model), model
    with pytest.raises(PolicyRefusal):
        check_model_policy(model)


def test_doc_scan_denylist_matches_multi_token_family_names_standing_alone():
    # [ruling N2] a family that already contains a separator (`moss-moon`) is tag-shaped
    # by construction and must not additionally require an external tag-context
    # character, or it becomes unmatchable standing alone.
    assert DOC_SCAN_DENYLIST.search("moss-moon") is not None


def test_known_uncaught_is_honest():
    """The accepted family set is a tripwire, not a guarantee — say so in code."""
    assert all(not DENYLIST.search(m) for m in KNOWN_UNCAUGHT)


def test_allow_denylisted_override_warns_and_proceeds(monkeypatch, caplog):
    # [pre-flight defect 3] / [ruling R2]: the documented, warning-logged escape.
    monkeypatch.setenv("DOCKET_LLM_ALLOW_DENYLISTED", "1")
    monkeypatch.setenv("DOCKET_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("DOCKET_LLM_MODEL", "qwen3.8:27b-mlx")
    monkeypatch.setenv("DOCKET_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("DOCKET_LLM_API_KEY", "")
    with caplog.at_level("WARNING"):
        b = backend_from_env()
    assert b.model_id == "qwen3.8:27b-mlx"
    assert "DOCKET_LLM_ALLOW_DENYLISTED" in caplog.text


def test_openai_payload_shape(monkeypatch):
    from docket.agent.backend import OpenAICompatibleBackend

    captured = {}

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"n": 5}'}}]}

        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, body=json, headers=headers, timeout=timeout)
        return R()

    monkeypatch.setattr("docket.agent.backend.httpx.post", fake_post)
    # [pre-flight defect 1] the plan asserted `"k" not in json.dumps(body)`, which can
    # never pass: the body contains `"json_schema": {"name": "docket"}` and "docket"
    # contains a k. Use a sentinel key value and assert the sentinel is absent instead.
    b = OpenAICompatibleBackend(model="llama-3.3-70b", base_url="http://x/v1",
                                api_key="sentinel key value")
    assert b.complete_json(system="s", user="u", schema=SCHEMA) == {"n": 5}
    assert captured["url"] == "http://x/v1/chat/completions"
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["headers"]["Authorization"] == "Bearer sentinel key value"
    assert "sentinel key value" not in json.dumps(captured["body"])
    assert b.extractor == "openai-compatible:llama-3.3-70b/json_schema"
    # [ruling R7] one Timeout object, not a scalar; a cold 30B MLX load needs the read leg.
    assert captured["timeout"].connect == 10.0 and captured["timeout"].read >= 600.0


def test_openai_negotiates_down_to_json_object_on_a_client_error(monkeypatch):
    # [ruling R8] capability-probed, and the mode that succeeded is recorded.
    from docket.agent.backend import OpenAICompatibleBackend

    bodies = []

    class R400:
        status_code = 400
        text = "unsupported parameter: response_format.json_schema"

        def json(self):
            return {}

        def raise_for_status(self):
            raise AssertionError("should not be reached")

    class ROK:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"n": 7}'}}]}

        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None, timeout=None):
        bodies.append(json["response_format"]["type"])
        return R400() if len(bodies) == 1 else ROK()

    monkeypatch.setattr("docket.agent.backend.httpx.post", fake_post)
    b = OpenAICompatibleBackend(model="gemma4:e4b", base_url="http://localhost:11434/v1",
                                api_key="")
    assert b.complete_json(system="s", user="u", schema=SCHEMA) == {"n": 7}
    assert bodies == ["json_schema", "json_object"]
    assert b.structured_mode == "json_object"
    assert b.extractor.endswith("/json_object")


def test_openai_retries_transport_errors_then_succeeds(monkeypatch):
    # [ruling R7] two transport retries, fixed backoff, sleep patched so the suite is fast.
    from docket.agent.backend import OpenAICompatibleBackend

    calls = {"n": 0}
    slept = []

    class ROK:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"n": 1}'}}]}

        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("cold model load")
        return ROK()

    monkeypatch.setattr("docket.agent.backend.httpx.post", fake_post)
    monkeypatch.setattr("docket.agent.backend.time.sleep", lambda s: slept.append(s))
    b = OpenAICompatibleBackend(model="gemma4:e4b", base_url="http://x/v1", api_key="")
    assert b.complete_json(system="s", user="u", schema=SCHEMA) == {"n": 1}
    assert calls["n"] == 2 and slept


def test_openai_persistent_server_error_raises_backend_error(monkeypatch):
    # [ruling I6] a raw httpx.HTTPStatusError must never escape the backend abstraction.
    from docket.agent.backend import OpenAICompatibleBackend

    class R503:
        status_code = 503
        text = "service unavailable"

        def json(self):
            return {}

        def raise_for_status(self):
            raise httpx.HTTPStatusError("503", request=None, response=None)

    calls = {"n": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        return R503()

    monkeypatch.setattr("docket.agent.backend.httpx.post", fake_post)
    monkeypatch.setattr("docket.agent.backend.time.sleep", lambda s: None)
    b = OpenAICompatibleBackend(model="gemma4:e4b", base_url="http://x/v1", api_key="")
    with pytest.raises(BackendError):
        b.complete_json(system="s", user="u", schema=SCHEMA)
    assert calls["n"] == 3   # _post's own transport-retry cap (three attempts), not more


def test_openai_401_raises_backend_error_with_no_downgrade(monkeypatch):
    # [ruling I6] 401/403/404 are excluded from the capability downgrade: they mean
    # "wrong key" / "wrong path", not "this server doesn't support json_schema".
    from docket.agent.backend import OpenAICompatibleBackend

    class R401:
        status_code = 401
        text = "unauthorized"

        def json(self):
            return {}

        def raise_for_status(self):
            raise httpx.HTTPStatusError("401", request=None, response=None)

    calls = {"n": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        return R401()

    monkeypatch.setattr("docket.agent.backend.httpx.post", fake_post)
    b = OpenAICompatibleBackend(model="gemma4:e4b", base_url="http://x/v1",
                                api_key="bad-key")
    with pytest.raises(BackendError):
        b.complete_json(system="s", user="u", schema=SCHEMA)
    assert calls["n"] == 1                     # no downgrade retry, no transport retry
    assert b.structured_mode == "json_schema"  # unchanged: nothing ever succeeded


def test_overall_request_budget_caps_total_attempts_per_complete_json(monkeypatch):
    # [ruling M5] schema-validation retries alone must not run unbounded even with a
    # high max_retries; the shared budget documented on `_post` caps the total.
    from docket.agent.backend import MAX_TOTAL_REQUESTS, OpenAICompatibleBackend

    calls = {"n": 0}

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"n": "not-an-int"}'}}]}

        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        return R()

    monkeypatch.setattr("docket.agent.backend.httpx.post", fake_post)
    b = OpenAICompatibleBackend(model="gemma4:e4b", base_url="http://x/v1", api_key="")
    with pytest.raises(BackendError):
        b.complete_json(system="s", user="u", schema=SCHEMA, max_retries=50)
    assert calls["n"] == MAX_TOTAL_REQUESTS


def test_openai_raw_works_standalone_without_complete_json(monkeypatch):
    # [ruling N5] `_raw` must not depend on `complete_json` having run first — it falls
    # back to the instance-level budget set in `__init__` when called directly.
    from docket.agent.backend import OpenAICompatibleBackend

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"n": 9}'}}]}

        def raise_for_status(self):
            pass

    monkeypatch.setattr("docket.agent.backend.httpx.post", lambda *a, **k: R())
    b = OpenAICompatibleBackend(model="gemma4:e4b", base_url="http://x/v1", api_key="")
    assert b._raw(system="s", user="u", schema=SCHEMA) == '{"n": 9}'


def test_anthropic_raw_works_standalone_without_complete_json(monkeypatch):
    # [ruling N5] same guarantee on the other live backend.
    from docket.agent.backend import AnthropicBackend

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"content": [{"type": "tool_use", "input": {"n": 4}}]}

        def raise_for_status(self):
            pass

    monkeypatch.setattr("docket.agent.backend.httpx.post", lambda *a, **k: R())
    b = AnthropicBackend(model="test-model", api_key="k")
    assert b._raw(system="s", user="u", schema=SCHEMA) == '{"n": 4}'


def test_complete_json_budget_is_call_scoped_not_shared_across_calls(monkeypatch):
    # [ruling N5] each complete_json call gets its own local budget, never stored on
    # `self` — so repeated calls on one shared backend instance (plan 07 is a server)
    # can't exhaust or reset each other's counter. More iterations than
    # MAX_TOTAL_REQUESTS would fail if the budget were instance-shared and never reset.
    from docket.agent.backend import MAX_TOTAL_REQUESTS, OpenAICompatibleBackend

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"n": 1}'}}]}

        def raise_for_status(self):
            pass

    monkeypatch.setattr("docket.agent.backend.httpx.post", lambda *a, **k: R())
    b = OpenAICompatibleBackend(model="gemma4:e4b", base_url="http://x/v1", api_key="")
    for _ in range(MAX_TOTAL_REQUESTS + 5):
        assert b.complete_json(system="s", user="u", schema=SCHEMA) == {"n": 1}


def test_anthropic_strips_trailing_v1_from_base_url():
    # [ruling M6] OpenAI-compatible base URLs include /v1; Anthropic's does not.
    from docket.agent.backend import AnthropicBackend

    b = AnthropicBackend(model="test-model", base_url="https://api.anthropic.com/v1",
                         api_key="k")
    assert b.base_url == "https://api.anthropic.com"
    b2 = AnthropicBackend(model="test-model", base_url="https://api.anthropic.com",
                          api_key="k")
    assert b2.base_url == "https://api.anthropic.com"


def test_list_models_filters_denylisted_by_default_and_marks_when_included(monkeypatch):
    # [ruling M3] a picker that never shows a PRC-origin id by default; explicit opt-in
    # marks them rather than hiding the fact that they're denylisted.
    from docket.agent.backend import list_models

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"id": "gemma4:e4b"}, {"id": "qwen3.8:27b-mlx"},
                             {"id": "muse-glimmer:30b-mlx"}]}

    monkeypatch.setattr("docket.agent.backend.httpx.get", lambda *a, **k: R())

    default = list_models(base_url="http://x/v1")
    assert default == [{"id": "gemma4:e4b", "denylisted": False},
                       {"id": "muse-glimmer:30b-mlx", "denylisted": False}]

    included = list_models(base_url="http://x/v1", include_denylisted=True)
    assert {"id": "qwen3.8:27b-mlx", "denylisted": True} in included
    assert len(included) == 3


def test_config_loader_rejects_a_persisted_key(tmp_path):
    # [ruling R6] the file schema REJECTS apiKey outright; .gitignore is not the defence.
    p = tmp_path / "llm.json"
    p.write_text(json.dumps({"provider": "openai-compatible", "apiKey": "whatever secret"}))
    with pytest.raises(PolicyRefusal) as exc:
        load_config(p)
    assert "apiKey" in str(exc.value)
    assert "whatever secret" not in str(exc.value)   # never echo the value


@pytest.mark.parametrize(("payload", "secret_marker", "secret_value"), [
    ({"model": {"api_key": "nested secret in model"}}, "api_key", "nested secret in model"),
    ({"provider": {"apiKey": "nested secret in provider"}}, "apiKey", "nested secret in provider"),
    ({"baseUrl": {"nested": {"apiKey": "deep nested secret"}}}, "apiKey", "deep nested secret"),
])
def test_config_loader_rejects_a_secret_nested_at_any_depth(
    tmp_path, payload, secret_marker, secret_value
):
    # [ruling I2] a credential nested under an allowed field name is still a credential,
    # and reading such a file must raise PolicyRefusal — never a bare TypeError.
    p = tmp_path / "llm.json"
    p.write_text(json.dumps(payload))
    with pytest.raises(PolicyRefusal) as exc:
        load_config(p)
    assert secret_marker in str(exc.value)
    assert secret_value not in str(exc.value)


def test_config_loader_rejects_a_non_string_allowed_field_without_a_secret_key(tmp_path):
    # [ruling I2] a non-string value with no secret-shaped key inside it must still be
    # refused cleanly (this is what previously reached check_model_policy as a dict and
    # crashed with an unhandled TypeError).
    p = tmp_path / "llm.json"
    p.write_text(json.dumps({"model": {"foo": "bar"}}))
    with pytest.raises(PolicyRefusal) as exc:
        load_config(p)
    assert "model" in str(exc.value)


def test_config_round_trip_is_0600_and_holds_no_key(tmp_path):
    import stat

    p = tmp_path / "cfg" / "llm.json"
    write_config(provider="openai-compatible", model="gemma4:e4b",
                 base_url="http://localhost:11434/v1", path=p)
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    cfg = load_config(p)
    assert cfg == {"provider": "openai-compatible", "model": "gemma4:e4b",
                   "baseUrl": "http://localhost:11434/v1"}


def test_precedence_cli_over_env_over_config(monkeypatch, tmp_path):
    # [ruling R6] CLI flags > DOCKET_LLM_* env > JSON config file.
    p = tmp_path / "llm.json"
    write_config(provider="anthropic", model="from-config",
                 base_url="http://config/v1", path=p)
    monkeypatch.setenv("DOCKET_LLM_CONFIG", str(p))
    assert resolve_settings().model == "from-config"
    monkeypatch.setenv("DOCKET_LLM_MODEL", "from-env")
    assert resolve_settings().model == "from-env"
    assert resolve_settings(model="from-cli").model == "from-cli"
    assert resolve_settings().base_url == "http://config/v1"


def test_denylist_is_checked_at_every_resolution_point(monkeypatch, tmp_path):
    # [ruling R3] env, CLI override, config file (however it reached disk) and the
    # constructors — not only env.
    from docket.agent.backend import AnthropicBackend, OpenAICompatibleBackend

    with pytest.raises(PolicyRefusal):
        resolve_settings(model="qwen3.8:27b-mlx")
    # A config file naming a denylisted model must be caught on read regardless of how
    # it reached disk — write_config refuses to write one at all (see
    # test_write_config_refuses_a_denylisted_model), so this writes by hand, standing in
    # for a hand-edited file or one written by an older version of the code.
    p = tmp_path / "llm.json"
    p.write_text(json.dumps({"provider": "openai-compatible", "model": "glm4:9b",
                             "baseUrl": "http://localhost:11434/v1"}))
    monkeypatch.setenv("DOCKET_LLM_CONFIG", str(p))
    with pytest.raises(PolicyRefusal):
        resolve_settings()
    with pytest.raises(PolicyRefusal):
        OpenAICompatibleBackend(model="yi:34b", base_url="http://x/v1", api_key="")
    with pytest.raises(PolicyRefusal):
        AnthropicBackend(model="deepseek-v3", api_key="")


def test_write_config_refuses_a_denylisted_model(tmp_path):
    # [ruling I1] the write path fails fast, before persisting a refused choice — plan
    # 07's PUT /api/settings/model must surface this as a request failure, not silently
    # write a denylisted model and only complain on the next read.
    p = tmp_path / "llm.json"
    with pytest.raises(PolicyRefusal):
        write_config(provider="openai-compatible", model="glm4:9b",
                     base_url="http://localhost:11434/v1", path=p)
    assert not p.exists()


def test_write_config_honours_the_allow_denylisted_override(monkeypatch, tmp_path):
    # [ruling I1] the override (with its warning, asserted elsewhere) still works here.
    monkeypatch.setenv("DOCKET_LLM_ALLOW_DENYLISTED", "1")
    p = tmp_path / "llm.json"
    write_config(provider="openai-compatible", model="qwen3.8:27b-mlx",
                 base_url="http://localhost:11434/v1", path=p)
    assert json.loads(p.read_text())["model"] == "qwen3.8:27b-mlx"


# ---- R9 guards: no test may reach the network, ever ---------------------------------

LIVE_NAMES = ("OpenAICompatibleBackend", "AnthropicBackend", "backend_from_env",
              "backend_from_settings", "list_models")
LIVE_ALLOWED = {"tests/agent/test_backend.py"}


def test_only_this_module_constructs_a_live_backend():
    # [ruling R9] the recorded backend is the only backend a test may construct.
    # [ruling I3] anchored at ROOT so this cannot pass vacuously when pytest runs from
    # somewhere other than the repo root.
    for p in sorted((ROOT / "tests").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if rel in LIVE_ALLOWED:
            continue
        text = p.read_text(encoding="utf-8")
        for name in LIVE_NAMES:
            assert name not in text, f"{rel} references {name}; tests use RecordedBackend"


DENYLIST_DEFINING_FILES = {
    "src/docket/agent/backend.py",
    "tests/agent/test_backend.py",
}
SCANNED_TREES = ("src", "tests", "docs")


def test_no_committed_fixture_default_or_doc_names_a_denylisted_model():
    # [ruling R2] nothing PRC-origin may be named in a fixture, a default or a doc.
    # [ruling I4] widened from a handful of subtrees to src, tests, docs and
    # the root *.md files — the trees that actually matter for the docs or a demo.
    # [ruling I5] uses DOC_SCAN_DENYLIST, not the model-id DENYLIST, so ordinary prose
    # elsewhere in the tree (which I4's widening now reaches) doesn't trip this guard.
    candidates: set[Path] = set()
    for tree in SCANNED_TREES:
        root = ROOT / tree
        if root.exists():
            candidates.update(root.rglob("*"))
    candidates.update(ROOT.glob("*.md"))
    for p in sorted(candidates):
        if not p.is_file() or p.suffix not in {".json", ".md", ".yaml", ".yml", ".py"}:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in DENYLIST_DEFINING_FILES:
            continue
        hit = DOC_SCAN_DENYLIST.search(p.read_text(encoding="utf-8", errors="ignore"))
        assert hit is None, f"{rel} names a denylisted model family: {hit.group(0)!r}"
