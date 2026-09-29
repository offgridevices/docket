# 2026-09-04 — the kernel is a Python library over a JSON object graph

**Chosen:** Python ≥3.12, uv-managed; objects as JSON documents validated by
JSON Schema (Draft 2020-12) generated from one YAML catalogue; a directory of
JSON files plus an append-only log as the store; content hashes over canonical
JSON; exports (PROV, GSN, DMN, MIL-STD-3022, MADR, RTVM) derived from the same
graph.

**Over:** a graph database, a typed ORM, or a TypeScript service.

**Why.** No database means a reviewer can read the record with `cat`. JSON
Schema is an open standard the rubric's "Enabling Technologies" criterion
rewards. Python is what the SME reviewers and the Army analytic community use.
Canonical-JSON hashing gives byte-identical reproducibility without a runtime.

**Would reverse if:** Phase II enterprise scale needs concurrent multi-user
writes — at which point the store gets a database backend behind the same
`Graph` interface.

**Supersedes:** the earlier note that deferred Python scaffolding until the schema
settled; the schema is settled enough (design §6) to scaffold now.
