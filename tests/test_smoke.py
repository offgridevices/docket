import docket
from docket.errors import (
    AuthorityViolation,
    DocketError,
    TransitionRefused,
    UncitedSentenceError,
    ValidationError,
)


def test_version_is_semver():
    parts = docket.KERNEL_VERSION.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)
    assert docket.KERNEL_VERSION == "0.1.0"


def test_kernel_actor_names_version():
    assert docket.KERNEL_ACTOR == {
        "actorType": "kernel",
        "actorId": f"docket-kernel/{docket.KERNEL_VERSION}",
    }


def test_error_hierarchy():
    assert issubclass(DocketError, Exception)
    for cls in (
        ValidationError,
        AuthorityViolation,
        UncitedSentenceError,
        TransitionRefused,
    ):
        assert issubclass(cls, DocketError)
    assert ValidationError(["a", "b"]).errors == ["a", "b"]
    assert str(ValidationError(["a", "b"])) == "a; b"
    assert TransitionRefused(["x"]).unsatisfied == ["x"]
    assert str(TransitionRefused(["x"])) == "transition refused: x"
