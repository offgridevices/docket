"""The prompt package is data: pure, importable offline, and honest about its sources."""

import re
from pathlib import Path

from docket.agent.prompts import HERE, PARTS, load_prompt, system_prompt

# The catalogue types stage E elicits. Every one of them must have a guideline.
ELICITED_TYPES = (
    "Charter",
    "Objective",
    "Alternative",
    "GroundRule",
    "Constraint",
    "Assumption",
    "Evidence",
    "InsufficientEvidence",
)

ALL_FILES = tuple(sorted(p.name for p in HERE.glob("*.md")))

# A citation is a named document plus a locator. Both are required in every guideline.
CITED_DOCUMENT = re.compile(
    r"AR 5-11|OAS AoA Handbook|ICD 203|CBA Guide|GAO-\d|MIL-STD-3022|DoDI \d"
    r"|ARM26BX06|objects\.yaml|design §"
)
LOCATOR = re.compile(r"printed pp?\.|\bpp?\. ?\d|§|¶")

# A literal shaped like a value someone could paste into a numeric field. Case matters:
# citations ("¶4-5b", "§4.9", "printed p. 45", "GAO-20-283G") deliberately do not match.
VALUE_SHAPED = re.compile(
    r"\$\s*\d"
    r"|\b\d+(?:[.,]\d+)?\s*(?:%|M\b|B\b|K\b)"
    r"|\b\d+(?:[.,]\d+)?\s*(?:km|kg|mm|tons?|miles?|hours?|dollars|percent)\b"
    r"|\bFY\s?\d{2,4}\b"
)
NON_VALUE_MARKER = "not a value"

# No prompt may name a provider, a hosted service or a model family. Model-agnostic is a
# design commitment, and the PRC-origin families are excluded by policy on top of it.
FORBIDDEN_NAMES = re.compile(
    r"\b(openai|anthropic|claude|chatgpt|gpt-?\d|azure|bedrock|vertex ai|openrouter|ollama"
    r"|llama|mistral|mixtral|gemini|palm 2|cohere|grok|deepseek|qwen|qwq|kimi|moonshot"
    r"|chatglm|zhipu|baichuan|minimax|hunyuan|ernie|doubao|internlm|internvl|minicpm"
    r"|skywork|xverse|telechat|stepfun|sparkdesk|longcat|pangu|sensechat)\b",
    re.IGNORECASE,
)


def _guidelines() -> dict[str, str]:
    return {name: load_prompt(name) for name in PARTS}


# --- the brief's tests -------------------------------------------------------------


def test_prompts_present_and_embedded():
    s = system_prompt()
    for p in PARTS:
        assert load_prompt(p) and load_prompt(p) in s
    assert "{" not in s.split("AR 5-11")[0]
    assert "Consequences resulting from erroneous M&S outputs" in s


def test_no_placeholder_survives_substitution():
    s = system_prompt()
    for p in PARTS:
        assert "{" + p + "}" not in s


def test_grca_placeholder_was_actually_replaced():
    """The plan shipped an executor note in grca-typing.md. It must be gone."""
    t = load_prompt("grca-typing")
    assert "[Executor:" not in t and "<Handbook's verbatim sentence>" not in t
    assert "printed p. 45" in t


def test_lexicon_bands_match_the_catalogue():
    from docket.schema import catalogue

    bands = catalogue()["lexicon_bands"]
    text = load_prompt("icd-203-assumptions").lower()
    for b in bands:
        assert b.replace("-", " ") in text, b


def test_authority_prompt_states_the_five_capabilities_and_the_refusals():
    a = load_prompt("authority")
    for phrase in (
        "EvaluationRuns",
        "approve Plans",
        "reviewStatus",
        "uncited sentence",
        "lifecycle state",
        "Commitments",
        "confirm a gap",
    ):
        assert phrase in a


# --- the prompt package is data ----------------------------------------------------


