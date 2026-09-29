# Documentation

Read `../README.md` first: it says what Docket is, what it runs on, and how to run it.
This folder holds the deeper material, in four places and no more.

| Where | What it is | Read it when |
|---|---|---|
| `architecture.md` | Why the repository is laid out the way it is, what each folder and each Python module does, and where to look when something misbehaves. | You need to debug or change something. |
| `design/` | The design documents the build followed: the system design (principles, architecture, schema, kernel, agent layer, validation method, output — cited in code as `design §N.M`) and the demo frontend design. | You want to know why a mechanism exists, not just what it does. |
| `decisions/` | One file per technical decision, dated, with what would reverse it. | You are about to change a rule, a threshold or a scoring choice. |
| `research/` | Our own analysis of the public record: the GAO teardown and the human-AI guidance mapping. | You are checking a claim the software or its docs make. |

One more document lives here because it is read by people, not by code:
`demo-script.md` (what to say and click when showing the demonstrations).

Rules for adding to this folder: a new decision is a new dated file under `decisions/`;
everything else goes into an existing file. Deep technical explanations belong in
`architecture.md` or in the design documents, never in the top-level README.
