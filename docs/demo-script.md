# Demo script

What to click and what to say, for the two demos the frontend design spec's §7
choreography defines. Nine minutes and a closing question: Demo A is seven, Demo B is
two, and the last twenty seconds put a question to the chat.

Read this once before the room fills. The timings are targets, not a metronome — the
beats are what matter, and beat 4 (the gate refusing) is the one worth being slow about.

**No provider or model name is spoken anywhere in this script, or shown on any screen it
visits.** That is a product property, not stagecraft: every screen the script opens keeps
provider and model strings out, and the two surfaces that do carry them — the Settings
slide-over and the raw-object drawer — are only opened if something breaks.

**Where the controls are.** The header carries the decision switcher (`Which decision`),
the episode chip, `Explain`, `Browse the record`, `Ask about this decision` and
`open settings`. Under it, a status row: `needs you`, `blocking`, the time chip, and the
chip saying where the answers come from. Down the left, the progress map — `What needs
you`, then `Request`, `Model`, `Plan`, `Compute`, `Readiness`, `Package`, then the
registers `Evidence`, `Timeline`, `Activity` — and that map is the navigation. "Map →
**Model**" below means clicking that row. The chat sits on the right and the footer, with
`Coverage — every control and every requirement`, is always in view. The page itself
never scrolls; each column scrolls inside itself.

---

## Pre-flight

Run through this before the audience arrives. The last two are **human-only** — nothing
in the repository can check them for you.

| # | Check | How |
|---|---|---|
| 1 | The app starts and seeds itself | `make demo` — builds the bundle if it is missing, then opens the browser already inside a Demo A session, on **What needs you** |
| 2 | The mode chip in the status row reads `recorded` (or `live` with a filled dot) | Right-hand end of the status row. Either is a pass. `API absent` is not — the server did not come up |
| 3 | Both demo stores are present | `demos/a_cbo_gcv_2013/out/graph` and `demos/b_omfv_2019_2023/out/graph` both exist. The switcher lists a store it cannot find as `— not built` |
| 4 | The switcher offers `Demo A · CBO GCV 2013`, `Demo B · OMFV 2019–2023` and `New session` | If not, stop — nothing downstream will work. With no decision open at all, **What needs you** shows the same three as start cards |
| 5 | Walk beats 1–4 once, then close the tab | Every session is a private copy; a rehearsal costs nothing and leaves nothing behind |
| 6 | **Browser at 100 % zoom** — *human-only* | `Cmd`/`Ctrl` + `0`. Zoomed in, the frame folds to its narrow layout: the map becomes a strip along the top and the chat becomes a bottom sheet. Nothing is lost, but the shape you rehearsed is |
| 7 | **Projector resolution confirmed** — *human-only* | Mirror, do not extend. Confirm the readiness grid's four rows of nine cells are legible from the back row before you start |

If the room has no network at all, nothing above changes. Recorded mode is the default
and needs none.

---

## Demo A — a 2013 ground-vehicle trade study, 7 minutes, 8 beats

(Beat 5 splits into a live half and a hand-over half; eight beats, nine rows.)

Beats 2–5 run **live**, in front of the audience, in a fresh empty session, on an episode
that does not exist until you press `Elicit`. The live loop, exactly and only, is:
**request in → draft objects out → the gate-one board → approve → the weights a human
types.** Beats 5b–8 run on **Demo A's own episode**, `ep-cbo-2013`, the one the store
ships with, which is already computed, scored and packaged and is waiting for a
signature.

> **Say this once, at beat 5b, and do not skip it.** *"From here on I am on the episode
> this demo ships with, not the one we just built. In Phase I nothing lets a human name
> the evaluator for a brand-new question, and the kernel refuses to pick one on a human's
> behalf — so the plan, the computation and the package are shown on a record that already
> has one."* That sentence is the honest boundary of the live loop; a reviewer who spots
> the switch and is not told is a reviewer you have lost.