def test_every_part_has_a_file_and_the_file_set_is_exactly_what_is_used():
    on_disk = {p.stem for p in HERE.glob("*.md")}
    assert on_disk == set(PARTS) | {"elicitation-system"}, sorted(on_disk)


def test_load_prompt_is_pure_and_cached():
    first = load_prompt("authority")
    assert load_prompt("authority") is first  # lru_cache, not a re-read
    assert first == first.strip() and first


def test_system_prompt_is_deterministic():
    assert system_prompt() == system_prompt()


# --- every elicited type has a guideline, and it names the catalogue's own fields ----


def test_every_elicited_catalogue_type_has_a_guideline():
    s = system_prompt()
    for t in ELICITED_TYPES:
        assert t in s, f"no guideline mentions {t}"


def _type_blocks() -> dict[str, str]:
    """`object-typing.md` split on its `##` headings, keyed by the heading line."""
    blocks: dict[str, str] = {}
    heading = ""
    for line in load_prompt("object-typing").splitlines():
        if line.startswith("## "):
            heading = line[3:]
            blocks[heading] = ""
        elif heading:
            blocks[heading] += line + "\n"
    return blocks


def test_every_elicited_type_block_says_what_you_fill_and_what_is_not_yours():
    """[review M7] A block must not decay into prose: both halves stay explicit."""
    covered: set[str] = set()
    for heading, body in _type_blocks().items():
        named = {t for t in ELICITED_TYPES if re.search(rf"\b{t}\b", heading)}
        if not named:
            continue
        assert "You fill:" in body, f"{heading!r} never says what the model fills"
        assert "Not yours:" in body, f"{heading!r} never says what is not the model's"
        covered |= named
    assert covered == set(ELICITED_TYPES), sorted(set(ELICITED_TYPES) - covered)


def test_the_two_slot_markers_are_named_and_only_the_gap_marker_is_the_agents():
    o = load_prompt("object-typing")
    assert '{"$gap": id}' in o and '{"$exclusion": id}' in o
    assert "this marker is never\nyours" in o or "this marker is never yours" in " ".join(
        o.split()
    )


def test_the_model_is_told_it_may_never_write_a_number_the_kernel_or_a_human_owns():
    o = load_prompt("object-typing")
    for owner in (
        "Observation.value",
        "WeightSet.weights",
        "Measure.criteria.threshold",
        "Result",
    ):
        assert owner in o, owner
    assert "never emit a number" in o


def test_evidence_is_presented_as_our_addition_not_as_compliance():
    flat = " ".join(load_prompt("object-typing").split())
    assert "our addition" in flat.lower()
    assert "objectives, options, constraints, assumptions, risks, and bias checks" in flat
    assert "Evidence is not on it." in flat
    assert "contribution and not as a compliance item" in flat


# --- honesty rules -----------------------------------------------------------------


def test_every_guideline_cites_a_source_document_and_a_locator():
    for name, text in _guidelines().items():
        assert CITED_DOCUMENT.search(text), f"{name}.md names no source document"
        assert LOCATOR.search(text), f"{name}.md gives no section, paragraph or page"


def test_no_guideline_carries_an_unmarked_value_shaped_literal():
    """[orchestrator rule] No digit-bearing example a model could paste into a number."""
    for name in ALL_FILES:
        for n, line in enumerate((HERE / name).read_text(encoding="utf-8").splitlines(), 1):
            hit = VALUE_SHAPED.search(line)
            if hit:
                assert NON_VALUE_MARKER in line, f"{name}:{n} {hit.group(0)!r} unmarked"


def test_every_illustration_is_marked_as_a_non_value():
    for name in ALL_FILES:
        for n, line in enumerate((HERE / name).read_text(encoding="utf-8").splitlines(), 1):
            if "Illustration" in line:
                assert NON_VALUE_MARKER in line, f"{name}:{n} illustration not marked"


