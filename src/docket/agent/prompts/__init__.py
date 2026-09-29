"""Doctrinal definitions used verbatim as annotation guidelines (GoLLIE, design §8.1).

Data only: Markdown files on disk, read once and cached. Nothing here touches the network,
and nothing here names a provider or a model. `PARTS` is the order the guidelines are
substituted; the order they appear to the model is set by `elicitation-system.md`.
"""

from functools import cache
from pathlib import Path

__all__ = ["HERE", "PARTS", "load_prompt", "system_prompt"]

HERE = Path(__file__).parent

#: The embedded parts, in substitution order. `object-typing` names the catalogue fields and
#: the two slot markers; the other five are the doctrinal guidelines.
PARTS = [
    "authority",
    "ar-5-11-problem-statement",
    "grca-typing",
    "icd-203-assumptions",
    "gap-discipline",
    "object-typing",
]


@cache
def load_prompt(name: str) -> str:
    return (HERE / f"{name}.md").read_text(encoding="utf-8").strip()


def system_prompt() -> str:
    text = load_prompt("elicitation-system")
    for p in PARTS:
        text = text.replace("{" + p + "}", load_prompt(p))
    return text