One thing the browser deliberately cannot do today, and the script turns it into a beat
rather than hiding it: **the plan cannot be proposed** for a live episode, for the
evaluator reason above. The refusal is the product working, and it is said out loud.
Gate one, by contrast, now goes all the way through on a live episode: the charter's empty
field is typed into on the model board, and the gate passes. It refuses first, for a
reason it names, and that refusal is beat 4.

| # | Time | Screen | Click path | Say |
|---|---|---|---|---|
| 1 | 0:00 – 0:30 | What needs you | You are already in a Demo A session. Point at the status row: `needs you`, `blocking`, the time chip. Point at the map down the left, then at the footer | "This is the whole product's shape. Down the left, where this decision stands. Along the top, what is waiting on a person and what is stopping it — both read out of the record, not out of a to-do list. Bottom of every screen: all data here is public, and this is a demonstration, not an authorisation system. Watch the counters as I work." |
| 2 | 0:30 – 1:30 | File the request | Switcher → **New session**. Map → **Request**. Step 1: click `Load the recorded request`, then `Next`. Step 2: type `NGCV CFT` into *who asked for this*; the policy arrives with the request; leave the deadline empty. `Next`. Step 3: the source is already chosen — click `Elicit` and watch the stages | "This is a real request for a real trade study. The AI reads it and proposes a structure — a charter, objectives, alternatives, constraints, assumptions — and every card that lands is dashed and blue, because that means *the AI said so, nobody has agreed yet*. Each one carries the paragraph it came from. Nothing here is a number." |
| 3 | 1:30 – 2:45 | Every object in the model | Click `Go to the model checklist`. On the board, open the assumption marked as one the answer depends on — `Read it` | "This is the whole product in one card. Six regions, same order, every time: what it says, why the AI proposed it, the source, what happens if it is wrong, what you can do, and — before you click anything — what your click will do to the record. The AI proposed a threshold. Nobody has agreed to it. If it is wrong, the vehicle is too heavy to cross the bridges it has to cross." Close the card. "And here" — point at a card under *What the source never says* — "is what the AI did *not* find. A recorded absence is content. Silence is not allowed." |
| 4 | 2:45 – 3:30 | Every object in the model | Scroll the view column to the gate-one checklist. Press `Approve the model` **with an absence still unconfirmed**. Read the refusal. Press the remedy on the first unmet check — `Confirm the recorded absence` — which opens **Read and agree** at that object; press `Confirm gap`. Map → **Model**. Open the linchpin assumption again and press `Accept`. In the charter block, type into the empty field (*what happens if this is wrong*) and press `Save the charter`. The approve button turns Ember — press `Approve the model` again | "Refused — and it names the check: `gaps-confirmed`. Not a warning, not a toast: the refusal is now part of the record, with my name on the attempt. I confirm the absence. Now the charter: three fields, one per AR 5-11 paragraph, and one of them is empty — this document never states what happens if the output is wrong, so the AI recorded an absence instead of guessing. I write the answer myself, in my own words, and save. I agree the assumption too. And approve again: this time nothing is missing, the button has gone Ember, and the queue behind me has drained as I went. `MODEL_APPROVED`, my name on the transition, and I did every bit of it by clicking." |
| 5 | 3:30 – 4:00 | The plan | Map → **Plan**. Type a weight per objective, press `Save weights`. Then press `Ask the AI to propose a plan` and read what comes back | "Weights are a value judgement, so a human types them — the browser does no arithmetic and the AI is not asked. That is the last thing a person authors before the kernel takes over. And when I ask for a plan: it refuses, and it says why — it cannot choose an evaluator, and it will not pick between models on a human's behalf." |
| 5b | 4:00 – 4:15 | The plan | Say the boundary sentence above, then switcher → `Demo A · CBO GCV 2013`. Map → **Plan** | *(the boundary sentence)* "On this record the plan already exists: steps that each cite the doctrine paragraph authorising them, approved by a named human. `Approve the plan` and `Pass gate 2` are the two buttons that got it here, and they are spent — the gate is behind this record, and the checklist is now read-only." |
| 6 | 4:15 – 5:30 | Compute | Map → **Compute** | "First numbers in the whole demo — and they are in survey brackets, which is the rule: a numeral is only rendered inside brackets, and only the kernel puts one there. Sealed runs with their hashes. The ranking. And this" — point — "is what the topic asks for: what would change the answer, shortest flip distance first. The top two parameters are under two points of weight away from changing which vehicle wins, and the second of them is bound to an assumption a human accepted: that carrying a full nine-member squad in one vehicle is what matters. Underneath, the weight simplex: the fraction of all possible weightings in which each option comes first. `Run the plan` is the one act on this view, and it is not offered here because this plan has already been run." |
| 7 | 5:30 – 6:30 | Readiness | Map → **Readiness**. The score button reads `Score it again`, because `rr-ep-cbo-2013-1` already exists — do not press it | "Thirty-six questions from the published research standard; twenty-one apply to this study, and the fifteen that do not are struck out with a written reason — an unreasoned exclusion is itself a finding. Three dimension verdicts, computed from the cells by a stated rule, printed under the grid. The rating scale is cited on screen, not in a tooltip. Under *What blocks sign-off*: anything stopping it would be listed there in red, each row naming the rule it broke and offering to take you to the object. Here it says *nothing blocks sign-off*, which is why the signature is on offer at all — and the warnings beside it are still printed, because a warning is not nothing. Look up at the header while you are here: `blocking` reads zero, and it agrees with this page. The signature gate does want two things this record has not got — a commitment, and a commitment bound to the package — but both of them *are* the signature, and an act is not counted as an obstruction to itself." |
| 8 | 6:30 – 7:00 | The package | Map → **Package**. Press `Render the package`. Toggle `unclassified` / `full`. Press `Verify the bytes`, then `Download the text`. Point at the six exports. Then either press `Sign` and fill the sheet, or press `Send back for rework`, type a reason, and go back to **What needs you** to watch the card appear | "Sixteen sections, two renderings — one you can carry out of the room, one you cannot. Render the same record again and you get *identical bytes*. Every sentence in it cites the object it came from; the renderer refuses an uncited one. And this is the last human act: I either sign — and the signature binds by hash to exactly this text — or I send it back with a named reason, which files a trigger against the episode, puts a card at the top of the queue, and deletes nothing." |

