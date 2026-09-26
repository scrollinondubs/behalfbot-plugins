---
id: stage-5-position-and-story
type: gate
title: "Stage 5 gate: one job, one foothold, one rewritten launch"
stage: 5
signoff: claude+sean
fail_routes_to: 5
---

# Stage 5 gate: one job, one foothold, one rewritten launch

> DRAFT - needs Sean ruling. No founder is held to this gate until Sean signs
> it off. Numeric minimums that need his call: 5 `pains` rows behind the job;
> 1 stage 4 test result; 2 incumbents in the table; 3 rows placing the segment
> on its fork; 5 interviews in the foothold segment; 3 to 5 `not_for` entries;
> 2 or 3 expansion markets; 1 dead assumption in the diff; 1 internal FAQ
> answer still assumed; 10 segment members the founder can name.

## Required evidence

- One `artifacts` row, kind `job_statement`, linking to at least 5 `pains` rows that share its `job` and to at least 1 stage 4 test result.
- One `artifacts` row, kind `foothold`, naming the fork (low-end or new-market), the current fixes and an incumbent table with at least 2 rows. It must cite at least 3 `pains` or `interviews` rows from that segment that place it on the fork.
- At least 5 `interviews` rows whose `segment` matches the foothold.
- One `artifacts` row, kind `not_for`, with 3 to 5 entries, each with a reason.
- One `artifacts` row, kind `market_sizing`, with a headcount and its source, at least 1 channel, a competitor table and a target share.
- One `artifacts` row, kind `expansion_sequence`, with 2 or 3 ordered adjacent markets and a durability line.
- Two `prfaq_versions` rows: version 0 from stage 0, unchanged, and version 2 from stage 5.
- One `artifacts` row, kind `prfaq_diff`, listing at least 1 assumption that died.

## Auditor checks

The auditor writes one `audits` row per check, with `check_name` and `verdict`.

- Every artifact above exists and meets its count. (Laya pre-tags.)
- Every customer quote in v2 resolves to an `interviews` row id. (Laya pre-tags.)
- v0 predates v2 and its body has not changed since stage 0. (Laya pre-tags.)
- Every internal FAQ answer carries a status: confirmed, still assumed or dropped. (Laya pre-tags.)
- The headcount has a source URL or named list. (Laya pre-tags; Claude confirms the source counts people.)
- The job sentence opens with a circumstance and names the progress wanted. It is not a demographic or a feature. (Claude.)
- The cited `pains` rows and the stage 4 result back this job over the other clusters. (Claude.)
- The cited rows really place the segment on the chosen fork. Nonconsumers are struggling or patching together workarounds, not shrugging. (Claude.)
- No incumbent in the table would defend the segment, and the reasons hold up. (Claude.)
- `not_for` turns away at least one customer the founder would have been tempted to serve. (Claude.)
- Each expansion step is the same buyer with a new job or the same job for a neighbouring buyer. (Claude.)
- The v2 headline and opener use the job sentence and name the foothold. Market claims use the counted group and pass both size-lie checks. (Claude.)
- Every external FAQ question traces to an objection in `interviews` notes or test results. (Claude.)
- At least one internal FAQ answer is still assumed. (Claude.)

## Pass/fail rubric

- **Pass:** all evidence is present and every check is `pass`. The decision cites the ids of every artifact, both `prfaq_versions` rows and the `interviews` rows behind the fork.
- **Fail:** any artifact is missing or below its count, any quote has no interview row, v0 was overwritten, the diff has no dead assumption, or a market claim starts from a top-down dollar figure.
- **Borderline:** one incumbent could plausibly defend the segment. Pass only if the table shows why that incumbent's margins or contract sizes make defending it unlikely. Put the risk in the rationale.
- **Borderline:** the headcount comes from one directory that may be incomplete. Pass if the founder can name ten members, and flag the count for Sean.

## Failure routing

- Job is demographic, feature-shaped or untraced: stay in stage 5 and redo `job-and-foothold`, step 1.
- The stage 4 tests backed no cluster clearly: back to stage 4 to run another test, starting from `choose-the-mvp-type`.
- Fork unsupported or an incumbent would defend: stage 5, `job-and-foothold`, steps 3 and 4.
- `not_for` costs nothing: stage 5, `job-and-foothold`, step 6.
- No headcount, a fake intersection, or scattered reach: stage 5, `small-market-first`, steps 1, 2 and 5.
- Expansion jumps straight to everyone: stage 5, `small-market-first`, step 6.
- Ghost quotes, a wish-list FAQ or everything marked confirmed: stage 5, `prfaq-v2`, steps 3 to 5.
- v0 overwritten or diff missing: stage 5, `prfaq-v2`, steps 6 and 7. Recover v0 from the stage 0 record before rewriting the diff.
