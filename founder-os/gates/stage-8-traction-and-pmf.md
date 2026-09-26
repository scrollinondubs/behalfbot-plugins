---
id: stage-8-traction-and-pmf
type: gate
title: "Stage 8 gate: fit you can measure, a number that moves"
stage: 8
signoff: claude+sean
fail_routes_to: 8
---

# Stage 8 gate: fit you can measure, a number that moves

> DRAFT - needs Sean ruling. No founder is held to this gate until Sean signs
> it off. Numeric minimums that need his call: 2 Sean Ellis survey runs of 30
> or more responses each, with 100 or more before a score is more than
> directional; whether the 40% very-disappointed line is required to pass or
> only advises; users active within 14 days of the survey; 4 weekly OMTM
> points; 4 cohort rows; 1 logged change followed by movement; 3 flat weeks
> with no change counted as a fail.

## Required evidence

- At least two `pmf_survey` artifacts, each dated, with the real-usage definition, the predicted score, the pull date, number sent, a response count of 30 or more, the share for all four answers and a very-disappointed segment table. `meta` holds a one-line core-user statement.
- One `pmf_rerun` artifact linking two `pmf_survey` runs and naming the change made between them.
- One `omtm` artifact with the stage and its evidence, the business model line, the metric definition (numerator, denominator, window) and a dated line in the sand with both decisions attached.
- One `metric_series` artifact with at least four weekly points, each carrying a note on what shipped.
- Any `omtm_change` artifacts, each with a written reason. Zero is fine if the metric and target never moved.
- One `aarrr_event_map` artifact with five steps, each tied to one product event.
- One `cohort_table` artifact with at least four weekly join-week rows and the leakiest step named and dated.
- One `change_log` artifact with at least one entry giving a ship date and the first cohort it touched.

## Auditor checks

Each check writes an `audits` row with `check_name` and `verdict`.

- Each `pmf_survey` has n of 30 or more, a pull date within 14 days of sending, and a close date. (Laya)
- The two survey runs are dated apart and `pmf_rerun` points at both. (Laya)
- The `omtm` line-in-sand date is earlier than the first `metric_series` point. (Laya)
- `metric_series` has four or more weekly points and `cohort_table` has four or more rows. Immature cells are blank, not estimated. (Laya)
- The definition in `omtm` matches the one in `metric_series` meta. (Laya pre-tags, Claude confirms.)
- The survey sample is active users who hit the core action, not signups or a waitlist. A large "no longer use it" share is a flag. (Claude)
- Event map steps are real product events, not page views or logins. (Claude)
- The OMTM is a rate, not a total that only climbs. (Claude)
- Movement in the metric follows a named `change_log` or `omtm_change` entry and holds in later rows, not a one-week spike. (Claude)
- No target was lowered without a reason on record. (Claude)

## Pass/fail rubric

- **Pass:** every piece of evidence is present, every check passes, and the metric moved across several weeks after a named change. Claude recommends a ruling on the PMF score and Sean makes it. The decision cites every artifact id and `audits` row it relies on.
- **Fail:** a missing artifact, any survey under 30 responses, a line in the sand dated after the data, a cumulative metric, or no movement tied to a logged change.
- **Borderline, 30 to 99 responses:** the score is directional. Claude notes it and Sean decides whether it counts.
- **Borderline, under 40% overall with a segment well above it:** passes only if the core-user statement names that segment and the rerun targeted it. Sean rules.
- **Borderline, metric moved but stayed under the line:** passes if the series and `omtm_change` show an honest record and what came next. If it has been flat for three weeks or more with nothing changed, fail.

## Failure routing

Every failure stays in stage 8.

- Sample is signups, a waitlist or stale: `sean-ellis-test`, step 2.
- Too few responses: `sean-ellis-test`, step 4.
- No segment table or core user: `sean-ellis-test`, step 6.
- No second run or no named change: `sean-ellis-test`, step 7.
- Metric is a total or loosely defined: `one-metric-that-matters`, step 3.
- Line drawn after the data: `one-metric-that-matters`, step 4, with a new line and a fresh series.
- Fewer than four weekly points: `one-metric-that-matters`, step 5.
- Target quietly lowered: `one-metric-that-matters`, step 6.
- Events are page views or logins: `cohort-dashboard-aarrr`, step 1.
- Fewer than four cohort rows: `cohort-dashboard-aarrr`, step 3.
- Movement not tied to a logged change: `cohort-dashboard-aarrr`, step 5.
