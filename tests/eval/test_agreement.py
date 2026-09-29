# tests/eval/test_agreement.py
from docket.eval.agreement import (
    agreement,
    by_band,
    cohen_kappa,
    confusion,
    label_from_state,
    majority_baseline,
    precision_recall,
)


def test_labels():
    assert [label_from_state(s) for s in (1, 2, 3, 4, None)] == ["assessed"] * 3 + [
        "unable_to_assess", "not_applicable"]


def test_stats_known_values():
    truth = {
        "a": "assessed", "b": "assessed", "c": "unable_to_assess", "d": "unable_to_assess",
    }
    pred = {
        "a": "assessed", "b": "unable_to_assess", "c": "unable_to_assess", "d": "unable_to_assess",
    }
    assert agreement(pred, truth) == 0.75
    assert confusion(pred, truth) == {"tp": 2, "fp": 1, "fn": 0, "tn": 1, "n": 4}
    p, r = precision_recall(pred, truth, "unable_to_assess")
    assert (p, r) == (2 / 3, 1.0)
    assert abs(cohen_kappa(pred, truth) - 0.5) < 1e-9   # po=0.75, pe=0.5
    assert majority_baseline(truth) == 0.5
    assert by_band(pred, truth, {"a": "design", "b": "design", "c": "exec", "d": "exec"}) == {
        "design": 0.5, "exec": 1.0}


def test_kappa_degenerate():
    t = {"a": "assessed", "b": "assessed"}
    assert cohen_kappa(t, t) == 0.0  # expected agreement 1 -> defined as 0


def test_empty_and_partial_inputs_do_not_raise():
    assert agreement({}, {}) == 0.0
    assert by_band({}, {}, {}) == {}
    assert precision_recall({"a": "assessed"}, {"a": "assessed"}, "unable_to_assess") == (0.0, 0.0)
    assert agreement(
        {"a": "assessed", "z": "assessed"}, {"a": "assessed"}
    ) == 1.0  # shared keys only
