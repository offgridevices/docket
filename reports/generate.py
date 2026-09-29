"""Generate `reports/phase1-validation.md` from every demo's `out/` JSON.

    uv run python -m reports.generate [--out ROOT]

This module never runs a demo and never opens a source PDF. It reads the JSON each demo
already wrote under `<root>/demos/<name>/out/` (`demos/run_all.py` is what produces
those; run it first) and formats what is there. Every figure in the generated report —
every count, ratio, hash and label — is a value loaded out of one of those JSON files, or
a `len()`/simple pairing over one; nothing here is a literal statistic typed into a
string. The one deliberate exception is the second human reader's row (plan 05 Task 8):
`"pending: Shreyash"` is not a result, it is the record that a human step has not
happened yet, and no agent may fill it in.

`--out` mirrors `demos/run_all.py --out`: a bare invocation reads and writes the
committed, in-repo layout (`demos/*/out/`, `reports/phase1-validation.md`); passing
a directory reads/writes the same relative layout under it, so a test can run
`demos.run_all.run_all(tmp_path)` and then `write_report(tmp_path)` and diff the result
against the committed file without touching the working tree (plan 05 Task 8's ledger
ruling: T8 adds only this report and the CLI command, not `run_all.py` itself).

Section order and headings are fixed in `SECTION_HEADINGS` and must never drift from the
functions below — `tests/demos/test_run_all.py` asserts both the heading text and the
byte-identity of a fresh regeneration against the committed file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every demo present in `demos/run_all.py`'s own `DEMOS` list, paired with the file its
# own `run.py` either declares as `RESULTS_FILE` or (for the three that do not) writes
# under this literal name — the same three names `demos/run_all.py`'s own
# `DEFAULT_RESULTS_FILE` table carries, kept here rather than imported so this module
# never has to reach into that module's private helpers to resolve a path.
RESULTS_FILES: dict[str, str] = {
    "a_cbo_gcv_2013": "results.json",
    "ablation": "ablation.json",
    "b_omfv_2019_2023": "results.json",
    "budget_books": "conflicts.json",
    "control_gao_15_548": "control.json",
    "validation_gao_21_460": "agreement.json",
}

SECTION_HEADINGS: tuple[str, ...] = (
    "## 1. Method",
    "## 2. GAO-21-460 \u2014 per-question agreement",
    "## 3. GAO-15-548 \u2014 positive control",
    "## 4. GAO-23-106549 \u2014 verdict grid and finding-detection matrix",
    "## 5. Ablations",
    "## 6. Budget-book conflicts",
    "## 7. Reproducibility",
    "## 8. What Phase I proves, and what it does not",
)

# Phrases the report must never contain, case-insensitively, each with the reason it is
# false or out of scope (CLAUDE.md "Claims that must stay honest"; design ruling R14).
# This is not the deliverable denylist (`scripts/check-citations.py`) — this report is
# not a deliverable file and is not scanned by that script's full rule set — it is a
# second, independent guard on this specific artefact, checked by
# `tests/demos/test_run_all.py`.
DENYLIST: tuple[tuple[str, str], ...] = (
    ("GAO-validated", "GAO did not assess or verify the Army's underlying analytical "
        "work (GAO-23-106549 fn. 7, App. I)"),
    ("GAO validated", "same — GAO validated nothing of ours"),
    ("validated by GAO", "same — GAO validated nothing of ours"),
    ("GAO-approved", "GAO approved nothing of ours"),
    ("GAO approved", "GAO approved nothing of ours"),
    ("reproduces GAO's per-question", "GAO-21-460 Fig. 6 is the only per-question key "
        "GAO has published; the GAO-23-106549 per-question layer is ours"),
    ("GAO's per-question", "the GAO-23-106549 per-question layer is ours, not GAO's"),
    ("deterministic LLM", "the reproducibility promise is architectural, not a claim "
        "about inference"),
    ("reproducible LLM", "same"),
    ("deterministic inference", "same"),
    ("lacked sensitivity analysis", "GAO credited the combat-effectiveness section for "
        "varying engine power and infantry carried across the four vehicles"),
    ("no sensitivity analysis", "same"),
    ("without sensitivity analysis", "same"),
    ("the Army failed to", "GAO made no recommendations and found no fault with the "
        "Army's analysis, only with what the report represented of it"),
)

# No provider, model or hosting commitment anywhere in this report (design ruling R14) —
# checked the same way regardless of context, because there is no legitimate reason for
# any of these strings to appear in a validation report about a kernel's own scoring.
PROVIDER_NAMES: tuple[str, ...] = (
    "OpenAI", "Anthropic", "Claude", "Google Gemini", "Gemini", "Azure OpenAI",
    "Amazon Bedrock", "Mistral", "Cohere", "Llama", "DeepSeek", "Qwen", "GLM", "Kimi",
    "ERNIE", "Hunyuan",
)

REQUIRED: tuple[str, ...] = (
    "GAO did not assess or verify",
    "only per-question",
    "ours",
    "pending: Shreyash",
    "GAO credited",
    "no evaluation run",
)


# ---- loading -----------------------------------------------------------------------

def _demo_out(root: Path, name: str) -> Path:
    return root / "demos" / name / "out"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _results(root: Path, name: str) -> dict:
    return _load(_demo_out(root, name) / RESULTS_FILES[name])


def _manifest(root: Path, name: str) -> dict | None:
    """`Graph.save`'s own manifest for the demo's persisted store — `kernelVersion`,
    `objects`, `logEntries`, `snapshotHash` — or `None` for a demo that never calls
    `Graph.save` (only `ablation`: its transforms run in memory and are asserted
    byte-for-bit non-mutating by `run_ablations` itself, so there is no store to hash)."""
    path = _demo_out(root, name) / "graph" / "manifest.json"
    return _load(path) if path.is_file() else None


_BAND_ORDER = {"DES": 0, "EXE": 1, "PRE": 2}


def _qsort_key(qid: str) -> tuple[int, int]:
    prefix, num = qid.split("-")
    return (_BAND_ORDER.get(prefix, 9), int(num))


# ---- markdown helpers ----------------------------------------------------------------

def _esc(cell: object) -> str:
    return str(cell).replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(_esc(c) for c in row) + " |")
    return "\n".join(lines)


def _kv(pairs: list[tuple[str, object]]) -> str:
    return "; ".join(f"{k} = {v}" for k, v in pairs)


# ---- section 1: method ----------------------------------------------------------------

def _section_1(root: Path) -> str:
    a = _results(root, "validation_gao_21_460")
    return "\n".join([
        SECTION_HEADINGS[0],
        "",
        "**The answer-key method (design \u00a79.2 steps 1-3).** The two demonstrations "
        "carrying a numeric key each reconstruct a published GAO study from its own "
        "public record into the schema, score the reconstruction with the standards "
        "scorer under the tailoring GAO used for that report, and compare the kernel's "
        "per-question ratings against GAO's own published labels. Every reconstructed "
        "object carries a page locator into the source PDF; every gap the "
        "reconstruction itself could not close is recorded as an `InsufficientEvidence` "
        "object, not smoothed over.",
        "",
        "**Blinding.** GAO-21-460's fixture (`demos/validation_gao_21_460/build.py`) "
        "was written by a single agent working only from a mechanical extraction of the "
        "study's own narrative pages. That agent never opened GAO's published labels or "
        "`ground_truth.yaml`; a separate, unblinded step transcribed those labels "
        f"afterward, and only `run.py` opens both sides to compare them "
        f"(`\"blinded\": {json.dumps(a['blinded'])}`, "
        "`demos/validation_gao_21_460/out/agreement.json`). The blind protects against "
        "the builder fitting the fixture to the key; it does not extend to the fixture "
        "table itself, which an unblinded author wrote from the plan's own "
        "requirements \u2014 see `demos/validation_gao_21_460/README.md` \u00a71 for "
        "that boundary, stated there rather than repeated here.",
        "",
        "**Human reconciliation (design \u00a79.2 step 4).** GAO's own protocol has two "
        "analysts score independently and then reconcile; the kernel's ratings stand as "
        "the third reader here. The second human reader is a human act no agent may "
        "perform:",
        "",
        _table(
            ["Reader", "Role", "Status"],
            [
                ["Kernel (reader 1)", "mechanical scoring under the published tailoring",
                 "complete \u2014 \u00a72, \u00a73, \u00a74"],
                ["Shreyash (reader 2)",
                 "independent read of the same record, reconciled against the kernel's "
                 "calls", "pending: Shreyash"],
            ],
        ),
        "",
        "**Ablation (design \u00a79.2 step 5).** Re-running the same record with a "
        "mechanism turned off (the scope checker, `Exclusion` objects, "
        "`InsufficientEvidence` objects, the `silence` structural rule) shows which "
        "findings are lost outright and which are only re-typed as a schema or silence "
        "finding \u2014 \u00a75.",
    ])


# ---- section 2: GAO-21-460 agreement --------------------------------------------------

def _section_2(root: Path) -> str:
    a = _results(root, "validation_gao_21_460")
    pq = a["per_question"]
    rows = [
        [qid, pq[qid]["band"], f"`{pq[qid]['rule']}`", pq[qid]["state"], pq[qid]["pred"],
         pq[qid]["truth"], "yes" if pq[qid]["match"] else "no"]
        for qid in sorted(pq, key=_qsort_key)
    ]
    table = _table(
        ["Question", "Band", "Kernel rule fired", "State", "Kernel label",
         "GAO Fig. 6 label", "Match"],
        rows,
    )
    conf = a["confusion"]
    # The disagreements are read off the same per-question rows the table prints — never
    # a typed count (a hand-typed "two" once contradicted the table's three).
    misses = [qid for qid in sorted(pq, key=_qsort_key) if not pq[qid]["match"]]
    miss_bands = sorted({pq[qid]["band"] for qid in misses})
    miss_ids = ", ".join(f"`{qid}`" for qid in misses) if misses else "none"
    miss_where = (
        f"all fall in the {miss_bands[0]} band" if len(miss_bands) == 1
        else "fall in the " + " and ".join(miss_bands) + " bands"
    )
    blockers = ", ".join(f"`{b}`" for b in a["blockers"]) if a["blockers"] else "none"
    warnings = ", ".join(f"`{w}`" for w in a["warnings"]) if a["warnings"] else "none"
    return "\n".join([
        SECTION_HEADINGS[1],
        "",
        f"Scored blinded (`blinded: {a['blinded']}`) against GAO-21-460 Figure 6 under "
        f"the `{a['tailoring']}` tailoring \u2014 GAO's only per-question answer key "
        "published for any product in this line; every other product this standard "
        "draws on states its verdicts in prose only (\u00a73, \u00a74).",
        "",
        table,
        "",
        f"**Agreement:** {a['agreement']}. **Cohen's \u03ba:** {a['kappa']}. "
        f"**Majority-class baseline:** {a['majority_baseline']}. **Confusion** "
        f"(positive class `unable_to_assess`): tp={conf['tp']}, fp={conf['fp']}, "
        f"fn={conf['fn']}, tn={conf['tn']}, n={conf['n']}. **Precision / recall on "
        f"`unable_to_assess`:** {a['precision_unable']} / {a['recall_unable']}.",
        "",
        "**By band:** " + _kv(sorted(a["by_band"].items())) + ".",
        "",
        "**Dimension verdicts** (ours \u2014 GAO-21-460 does not use the "
        "objectivity/validity/reliability frame; these are read off the same "
        "per-question ratings above): " + _kv(sorted(a["dimensionVerdicts"].items()))
        + ".",
        "",
        f"**Readiness:** ready={a['ready']}; blockers: {blockers}; warnings: {warnings}.",
        "",
        f"The {len(misses)} disagreements ({miss_ids}) {miss_where}: the "
        "kernel reads a Data Reliability question from the claims that cite the "
        "evidence register, and this record's not-yet-reported study carries no claims "
        "yet, so its reliability steps never reach those questions the way GAO's "
        "interview-based answer did. That predicate is unchanged by this report \u2014 "
        "see `docs/decisions/2026-09-05-data-questions-are-claim-scoped.md` \u2014 the "
        "gap is reported, not closed by widening a rule.",
    ])


# ---- section 3: GAO-15-548 control -----------------------------------------------------

def _section_3(root: Path) -> str:
    c = _results(root, "control_gao_15_548")
    states, rules = c["states"], c["rules"]
    rows = [
        [qid, states[qid] if states[qid] is not None else "\u2014", f"`{rules[qid]}`"]
        for qid in sorted(states, key=_qsort_key)
    ]
    table = _table(["Question", "State", "Rule"], rows)
    ag = c["agreement"]
    blockers = ", ".join(f"`{b['rule']}`" for b in c["blockers"]) if c["blockers"] else "none"
    return "\n".join([
        SECTION_HEADINGS[2],
        "",
        "GAO-15-548 (Army combat-vehicle industrial base, 2015) is the positive "
        "control: a study GAO's review found sound, run through the same scorer, to "
        "show the scorer is not a hammer that sees only nails.",
        "",
        table,
        "",
        "**Dimensions:** " + _kv(sorted(c["dimensions"].items())) + f" (aggregation "
        f"rule: `{c['aggregationRule']}`; `aggregationK` = {c['aggregationK']}).",
        "",
        "> " + c["note"],
        "",
        "**Qualifiers on each verdict** (every state-2 question named, not folded "
        "silently into \"generally\"): " + _kv(sorted(c["dimensionQualifiers"].items()))
        + ".",
        "",
        f"**Agreement against `{ag['against']}`:** {ag['agreement']} "
        f"(\u03ba={ag['kappa']}, n={ag['n']}, state agreement={ag['state_agreement']}, "
        f"majority baseline={ag['majority_baseline']}, disagreements="
        f"{ag['disagreements'] if ag['disagreements'] else '{}'}). This target is "
        "**ours** \u2014 GAO published no per-question key for GAO-15-548.",
        "",
        f"**Readiness:** ready={c['ready']}; blockers: {blockers}; open exclusions: "
        f"{len(c['openExclusions'])}; open gaps: {len(c['openGaps'])}.",
        "",
        f"**Package:** `{c['package']['path']}`, sha256 `{c['package']['hash']}`.",
    ])


# ---- section 4: GAO-23-106549 grid + F1-F9 --------------------------------------------

def _section_4(root: Path) -> str:
    b = _results(root, "b_omfv_2019_2023")
    grid = b["grid"]
    grid_rows = [
        [section, dims["objectivity"], dims["validity"], dims["reliability"]]
        for section, dims in sorted(grid.items())
    ]
    cell_count = sum(len(dims) for dims in grid.values())
    grid_table = _table(["Section", "Objectivity", "Validity", "Reliability"], grid_rows)
    ce_des6 = b["states"]["ce"]["DES-6"]

    findings = b["findings"]
    f_ids = sorted((k for k in findings if k.startswith("F")), key=lambda k: int(k[1:]))
    f_rows = [
        [fid, findings[fid]["detected_by"], findings[fid]["page"],
         ", ".join(findings[fid]["attributed_to"]),
         ", ".join(findings[fid]["cross_fired_on"]) or "\u2014",
         "; ".join(findings[fid]["by"])]
        for fid in f_ids
    ]
    f_table = _table(
        ["Finding", "Detected by", "Page", "Attributed to", "Cross-fires on", "Mechanism"],
        f_rows,
    )

    cross_fires = findings["cross_fires"]
    suppressed = findings["cross_fires_suppressed_by_our_attribution"]
    cf_rows = [[rule, ", ".join(sections)] for rule, sections in sorted(cross_fires.items())]
    cf_table = _table(["Cross-fire", "Also fires on"], cf_rows)
    supp_rows = [[rule, ", ".join(sections)] for rule, sections in sorted(suppressed.items())]
    supp_table = _table(["Suppressed cross-fire", "Would also fire on"], supp_rows)

    gc = b["grid_counterfactuals"]
    k_rows = [[row["k"], row["grid_match"], _kv(sorted(row["objectivity"].items()))]
              for row in gc["k"]]
    k_table = _table(["k", "grid_match", "Objectivity by section"], k_rows)

    r2 = gc["r2_clauses_withdrawn"]
    repair = b["repair"]

    return "\n".join([
        SECTION_HEADINGS[3],
        "",
        f"**{b['grid_match']} of {cell_count} cells match** GAO-23-106549's published "
        "verdicts. GAO states these nine verdicts in prose \u2014 three section "
        "headings, each followed by an Objectivity / Validity / Reliability paragraph, "
        "printed pp. 8-14 \u2014 and publishes no per-question labels. Arranging the "
        "nine as a 3\u00d73 grid is ours; the verdicts inside it are GAO's.",
        "",
        "GAO did not assess or verify the Army's underlying analytical work "
        "(GAO-23-106549 footnote 7 and Appendix I); the Army had no comments on the "
        "draft and GAO made no recommendations. Every finding below is therefore a "
        "**representation** failure \u2014 a claim about how the report described its "
        "own analysis \u2014 not a finding that the analysis itself was wrong. Nor did "
        "GAO find the Army's combat-effectiveness section short of sensitivity "
        "analysis: GAO credited it for varying assumptions (engine power, infantry "
        f"carried) across the four vehicles, and that section's own `DES-6` rates "
        f"{ce_des6}, not the floor.",
        "",
        grid_table,
        "",
        "### What the nine cells rest on",
        "",
        "> " + gc["note"],
        "",
        f"Withdrawing ruling R2's narrative-only clauses on `PRE-3`/`PRE-4` measures "
        f"{r2['grid_match']} of {cell_count} (clauses: {', '.join(r2['clauses'])}; "
        f"decision: `{gc['r2_decision']}`).",
        "",
        f"Sweeping `pol-omfv.aggregationK` (decision: `{gc['k_decision']}`):",
        "",
        k_table,
        "",
        "### The nine findings",
        "",
        f_table,
        "",
        "**Cross-fires** \u2014 a finding this demonstration attributes to one section "
        "also fires on the sections named below, under the kernel's own (graph-global) "
        "reachability, before this demonstration's attribution rule narrows it:",
        "",
        cf_table,
        "",
        "**Suppressed by our attribution rule** \u2014 the kernel's own scoping would "
        "additionally report a mechanism on these sections; this demonstration's "
        "attribution rule (which reads the episode the finding names) does not, and the "
        "suppression is measured on every run, not asserted:",
        "",
        supp_table,
        "",
        "> " + findings["cross_fires_suppressed_by_our_attribution_note"],
        "",
        "### The counterfactual repair",
        "",
        f"Supplying the withheld combat-effectiveness metric's classification metadata "
        f"moves `ev-ce-metrics` from `{repair['before']}` to `{repair['after']}` "
        f"(classification stays `{repair['classification_level']}`); `EXE-14` moves "
        f"{repair['exe14_before']} \u2192 {repair['exe14_after']}, and re-scored under "
        f"the grid tailoring `EXE-5` moves {repair['exe5_before']} \u2192 "
        f"{repair['exe5_after']}, with the combat-effectiveness reliability verdict "
        f"moving `{repair['ce_row_before']['reliability']}` \u2192 "
        f"`{repair['ce_row_after']['reliability']}`. Validity does not move.",
        "",
        "> " + repair["note"],
        "",
        "> " + repair["reliability_note"],
    ])


# ---- section 5: ablations ---------------------------------------------------------------

_ABLATION_SECTION_NAMES = {
    "ep-omfv-2020-02-r4-fs": "force structure designs and operational concepts",
    "ep-omfv-2020-02-r4-ce": "combat effectiveness",
}


def _section_5(root: Path) -> str:
    ab = _results(root, "ablation")
    parts = [
        SECTION_HEADINGS[4],
        "",
        "Design \u00a79.2 step 5: the same two March-2023 sections, re-scored with one "
        "mechanism removed at a time. `demos/ablation/out/ablation.json` is the full "
        "per-item comparison (`demos/ablation/out/ablation.md` renders it in full); this "
        "section is the bucketed summary and the one rating movement the ablations "
        "surfaced that the brief's own hypotheses did not name in advance.",
        "",
    ]
    for ep_id in sorted(ab):
        section = ab[ep_id]
        variants = [v for v in section if v != "baseline"]
        name = _ABLATION_SECTION_NAMES.get(ep_id, ep_id)
        bucket_rows = []
        for v in variants:
            g = section[v]["gained_findings"]
            bucket_rows.append([
                v, len(g["schema"]), len(g["silence"]), len(g["other"]),
                len(section[v]["substitutions"]),
                ", ".join(section[v]["lost_findings"]) or "\u2014",
            ])
        parts.append(f"### `{ep_id}` \u2014 {name}")
        parts.append("")
        parts.append(_table(
            ["Variant", "Gained (schema)", "Gained (silence)", "Gained (other)",
             "Substitutions", "Lost findings"],
            bucket_rows,
        ))
        parts.append("")
        moved = []
        for v in variants:
            vc = section[v]["verdicts_changed"]
            rc = section[v]["ratings_changed"]
            if vc:
                moved.append(f"`{v}` moves verdict(s) " +
                             _kv(sorted((d, f"{b[0]} \u2192 {b[1]}") for d, b in vc.items())))
            if rc:
                moved.append(f"`{v}` moves rating(s) " +
                             _kv(sorted((q, f"{b[0]} \u2192 {b[1]}") for q, b in rc.items())))
        if moved:
            parts.append("**Measured rating movement** (not in the brief's original "
                          "hypothesis table): " + "; ".join(moved) + ".")
        else:
            parts.append("No variant moved a rating or a dimension verdict on this "
                          "section.")
        parts.append("")
    return "\n".join(parts).rstrip()


# ---- section 6: budget-book conflicts --------------------------------------------------

def _section_6(root: Path) -> str:
    bb = _results(root, "budget_books")
    conflicts = bb["conflicts"]
    rows = [
        [c["rule"], c["severity"], ", ".join(c["objects"]), c["message"]]
        for c in conflicts
    ]
    table = _table(["Rule", "Severity", "Evidence objects", "Message"], rows)
    return "\n".join([
        SECTION_HEADINGS[5],
        "",
        f"{len(bb['subjects'])} data subjects, drawn from the annual R-2/R-3/R-4 budget "
        f"exhibits (PB2021-PB2027) plus GAO's own programme profile, produce "
        f"{len(conflicts)} value conflicts \u2014 {len(bb['internal'])} within a single "
        f"document, {len(bb['across'])} across documents. This is a validator finding "
        "about the public record's own internal consistency; it is not a claim that the "
        "Army's analysis was wrong.",
        "",
        "**Subjects:** " + ", ".join(f"`{s}`" for s in sorted(bb["subjects"])) + ".",
        "",
        table,
        "",
        "**Other findings on this record:** " + _kv(sorted(bb["otherFindings"].items()))
        + ". **Blocking rule kinds:** " + ", ".join(f"`{r}`" for r in bb["blockers"]) + ".",
    ])


# ---- section 7: reproducibility --------------------------------------------------------

def _section_7(root: Path) -> str:
    rows = []
    for name in sorted(RESULTS_FILES):
        manifest = _manifest(root, name)
        if manifest is None:
            rows.append([name, "\u2014 (no persisted store; see note)", "\u2014", "\u2014",
                         "\u2014"])
        else:
            rows.append([name, manifest["snapshotHash"], manifest["logHead"],
                         manifest["objects"], manifest["logEntries"]])
    manifest_table = _table(
        ["Demo", "Graph snapshot hash", "Log head", "Objects", "Log entries"], rows,
    )

    a_cbo = _results(root, "a_cbo_gcv_2013")
    control = _results(root, "control_gao_15_548")

    return "\n".join([
        SECTION_HEADINGS[6],
        "",
        "**It is the kernel that is reproducible \u2014 this section makes no claim "
        "about any model.** Byte-identical repeat output from a model call is "
        "achievable only by controlling the serving stack down to the kernel; a "
        "model-agnostic product calling a hosted endpoint cannot make, verify or even "
        "detect that guarantee, which is why the reproducibility promise here is "
        "architectural: the kernel's own read/score/render path, not any model call, "
        "produces the hashes below, and `scripts/determinism-check.sh` re-runs that "
        "path twice in independent processes and diffs every byte.",
        "",
        "`scripts/determinism-check.sh` performs two checks from two builds: it builds "
        "the whole demo tree twice, in two independent processes, and diffs every byte "
        "(\"DETERMINISM OK \u2014 two independent builds are byte-identical.\"); then it "
        "reuses one of those trees against the committed `demos/*/out` "
        "(\"COMMITTED OUTPUT OK \u2014 matches a fresh run for every demo with "
        "committed output.\"). This report is produced the same way \u2014 "
        "`tests/demos/test_run_all.py` regenerates it into a temporary directory and "
        "compares the result to the committed file, byte for byte.",
        "",
        "Every demo's persisted graph carries its own snapshot hash, in "
        "`demos/<name>/out/graph/manifest.json`:",
        "",
        manifest_table,
        "",
        "`ablation` has no row above with a hash: its transforms "
        "(`docket.eval.ablation.run_ablations`) run entirely in memory against a copy "
        "of Demonstration B's graph and never call `Graph.save`; the module asserts, on "
        "every run, that the graph it started from is byte-for-bit unchanged afterward "
        "(snapshot hash and log), which is the non-mutation guarantee in place of a "
        "store to hash.",
        "",
        "**Demonstration A is the numeric-path proof.** Its rendered package hashes are "
        "recorded directly in its own results file: full "
        f"`{a_cbo['packages']['full']}`, unclassified "
        f"`{a_cbo['packages']['unclassified']}` "
        "(`demos/a_cbo_gcv_2013/out/results.json`). It carries a sealed evaluation run "
        f"(ready={a_cbo['ready']}, dimensions " + _kv(sorted(a_cbo["dimensions"].items()))
        + ") \u2014 a ranking, simplex weights and a flip analysis all come out of the "
        "solver, not the agent.",
        "",
        "**Demonstration B has no evaluation run.** No `EvaluationRun` is ever sealed on "
        "any OMFV episode in this record: no number is computed, no ranking is "
        "produced, no flip analysis exists (`demos/b_omfv_2019_2023/README.md` \u00a78). "
        "Its snapshot hash above proves the *narrative* record it built is "
        "byte-identical on re-run; it is not evidence that the numeric path works, "
        "and \u00a78 below does not present it as such.",
        "",
        f"The GAO-15-548 control's rendered package: `{control['package']['path']}`, "
        f"sha256 `{control['package']['hash']}`.",
    ])


# ---- section 8: what Phase I proves ----------------------------------------------------

def _section_8() -> str:
    return "\n".join([
        SECTION_HEADINGS[7],
        "",
        "Design \u00a79.6, quoted verbatim:",
        "",
        "> Proves: the schema surfaces the gaps an outside referee found, mechanically, "
        "with a stated agreement rate; the numeric path is reproducible (byte-identical "
        "re-runs in CI); the agent stays out of numbers; refresh produces auditable "
        "diffs; the same representation serves one episode and many.",
        ">",
        "> Does not prove: that the Army's analysis was right or wrong (GAO did not "
        "either); anything about the classified metrics; per-question GAO-23-106549 "
        "labels (inferred); cycle-time or rework effects (that is Phase II's job, on "
        "real cases).",
        "",
        "Two further edges, recorded during this same plan and not in design \u00a79.6 "
        "because they surfaced afterward:",
        "",
        "- **A human, not the agent, names the evaluator when the record does not "
        "resolve one on its own.** `propose_plan` fills `Plan.steps[].evaluator` "
        "automatically only when exactly one `Model` in the episode resolves it without "
        "a rule; on zero or more than one candidate it refuses by name rather than "
        "choosing (`src/docket/agent/plan.py`). There is no mechanism yet for a human "
        "to supply that name directly through the agent layer \u2014 today, resolving "
        "the refusal means editing the record.",
        "- **The append-only log is tamper-evident, not tamper-proof, because it is "
        "unkeyed in Phase I.** The hash chain proves the store is internally "
        "consistent and unchanged against a log head retained elsewhere; it does not "
        "prove authorship, because signing entries \u2014 which would make the chain "
        "evidence of who wrote what \u2014 is not a Phase I claim "
        "(`src/docket/kernel/lifecycle.py`).",
    ])


# ---- assembly ---------------------------------------------------------------------------

def generate_report(root: Path) -> str:
    """The full report text, section by section, in `SECTION_HEADINGS` order."""
    sections = [
        _section_1(root), _section_2(root), _section_3(root), _section_4(root),
        _section_5(root), _section_6(root), _section_7(root), _section_8(),
    ]
    header = (
        "# Phase I validation report\n\n"
        "Generated by `reports/generate.py` from every demo's `out/` JSON "
        "(`demos/run_all.py` writes those; run it first). No numeral below is typed by "
        "hand \u2014 regenerating this file from the same `out/` trees reproduces it "
        "byte for byte (`tests/demos/test_run_all.py`)."
    )
    return header + "\n\n" + "\n\n".join(sections) + "\n"


def write_report(root: Path) -> Path:
    text = generate_report(root)
    out_path = root / "reports" / "phase1-validation.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    return out_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate reports/phase1-validation.md from every demo's out/."
    )
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT,
        help="Root that already holds demos/<name>/out/ (default: repo root, i.e. the "
             "committed layout); the report is written to <root>/reports/.",
    )
    return parser


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv[1:])
    path = write_report(Path(args.out).resolve())
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
