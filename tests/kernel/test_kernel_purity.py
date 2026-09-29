# tests/kernel/test_kernel_purity.py
import re
from pathlib import Path

FORBIDDEN = [
    r"datetime\.now", r"time\.time\(", r"random\.random\(", r"\bhttpx\b", r"\brequests\b",
    r"\bopenai\b", r"\banthropic\b", r"os\.urandom",
    r"\buuid\b", r"os\.environ", r"\bsubprocess\b", r"\burllib\b", r"\bsocket\b",
    r"\bsecrets\b", r"perf_counter", r"random\.(randint|choice|seed|shuffle)\(",
    r"date\.today\(",
]


def test_kernel_has_no_clock_network_or_llm():
    root = Path(__file__).resolve().parents[2] / "src" / "docket" / "kernel"
    for p in root.rglob("*.py"):
        text = p.read_text()
        for pat in FORBIDDEN:
            assert not re.search(pat, text), f"{p.name} contains forbidden pattern {pat}"
