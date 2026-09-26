---
id: stage-2-pain-research
type: gate
title: "Stage 2 gate: pains in their words, grouped into jobs"
stage: 2
signoff: claude
fail_routes_to: 2
evidence: [artifacts/problem_hypothesis>=1, artifacts/safari_session>=3, pains>=30, pains:audited>=30, artifacts/saturation_check>=3, artifacts/jobs>=1]
---

# Stage 2 gate: pains in their words, grouped into jobs

> Ruled by Sean on 2026-09-26. The minimums below are in force.

## Required evidence

- `artifacts` kind `problem_hypothesis`: 1 row. It holds the sentence, the kill line, a status and every dated earlier version.
- `artifacts` kind `safari_session`: at least 3 rows, each for a different watering hole from the stage 1 kept list.
- `pains`: at least 30 rows from at least 3 watering holes. This floor comes from the stopping rule: at least 5 people behind the passing job, then a final 10 entries that add nothing new. Change one of those inputs and the floor moves with it.
- `artifacts` kind `saturation_check`: one row for every 10 `pains` rows. The last one is the stopping note.
- `artifacts` kind `jobs`: 1 row, with at least 1 job that meets the stopping rule.
- `interviews`: 0 required. Stage 3 owns interviews.
- `prfaq_versions`: 0 required.
- `audits`: 1 Laya pre-tag row for each `pains` row, plus Claude verdict rows on the `jobs` and `problem_hypothesis` artifacts.

## Auditor checks

- Every `pains` row has a non-empty `quote`, a `source_url` and a post date in `tags`. (Laya.)
- Each `source_url` is a permalink to the post itself, not to the channel. (Laya pre-tags, Claude confirms.)
- Every `pains.watering_hole` appears in the stage 1 kept watering-holes list. (Laya.)
- On a sample of 10 `pains` rows, the quote turns up by search at its source, word for word. (Claude.)
- Every `pains.tags` holds the author handle, the words/worldview/buys fields or "none seen", and one of `supports`, `contradicts` or `surprise`. (Laya checks presence. Claude checks whether "none seen" is plausible.)
- Every `pains.job` holds a job id or `unclustered`. (Laya.)
- Each passing job has at least 5 distinct author handles from at least 2 watering holes. (Laya counts. Claude checks whether handles in different places belong to the same person.)
- Each job sentence names a situation and the progress wanted, with no product or feature in it. (Claude.)
- Each job lists functional, social and emotional sides, each with quote ids or marked as a guess. (Laya checks presence, Claude checks fit.)
- Each job's current hires include doing nothing or doing it by hand. (Claude.)
- The earliest `problem_hypothesis` version is dated before the median `pains` post date. (Laya.)
- The kill line could actually be met. Revisions are dated. An invalidated hypothesis links the rows that sank it. (Claude.)
- The final 10 `pains` rows contain the `surprise` count stated in the stopping note. (Laya.) They add no new job and no new twist. (Claude.)
- No `interviews` row is dated inside stage 2, and no `source_url` points to a poll or thread the founder posted. (Laya flags, Claude rules.)

## Pass/fail rubric

- **Pass:** every count is met and every check holds. The decision cites the ids of the `jobs`, `problem_hypothesis` and final `saturation_check` artifacts, plus the `audits` rows behind each check.
- **Fail:** any artifact is missing. Or quotes are paraphrased or unlinked, no job meets the stopping rule, or the hypothesis postdates the log.
- **Borderline:** one job meets the stopping rule and the others do not. Pass on that one job, park the rest, and name them in the rationale.
- **Borderline:** a cluster has 3 or more quotes but fewer than 5 people. It satisfies the clustering card but not this gate. It does not count as passing.
- **Borderline:** the verbatim sample finds 1 miss in 10. Draw 10 more rows. Any further miss is a fail.

## Failure routing

- Paraphrased, unlinked or undated quotes: stage 2, `sales-safari-pain-log` steps 4 and 6.
- Too few watering holes or authors, or one loud voice: stage 2, `sales-safari-pain-log` step 7.
- Words, worldview and buys missing: stage 2, `sales-safari-pain-log` step 5.
- Empty `pains.job` or persona-shaped clusters: stage 2, `cluster-pains-into-jobs` steps 2 and 7.
- Missing sides or quote ids: stage 2, `cluster-pains-into-jobs` step 4.
- No doing-nothing hire: stage 2, `cluster-pains-into-jobs` step 5.
- Feature-shaped or vague job sentence: stage 2, `cluster-pains-into-jobs` step 6.
- Hypothesis missing, has no kill line, or was written after the log: stage 2, `problem-hypothesis-heard-enough` steps 1 and 2. Then read one more batch of 10 against it before resubmitting.
- Stopping rule unmet: stage 2, `problem-hypothesis-heard-enough` steps 4 and 5.
- Hypothesis invalidated with no rewrite, or rewritten without marking the old one wrong: stage 2, `problem-hypothesis-heard-enough` step 7.
- Log shows the audience was the wrong group: back to stage 1, as `problem-hypothesis-heard-enough` step 7 directs.
