---
id: stage-0-why
type: gate
title: "Stage 0 gate: a problem you care about, written down"
stage: 0
signoff: claude
fail_routes_to: 0
---

# Stage 0 gate: a problem you care about, written down

> Ruled by Sean on 2026-09-26. The minimums below are in force.

## Required evidence

- One `artifacts` row of kind `why_statement`: the belief sentence plus the what and how lines.
- One `artifacts` row of kind `why_evidence` with at least three dated past actions.
- One `artifacts` row of kind `fit_check`: a problem line and an audience line, each with a verdict. It also holds the objection and the answer.
- One `prfaq_versions` row at version 0, stage 0. Its `body` holds the press release, an external FAQ with five to ten questions, and an internal FAQ.
- The `assumptions` list on that row has at least five items. Each is traced to a PR/FAQ line and tagged uncertain or risky, with risky ones ranked.
- At least one `artifacts` row of kind `lean_canvas`, with Plan A marked in `meta`.
- Exactly one `artifacts` row of kind `riskiest_assumption`.

No `pains` or `interviews` rows are needed at this gate. The verdict goes into `audits`, one row per check, against the rows above.

## Auditor checks

- Every row above exists and meets its minimum count. (Laya can pre-tag this; Claude confirms.)
- Every `why_evidence` item has a date. (Laya can pre-tag this; Claude confirms.)
- Neither `fit_check` verdict says breaks. (Laya can pre-tag this; Claude confirms.)
- Every assumption has a source line and a tag. (Laya can pre-tag this; Claude confirms.)
- The `riskiest_assumption` text matches risky item number one. (Laya can pre-tag this; Claude confirms.)
- The why sentence has no product name, no money and no market size, and it points at one problem. (Claude.)
- The evidence dates come before the idea, and they are about the problem, not the product. (Claude.)
- The release is in customer language, names the customer and the problem, and fits on one page. (Claude.)
- The internal FAQ has at least one real question the founder can't answer yet. (Claude.)
- Every price, time saving or market figure in the release has a matching assumption. (Claude.)
- Each assumption has a who, a number and a threshold, so one result could make it false. (Claude.)
- The number one assumption is ranked by the cost of being wrong, not by how easy it is to test. (Claude.)
- The Plan A problem box matches the problem named in the why and the PR/FAQ. (Claude.)

## Pass/fail rubric

- **Pass:** all evidence is present and every check holds. The decision cites the ids of the five artifact kinds and the `prfaq_versions` row.
- Being wrong is not a fail. Version 0 is supposed to be wrong. Vague and untestable is.
- **Fail:** any row is missing, or a fit verdict says breaks. It also fails if the why names a market or a revenue figure, or if the evidence list starts after the idea did. Assumptions no result could falsify fail. So does a riskiest assumption that's really a build question, and so does a set of canvases with no Plan A marked.
- **Borderline:** three evidence items where one is dated after the idea. Pass only if the other two clearly came first, and note the weak one.
- **Borderline:** five assumptions, but one number in the release has no matching item. Flag it, and pass only if that number isn't the riskiest claim.
- **Borderline:** the only "I don't know" in the internal FAQ is about something trivial. Flag it and ask for one hard question before passing.

## Failure routing

Every failure stays in stage 0.

- Why sentence mentions money or fits any problem: `find-your-why`, steps 2 to 4.
- Evidence thin, undated or retrofitted: `find-your-why`, step 3.
- A fit verdict says breaks: `find-your-why`, step 5.
- Changelog release or founder voice: `prfaq-v0`, step 2.
- Softball internal FAQ: `prfaq-v0`, step 4.
- Hidden or missing assumptions: `prfaq-v0`, step 5.
- Canvas missing, or problem box doesn't match: `plan-a-riskiest-assumption`, step 1.
- Assumptions can't fail: `plan-a-riskiest-assumption`, step 4.
- Assumptions untagged, or ranked by comfort: `plan-a-riskiest-assumption`, steps 5 and 7.
