# Work in a worktree; every change lands through a pull request

Date: 2026-09-08. Status: settled by Shreyash, 2026-09-08.

**Chosen:** branch in a git worktree and land every change through a pull request
against `main`. Nothing is committed to `main` directly and nothing is pushed to it.

**Over:** the previous rule — work directly on `main`, no PRs, no worktrees — which was
recorded in the repository's working guidance from 2026-09-02 and matched how a sibling
project runs.

**Why.** The Phase I build ran unattended for days at a time with agents committing on
their own. On `main` that gives no one a place to stand: there is no reviewable unit
between "an agent committed something" and "it is in the trunk", and no way to reject a
line of work without rewriting history. A worktree plus a PR gives three things the old
rule could not — an isolated tree that cannot disturb `main`, a single reviewable diff
with a written rationale, and a gate that a human passes deliberately rather than by
default. The automated review on the first PR immediately earned its cost by finding a
real sourcing gap in the research standard, which is the kind of defect that survives a
direct-to-`main` commit indefinitely.

**Would reverse if:** the PR overhead starts costing more than it returns on a
single-author repository — for instance if reviews stop finding anything over a long
run of PRs, or if the review turnaround delays time-critical submission work near a
deadline. In that case the fallback is not "commit to `main`" but "smaller, more
frequent PRs".

**Consequences recorded elsewhere.** `CONTRIBUTING.md` ("Branches, commits and pull requests") carries the rule for outside
readers. Whether any specific branch merges to `main` remains a separate, human call
each time — an open item about one specific branch is about that branch, not about the
working rule, and stays open.
