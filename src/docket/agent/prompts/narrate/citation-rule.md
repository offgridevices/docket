# Narrative citation rule (design §7.8, §8.7; kernel `check_citations`)

You are drafting prose for one section of a Decision Package. Every sentence you write
must name, in its own `cites` list, at least one object id from the context you were
given — never an id you were not shown, and never no id at all.

Every number that appears in your sentence text — a score, a threshold, a distance, a
weight, a count — must be copied character-for-character from a value already sitting
inside one of that sentence's cited objects. Do not compute a new number, do not round
one, do not convert its units, and do not average, sum or otherwise combine two numbers
into a third. If the arithmetic you want to state is not already sitting in the context
as a single stored value, you may not state it.

If the context does not give you enough to support a sentence you wanted to write, leave
that sentence out rather than filling the gap with an inference, a plausible-sounding
estimate, or a number from outside the context. A shorter narrative that survives the
renderer's citation check is worth more than a longer one that does not.

The renderer — not you — decides whether a draft passes. `check_citations` rejects any
sentence with no citation, any citation that does not resolve, and any number in the
sentence that does not match a number already present in a cited object. A rejected
draft is returned to you with the exact sentence and the exact reason; rewrite only what
was rejected, using only the ids and values you were already given.
