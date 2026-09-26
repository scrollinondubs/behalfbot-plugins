---
id: stage-4-solution-test
type: gate
title: "Stage 4 gate: tested with customers, reshaped by what they did"
stage: 4
signoff: claude+sean
fail_routes_to: 4
---

# Stage 4 gate: tested with customers, reshaped by what they did

> DRAFT - needs Sean ruling. No founder is held to this gate until Sean signs
> it off. Numeric minimums that need his call: 5 Sprint testers, all stage 3
> earlyvangelists; 10 solution interviews, no more than 3 of them new to the
> ledger; 3 to 6 sprint questions; a finding needs 3 of 5 testers; at least 2
> sketched alternatives; at least 1 feature deleted or backlogged.

## Required evidence

- One `mvp_choice` artifact in `artifacts`. It needs one assumption, one MVP type, numeric pass and fail lines, a deadline and a reshaping list. Its first version must predate the `sprint_plan`.
- One `sprint_plan` artifact with a named Decider and three to six sprint questions. Each question cites an `interviews` id.
- One `sprint_sketches` artifact showing at least two alternatives to the current flow, the winning flow and a keep/change/cut mark for every existing screen.
- One `prototype` artifact with a build link and a reshape log.
- Five `interview_record` artifacts. Each links to an `interviews` row for a person marked `earlyvangelist = 1` in stage 3.
- One `sprint_results` artifact with the board photo, a grid of questions against testers, and a verdict and count for each question.
- Ten `solution_interview` artifacts, each with a matching `interviews` row. Each holds feature tags and the reaction to a price the founder stated.
- One `exit_criteria` artifact. Each of the four criteria cites session ids.
- One `mvp_scope` artifact with the before and after feature lists. Each feature is marked keep, backlog or delete. At least one is deleted or backlogged.
- One `activation_flow` artifact that ends in an outcome event and notes that a fresh account reached it.
- `pains` rows only if a new must-have problem came up. None are required.

## Auditor checks

Each check writes one `audits` row with a `check_name` and `verdict`.

- Every item above exists at its minimum count, and every cited id resolves. (Laya.)
- The `mvp_choice` was created before the first sprint session, and its pass and fail lines did not change after that date. (Laya pre-tags; Claude confirms.)
- All five Sprint testers are stage 3 earlyvangelists. No more than three solution interviewees are new to the ledger. (Laya.)
- The `mvp_choice` question is one yes/no question about what customers do, with no "and". The pass line measures commitment, not signups. (Claude.)
- Every question in the `sprint_plan` has an observable pass or fail, such as a completed upload, never "would they like it". (Claude.)
- Every finding rests on at least three of the five testers. Anything seen once or twice is parked and absent from the reshape log. (Laya pre-tags counts; Claude.)
- Session notes record actions, not opinions, and the founder did not rescue testers. (Claude.)
- Every solution interview logs the founder's figure, not a figure the customer guessed. (Laya pre-tags; Claude.)
- Every kept feature cites a must-have tag. Removed features are gone from the build and the navigation, not moved into settings. (Claude.)
- Results are reported against the `mvp_choice` lines set in advance. (Claude.)

## Pass/fail rubric

- **Pass:** every item is present and every check holds. The decision cites the ids of the `mvp_choice`, `sprint_results`, `prototype`, `exit_criteria` and `mvp_scope` artifacts, and the five tester `interviews` ids.
- **Fail:** the before and after feature lists match, however many interviews were run. Other fails: a tester who is not a stage 3 earlyvangelist, a pass line edited after results came in, no stated price, fewer than five Sprint sessions, or a change made on one or two testers' reactions.
- **Borderline:** only backlogged cuts and no deletions. Pass only if the backlogged features are out of the build the customer sees, and note it in the rationale.
- **Borderline:** a result lands between the pass and fail lines. Hold the gate for the one rerun `choose-the-mvp-type` allows.
- **Borderline:** one of the lesser questions in the `sprint_plan` comes back unclear. Pass if the one tied to the `mvp_choice` assumption got a clear yes or no.

Sean rules on every borderline.

## Failure routing

- `mvp_choice` missing, written late or testing two assumptions: stay in stage 4. Redo `choose-the-mvp-type`, steps 1, 2 and 5, then rerun `sprint-test-your-app` from step 7.
- App reused as-is or the reshape log is empty: `sprint-test-your-app`, steps 5 and 6, then retest at step 7.
- Wrong testers, fewer than five sessions or rescued sessions: `sprint-test-your-app`, step 7.
- Findings from one or two testers: `sprint-test-your-app`, step 8.
- No stated price or too few solution interviews: `solution-interview-reduce-mvp`, steps 3 and 4.
- Exit criteria unmet: `solution-interview-reduce-mvp`, step 5.
- Same feature list, unsupported keeps or hidden features: `solution-interview-reduce-mvp`, step 6.
- Activation stops before the outcome: `solution-interview-reduce-mvp`, step 7.
- Fewer than five earlyvangelists exist in stage 3: flag this to Sean, who decides whether to reopen stage 3.
