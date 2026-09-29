"""Agreement statistics for comparing a kernel assessment against an expected key.

Pure arithmetic over two ``{questionId: label}`` mappings — no graph, no I/O, no
GAO data. ``label_from_state`` collapses the kernel's four states (1, 2, 3, 4)
onto the two labels GAO-21-460 Figure 6 actually publishes ("assessed" /
"unable to assess"); it is not a claim that GAO itself rates on four states.

Every statistic here is computed over shared keys only
(``sorted(set(pred) & set(truth))``): a question the scorer marked
inapplicable is simply absent from ``pred`` and drops out of the comparison
rather than counting as a disagreement.
"""

from __future__ import annotations


def label_from_state(state: int | None) -> str:
    """Map a kernel dimension/question state onto a comparison label.

    1, 2, 3 -> "assessed"; 4 -> "unable_to_assess"; None -> "not_applicable".
    """
    if state is None:
        return "not_applicable"
    if state == 4:
        return "unable_to_assess"
    return "assessed"


def _shared_keys(pred: dict[str, str], truth: dict[str, str]) -> list[str]:
    return sorted(set(pred) & set(truth))


def agreement(pred: dict[str, str], truth: dict[str, str]) -> float:
    """Fraction of shared keys where ``pred`` and ``truth`` agree.

    0.0 on an empty shared-key set (never a ``ZeroDivisionError``): callers
    such as ``run_all`` invoke this on partial runs.
    """
    keys = _shared_keys(pred, truth)
    if not keys:
        return 0.0
    matches = sum(1 for k in keys if pred[k] == truth[k])
    return matches / len(keys)


def confusion(
    pred: dict[str, str], truth: dict[str, str], positive: str = "unable_to_assess"
) -> dict[str, int]:
    """Binary confusion counts, treating ``positive`` as the positive class."""
    keys = _shared_keys(pred, truth)
    tp = fp = fn = tn = 0
    for k in keys:
        p_hit = pred[k] == positive
        t_hit = truth[k] == positive
        if p_hit and t_hit:
            tp += 1
        elif p_hit and not t_hit:
            fp += 1
        elif not p_hit and t_hit:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": len(keys)}


def precision_recall(
    pred: dict[str, str], truth: dict[str, str], positive: str
) -> tuple[float, float]:
    """Precision and recall for ``positive``; ``(0.0, 0.0)`` on a zero denominator."""
    c = confusion(pred, truth, positive)
    tp, fp, fn = c["tp"], c["fp"], c["fn"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall


def cohen_kappa(pred: dict[str, str], truth: dict[str, str]) -> float:
    """Cohen's kappa over shared keys.

    ``po`` is observed agreement; ``pe`` is expected agreement from the
    per-side label marginals over the union of labels seen. Returns 0.0 when
    ``pe == 1`` — perfect expected agreement is undefined, and 0.0 is the
    honest reading: the statistic carries no information about a one-label
    problem.
    """
    keys = _shared_keys(pred, truth)
    if not keys:
        return 0.0
    po = agreement(pred, truth)
    n = len(keys)
    labels = {pred[k] for k in keys} | {truth[k] for k in keys}
    pe = 0.0
    for label in labels:
        p_pred = sum(1 for k in keys if pred[k] == label) / n
        p_truth = sum(1 for k in keys if truth[k] == label) / n
        pe += p_pred * p_truth
    if pe == 1:
        return 0.0
    return (po - pe) / (1 - pe)


def majority_baseline(truth: dict[str, str]) -> float:
    """Accuracy of always predicting ``truth``'s most common label. 0.0 if empty."""
    if not truth:
        return 0.0
    counts: dict[str, int] = {}
    for label in truth.values():
        counts[label] = counts.get(label, 0) + 1
    return max(counts.values()) / len(truth)


def by_band(
    pred: dict[str, str], truth: dict[str, str], bands: dict[str, str]
) -> dict[str, float]:
    """``agreement`` broken out per band.

    A shared key with no entry in ``bands`` is ignored. A band with no shared
    keys is absent from the result, not present with a 0.0.
    """
    keys = _shared_keys(pred, truth)
    grouped: dict[str, list[str]] = {}
    for k in keys:
        band = bands.get(k)
        if band is None:
            continue
        grouped.setdefault(band, []).append(k)
    return {
        band: agreement({k: pred[k] for k in band_keys}, {k: truth[k] for k in band_keys})
        for band, band_keys in sorted(grouped.items())
    }
