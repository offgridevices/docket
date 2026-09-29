"""FastAPI service wrapping `docket.kernel` and `docket.agent` for the demo UI.

One process, no subprocesses: the routes here import the kernel and the agent layer
directly, so a `TransitionRefused` or an `AuthorityViolation` arrives as a typed Python
exception, never as parsed subprocess stderr. State lives where it already lives — the
append-only `Graph` — and a browser session is always a *copy* of a demo store, never
the committed fixture itself.
"""