def test_no_prompt_names_a_provider_a_service_or_a_model_family():
    for name in ALL_FILES + ("__init__.py",):
        text = (HERE / name).read_text(encoding="utf-8")
        hit = FORBIDDEN_NAMES.search(text)
        assert hit is None, f"{name} names {hit.group(0)!r}; prompts are model-agnostic"


def test_the_prompt_package_reaches_no_network_and_holds_no_secret():
    src = (HERE / "__init__.py").read_text(encoding="utf-8")
    for token in ("http", "requests", "httpx", "socket", "os.environ", "getenv", "api_key"):
        assert token not in src, token


def test_no_prompt_file_quotes_a_library_path_or_a_non_public_source():
    """`library/` is gitignored and never enters the repository (CLAUDE.md)."""
    for name in ALL_FILES + ("__init__.py",):
        text = (HERE / name).read_text(encoding="utf-8")
        assert "library/" not in text, f"{name} points at the local research library"


def test_buyer_naming_never_says_department_of_defense_outside_a_document_title():
    for name in ALL_FILES:
        text = (HERE / name).read_text(encoding="utf-8")
        assert "Department of Defense" not in text, name


def test_prompt_files_live_under_the_package_directory():
    """Under `src/docket/`, so hatchling's `packages = ["src/docket"]` ships them."""
    assert HERE == Path(__file__).resolve().parents[2] / "src" / "docket" / "agent" / "prompts"


# --- the "(slot)" annotations are the catalogue's, not the author's -----------------

#: `` `some.path` (slot) `` — the annotation this file's prompts use.
SLOT_ANNOTATION = re.compile(r"`([A-Za-z][A-Za-z0-9.\[\]]*)`\s*\(slot\)")


def _properties(node: dict) -> dict | None:
    """The sub-field map of a catalogue node, through an array's `items` if there is one."""
    if "properties" in node:
        return node["properties"]
    items = node.get("items")
    return _properties(items) if isinstance(items, dict) else None


def _field_spec(type_name: str, path: str, types: dict) -> dict | None:
    node: dict = {"properties": types[type_name]["fields"]}
    for segment in path.split("."):
        props = _properties(node)
        name = segment.removesuffix("[]")
        if not props or name not in props:
            return None
        node = props[name]
    return node


def test_every_slot_annotation_names_a_field_the_catalogue_marks_slot_true():
    """[review I2] The one file whose purpose is schema fidelity must not misplace a slot."""
    from docket.schema import catalogue

    types = catalogue()["types"]
    checked = 0
    for name in ALL_FILES:
        candidates: list[str] = []
        for n, line in enumerate((HERE / name).read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("## "):
                candidates = [t for t in types if re.search(rf"\b{t}\b", line)]
            for path in SLOT_ANNOTATION.findall(line):
                assert candidates, f"{name}:{n} annotates `{path}` (slot) under no known type"
                specs = [_field_spec(t, path, types) for t in candidates]
                hit = [s for s in specs if isinstance(s, dict) and s.get("slot") is True]
                assert hit, (
                    f"{name}:{n} marks `{path}` (slot), but no field of "
                    f"{candidates} with that path is `slot: true` in the catalogue"
                )
                checked += 1
    # Round 2 cut the per-type catalogue rosters, so the surviving annotations are the four
    # that carry information the "You fill" lines do not: Charter's
    # `consequencesOfErroneousOutput`, an Assumption's `evidence`, and Evidence's two
    # whole-object slots `pointer` and `scopeOfValidity`.
    assert checked >= 4, f"only {checked} slot annotations found; the parser is not working"


#: The prompt has to be *followed*, not just fit. A small local model loses instruction
#: adherence well before this; the ceiling exists so the file cannot creep back up.
MAX_WORDS = 2400


def test_the_system_prompt_stays_short_enough_to_be_followed():
    words = len(system_prompt().split())
    assert words <= MAX_WORDS, f"{words} words; the ceiling is {MAX_WORDS}"