**If it breaks — Demo A**

| Symptom | What it means | What to do, out loud |
|---|---|---|
| The mode chip reads `API absent` | The server is not up | Stop and restart with `make demo`. Nothing else recovers this |
| The mode chip reads `recorded` when you expected live | No model endpoint answered the health check | *"The backend went away and the app said so, in the header, and carried on. That is the design — the fallback is labelled, never silent."* Keep going; every beat is identical |
| `Elicit` fails at beat 2 | The recording does not answer this exact request | Go back to step 1, press `Load the recorded request` again (it fills the request and the policy together), retype who asked, and press `Elicit` again. If it still fails, skip to beat 5b and run the rest on `ep-cbo-2013` |
| A refusal at beat 4 or 5 does **not** appear | Something let the call through that should not have | Do not improvise a story. Say *"that should have refused"*, move to beat 5b, and write it down afterwards — an unexpected pass at a gate is a defect, not a lucky break |
| The switcher shows a demo as `— not built` | That demo's store is missing from disk | Quit, run `make demo` again — it seeds what is missing on boot |
| A view shows an error card | The route it names failed | The card prints the route; press `retry` on it. If it stays red, open any id chip — the raw-object drawer reads the record directly and still shows it |
| A number looks wrong | It is not this app's number | *"Nothing on this screen was computed by the browser or by a model. Every numeral was written by the kernel and is reproducible from the store."* Then move on |

---

## Demo B — the same programme over four years, 2 minutes and a closing question, 6 beats

(Beats 1–5 are the two minutes; beat 6 is the twenty-second question put to the chat.)

