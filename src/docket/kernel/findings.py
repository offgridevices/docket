from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, order=True)
class Finding:
    rule: str
    severity: str  # blocking | warning | info
    objects: tuple[str, ...]
    message: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["objects"] = list(self.objects)
        return d
