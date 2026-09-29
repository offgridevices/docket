class DocketError(Exception):
    """Base class for all docket errors."""


class ValidationError(DocketError):
    """An object failed schema or envelope validation."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class AuthorityViolation(DocketError):
    """An agent actor attempted something outside the agent authority boundary."""


class UncitedSentenceError(DocketError):
    """A narrative sentence has no object citation, or cites a number not in a cited Result.

    `narrative_id` and `sentence` are optional, keyword-only attributes for a caller
    that already knows which `Narrative` object and which sentence within it triggered
    the error — added for the API layer (plan 07), which turns this into a 422 response
    naming the offending sentence and would otherwise have to parse it back out of the
    message string. `message` stays a single positional argument so every existing
    caller (`render.py`'s `f"{narrative_id}: " + "; ".join(check_citations_errors)`)
    is unaffected; a caller that does not pass `narrative_id`/`sentence` leaves both
    `None`, and a consumer must fall back to parsing `str(exc)`.
    """

    def __init__(self, message: str, *, narrative_id: str | None = None,
                sentence: str | None = None):
        super().__init__(message)
        self.narrative_id = narrative_id
        self.sentence = sentence


class TransitionRefused(DocketError):
    """A lifecycle transition was refused because policy checks failed."""

    def __init__(self, unsatisfied: list[str]):
        super().__init__("transition refused: " + ", ".join(unsatisfied))
        self.unsatisfied = unsatisfied


class BackendError(DocketError):
    """An LLM backend failed to return valid structured output."""


class RecordingMissing(BackendError):
    """RecordedBackend has no response for this prompt."""


class PolicyRefusal(DocketError):
    """A configuration is refused by policy (e.g. a PRC-origin model, or a config file
    that tries to persist an API key)."""