Demo B is not a second product demo. It is the argument that the record survives time.

| # | Time | Screen | Click path | Say |
|---|---|---|---|---|
| 1 | 0:00 – 0:25 | The programme | Switcher → `Demo B · OMFV 2019–2023`. Map → **Timeline** | "One programme, `prg-omfv`, five episodes, four years. Each box is a decision episode with the date it was as-of, the state it ended in, and how long it lived; the connectors carry the months between them. Four of the five are superseded — superseded, not deleted." |
| 2 | 0:25 – 1:00 | The programme | Click the **second** episode box | "Between these two, something outside the record changed, and the trigger that filed it is on the line between them. Here is the diff the kernel computed: what changed, what stayed consistent, and — this line — which of them changed a *judgement* rather than a number." |
| 3 | 1:00 – 1:20 | The programme | Click the **third** episode box | "This pair is different: nothing was replaced and no pairing was attempted, so the panel says *field-level pairing unavailable for this diff* in those words rather than showing a blank. A tool that guessed here would be lying quietly." |
| 4 | 1:20 – 1:45 | The programme | Point at the red line under the last box. Point at *filed, opened nothing* — `rt-sigmgmt-correction` carries the Ember `Open refresh` because it has waited longest, and `rt-gao-grading` sits under it. Press `Ask the AI what changed`. Scroll to the 3×3 verdict grid | "Red, under the last episode: months since the last one, against the re-accreditation clock the same server keeps. Two triggers are filed and have opened nothing, and the one lit is the one that has waited longest — the screen says why in words rather than leaving you to read a colour. `Ask the AI what changed` detects; it does not record. Recording a trigger is a write, and opening a refresh is a human act at gate four. And this grid is what the last episode's sub-episodes score to: three sections, three dimensions, nine verdicts. The grid is ours; the report states those same nine verdicts in prose. The caption underneath is ours too, and it is a limit, not a boast: that report gives nine verdicts in prose, not a grid and not per-question labels, and the referee did not assess or verify the underlying analytical work." |
| 5 | 1:45 – 2:00 | Readiness | Map → **Readiness** | "Scored under this programme's own tailoring, and the tailoring's honesty note prints beside the grid — from the record, not retyped by the screen. Four years of a real requirements decision, reconstructed from public documents, and the record can still tell you what changed and what it changed." |
| 6 | 2:00 – 2:20 | Ask about this decision | Header → `Ask about this decision`. Click the chip *What is blocking this right now?*; click one of the citations in the answer to open the stored object, and close it. Then click the chip *Why is it late?* | "It reads this decision and never writes to it — that sentence is at the top of the panel, and it is structural, not a promise: there is no write path in the route at all. Every answer cites the objects it was drawn from, and a citation opens the object itself, so you never have to take the assistant's word for anything. Ask it why this is late and you get the clock: which stage the time went into, and how long it has been since a person last did anything." |

Not clicked, and not claimed: the counterfactual repair is a separate store on disk, not a
screen. Mention it only if asked, and say so.

**If it breaks — Demo B**

| Symptom | What to do |
|---|---|
| The programme view says the session has no programme | You are on a Demo A or a new session. Switcher → `Demo B · OMFV 2019–2023` |
| No diff panel appears on a click | That pair has no computed diff. Click a different box; the view already says "click an episode to see what changed" |
| The 3×3 grid is absent | It is discovered from the record, not fetched from a dedicated route, and it renders only when discovery succeeds. Skip that half of beat 4; the rest stands alone |
| The chat answers with "I can only answer from this decision's record" | No intent matched what was typed. Use the suggested chips, which are the questions the server names |

---

## The two sentences to fall back on

If a beat collapses and you need a bridge, either of these is true on every screen:

- *"The UI computes nothing. Every number it shows was written by the kernel and is
  reproducible from the store."*
- *"The gate sits on the model of the question, not on the answer. Catching a wrong
  question is cheap."*
