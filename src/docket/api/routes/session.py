"""Session lifecycle and read-only routes: episodes and objects out of a session's copy
of the graph. Every route here is read-only after `POST /session`; the mutating agent
and kernel routes live in `routes/agent.py` and `routes/kernel.py` (plan 07 Tasks 3-4).
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Request
from pydantic import BaseModel

from docket.api.config import RECORDED_REQUEST_POLICY, sources_dir
from docket.api.serialize import episode_view, object_view

router = APIRouter()

#: The one request text this repository has a *committed model response* for, and the
#: exact two arguments it was recorded under. Both are facts about files in the tree, not
#: choices this route makes: the request lives at `tests/fixtures/requests/`, and the
#: source-artifact label and policy id are the ones `uv run docket agent elicit --help`
#: documents for replaying `tests/fixtures/recorded/elicit.json` (and that
#: `tests/api/test_agent_routes.py`'s own `elicited` fixture posts). `elicit`'s user
#: prompt interpolates the source artifact and the policy id, and the recording key is a
#: hash over that prompt — change either string and the committed response no longer
#: answers, which is why the UI is told all three together rather than being left to
#: guess two of them. `RECORDED_REQUEST_POLICY` lives in `api.config` now, not here — it
#: is also what `sessions.SessionStore.create` seeds into every new session, so the
#: value a caller is told to send and the value that actually resolves in the graph can
#: never drift apart; re-imported under this name because
#: `tests/api/test_sources_route.py` imports it from this module.
RECORDED_REQUEST_PATH = "tests/fixtures/requests/omfv-con-2020-02-25.md"
RECORDED_REQUEST_ARTIFACT = (
    "sources/army-2020-02-25-omfv-characteristics-for-industry-comment.md"
)


_LOCAL_FILE_ROW = re.compile(r"^\| Local file \| `([^`/]+)`", re.MULTILINE)


class SessionCreate(BaseModel):
    source: str = "new"


@router.post("/session")
def create_session(body: SessionCreate, request: Request) -> dict:
    s = request.app.state.sessions.create(body.source)
    return {"id": s.id, "source": s.source, "created": s.created}


@router.get("/sessions")
def list_sessions(request: Request) -> dict:
    return {"sessions": request.app.state.sessions.list()}


@router.delete("/session/{sid}")
def delete_session(sid: str, request: Request) -> dict:
    request.app.state.sessions.delete(sid)
    return {"deleted": sid}


@router.get("/session/{sid}/episodes")
def list_episodes(sid: str, request: Request) -> dict:
    g = request.app.state.sessions.get(sid).graph
    episodes = [episode_view(g, ep["id"]) for ep in g.all("DecisionEpisode")]
    return {"episodes": episodes}


@router.get("/session/{sid}/episode/{eid}")
def get_episode(sid: str, eid: str, request: Request) -> dict:
    g = request.app.state.sessions.get(sid).graph
    return episode_view(g, eid)


@router.get("/session/{sid}/object/{oid}")
def get_object(sid: str, oid: str, request: Request, rev: int | None = None) -> dict:
    g = request.app.state.sessions.get(sid).graph
    return object_view(g, oid, rev=rev)


@router.get("/sections")
def list_sections() -> dict:
    """`render.SECTIONS` as `[{"key", "title"}]`. Import-guarded: `render.py` is
    present but was, at plan 07 Task 1's dispatch, still mid-review on plan 03b — a
    route reading its section list must not 500 the whole health-adjacent surface if a
    later revision ever drops it before landing.
    """
    try:
        from docket.kernel.render import SECTIONS
    except ImportError:
        return {"sections": []}
    return {"sections": [{"key": key, "title": title} for key, title in SECTIONS]}


def _first_heading(path) -> str | None:
    """The first Markdown `#` heading in a `.source.md` provenance stub, or `None`.

    Read line by line and capped, not `read_text()`: a source stub is a small file today
    and this route is polled by a picker, so there is no reason to hold a whole document
    in memory to find its title.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i > 40:
                    break
                if line.startswith("#"):
                    return line.lstrip("#").strip() or None
    except OSError:
        return None
    return None


def _recorded_request() -> dict | None:
    """The committed request text, its two elicitation arguments, and whether the
    *currently configured* recording actually holds an answer for that exact prompt.

    `answerRecorded` is checked, not asserted: `DOCKET_LLM_RECORDING` defaults to
    `tests/fixtures/recorded/default.json`, which is deliberately empty (`recorded/
    README.md`, ruling N3), so a UI that offered this request without saying whether the
    answer exists would put a button on screen that 503s. The check recomputes the
    fixture key the same way `RecordedBackend` does — over the prompt only — rather than
    calling the backend, so nothing is elicited and nothing is written.
    """
    from docket.api.config import repo_root

    path = repo_root() / RECORDED_REQUEST_PATH
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return {
        "path": RECORDED_REQUEST_PATH,
        "text": text,
        "sourceArtifact": RECORDED_REQUEST_ARTIFACT,
        "policyId": RECORDED_REQUEST_POLICY,
        **_recorded_answer_state(text),
    }


def _recorded_answer_state(request_text: str) -> dict:
    from docket.agent.backend import recording_key, resolve_settings
    from docket.agent.elicit import ELICITATION_SCHEMA, USER_TEMPLATE
    from docket.agent.prompts import system_prompt
    from docket.errors import PolicyRefusal

    try:
        recording = resolve_settings().recording
    except PolicyRefusal:
        # A denylisted or malformed configured model is `routes/settings.py`'s refusal to
        # report, not this picker's — say "unknown", never guess "yes".
        return {"recording": None, "answerRecorded": False}
    user = USER_TEMPLATE.format(source_artifact=RECORDED_REQUEST_ARTIFACT,
                                request_text=request_text,
                                policy_id=RECORDED_REQUEST_POLICY)
    key = recording_key(system_prompt(), user, ELICITATION_SCHEMA)
    try:
        with open(recording, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"recording": str(recording), "answerRecorded": False}
    return {"recording": str(recording), "answerRecorded": key in data}


@router.get("/sources")
def list_sources() -> dict:
    """`sources/` as the Intake picker sees it: one entry per `.source.md` provenance
    stub, with the artefact it documents and that stub's own first heading as the title.

    Keyed on the stubs rather than on the PDFs (the plan's "`sources/*.pdf`") because the
    stub is the thing that always exists — several entries in `sources/` are stubs for a
    document that is cited but not redistributable, and a listing built from the binaries
    alone would silently drop exactly those. Public data only: `sources/` holds nothing
    else, by the repository's own hard boundary.

    `recordedRequest` rides along so the Intake screen needs one round trip, not two: it
    is the committed request text (and the two arguments the committed model response was
    recorded under) the `Load the recorded request` button fills the form with.
    """
    directory = sources_dir()
    entries: list[dict] = []
    if directory.is_dir():
        for stub in sorted(directory.glob("*.source.md")):
            stem = stub.name[: -len(".source.md")]
            companions = sorted(
                p.name for p in directory.iterdir()
                if p.is_file() and p.stem == stem and p.name != stub.name
            )
            # Downloaded documents are not committed; the note names the file a local
            # copy is saved under, so the listing is the same on a fresh clone.
            named = _LOCAL_FILE_ROW.search(stub.read_text(encoding="utf-8"))
            artifact = (companions[0] if companions
                        else named.group(1) if named else stub.name)
            entries.append({
                "name": stem,
                "artifact": f"sources/{artifact}",
                "title": _first_heading(stub),
                "hasLocalCopy": bool(companions),
            })
    return {"sources": entries, "recordedRequest": _recorded_request()}
