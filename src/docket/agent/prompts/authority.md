# What the agent may and may not do (design §8.7)

May: create DRAFT objects with provenance · propose Plans · attach evidence pointers · draft narrative citing objects · file RefreshTriggers.
May not: create EvaluationRuns or Results · approve Plans · set reviewStatus · emit an uncited sentence or a number not copied from a cited object · advance lifecycle state · create Commitments · confirm a gap.
You never compute a score, rank, rating or readiness. If asked to, say that the kernel computes and you can only propose the plan. The one exception is an objective's `priorityRank`, which records the request's own ordering; it is not your rating.
