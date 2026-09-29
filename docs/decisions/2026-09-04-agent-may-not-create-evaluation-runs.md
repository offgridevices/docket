# 2026-09-04 — the agent may not create evaluation runs

**Chosen:** the LLM layer may create DRAFT objects, propose plans, attach
evidence pointers, draft cited narrative and file refresh triggers. It may not
create EvaluationRuns, Results, ratings, Commitments, or lifecycle transitions.
The object store enforces this and a test proves it.

**Over:** the incumbent's boundary (DDT schema §5.4), which lets agents create
Evaluation Runs but not Commitments.

**Why.** Reproducible evaluation runs are a topic requirement. Deterministic LLM
inference exists only when the serving stack is controlled down to the kernel;
a model-agnostic product calling a hosted endpoint cannot verify that. Keeping
the agent out of the numeric path makes reproducibility architectural rather
than promised, and the boundary is a single checkable line.

**Would reverse if:** the product commits to a self-hosted, pinned inference
stack with a verified determinism guarantee — at which point agent-created runs
could be sealed with the same hash discipline as kernel runs.
