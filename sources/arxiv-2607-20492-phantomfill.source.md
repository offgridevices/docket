# arXiv:2607.20492 — "PhantomFill: When the Form Demands an Answer, Language Models Invent One"

**Sidecar-only. No file is committed here** — this is the abstract-page stub the
code and docs cite; the preprint itself stays out of `sources/` because it is an author
preprint rather than a US Government work, and the one sentence relied on is quoted
in full below.

| | |
|---|---|
| Title | PhantomFill: When the Form Demands an Answer, Language Models Invent One |
| Author | Rana Muhammad Usman (Independent Researcher) |
| Identifier | arXiv:2607.20492v2 [cs.LG], 27 July 2026 |
| Abstract page | https://arxiv.org/abs/2607.20492 |
| PDF | https://arxiv.org/pdf/2607.20492v2 |
| Release status | **Public.** Author preprint, publicly posted on arXiv and openly readable at the abstract page above. Not a US Government work; not redistributed here, which is why this entry is a stub. |
| Retrieved | 2026-09-02 (read in the local research library); stub written 2026-09-07 |

The finding relied on, quoted verbatim from the abstract page:

> "We show that the form itself causes hallucination. … Required fields drive
> fabrication to 100% in ten of thirteen models. An explicit 'insufficient evidence'
> option rescues only the frontier: all nine open-weight models ignore it."

The paper's own remedy is "one line of schema"; docket's is stronger — absence is a
typed object a human must sign, not an optional enum value — and the paper is cited
as the statement of the risk, not as evidence that docket's mitigation works.

No model or provider named in the paper is repeated in this repository.

Used by: `src/docket/agent/prompts/gap-discipline.md` and the `InsufficientEvidence`
object in `src/docket/schema/objects.yaml` (the risk that required fields drive
fabrication); `docs/design/phase1-design.md` §4 P2, §6.1.
