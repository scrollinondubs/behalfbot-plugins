---
id: stage-7-validation-and-sales
type: gate
title: "Stage 7 gate: money changed hands, or a pilot was signed"
stage: 7
signoff: claude+sean
fail_routes_to: 7
---

# Stage 7 gate: money changed hands, or a pilot was signed

> Ruled by Sean on 2026-09-26. The minimums below are in force.

## Required evidence

- At least two `commitment` artifacts from two different buyers. Each one needs attached proof of money or a signature: a paid invoice, a deposit receipt, a Stripe customer record with a card on file, or a signed pilot agreement that states a price.
- One `offer_log` artifact with at least 10 priced asks. Each commitment must match one of its rows.
- One `outreach_log` artifact covering at least 30 prospects. Every touch is dated and every prospect has an outcome, including the nos.
- One `deal_log` artifact with a row for each prospect the founder worked, showing the dates of first contact and the outcome.
- `sales_roadmap` artifacts at version 1 or later, each with a changelog.
- One `pivot_or_proceed` artifact containing a dated pass bar, the score against it and the decision.
- At least one committed buyer who matches an `interviews` row with `earlyvangelist = 1`.

## Auditor checks

- Each commitment has a proof file attached. (Laya pre-tags; Claude confirms the proof shows money or a signature, not an LOI, a waitlist signup or a free pilot with no end date.)
- Each commitment names a prospect with a row in `offer_log`, and that row states a price. (Laya.)
- The price in each commitment is at least the offered price, or the discount follows a logged objection. (Claude.)
- Each commitment traces back to `outreach_log` rows for the same prospect, dated before the commitment. (Laya.)
- The outreach log has no blank outcomes, includes nos and includes calls as well as email. (Laya.)
- The touches were made by the founder, not by an agency, a rep or a hire. (Claude reads the log and the deal notes.)
- The latest roadmap version shows the steps the deal log actually shows, with blockers and stall points. (Claude.)
- The pass bar is dated before the first outcome date in `deal_log`. (Laya pre-tags the date comparison; Claude confirms the decision follows from the score.)
- The log has no "loved it", "keep me posted" or unpriced yeses counted as wins. (Claude.)

Each check writes one `audits` row with `target_table`, `target_id`, `check_name` and a verdict.

## Pass/fail rubric

- **Pass:** at least two proven money commitments, every check holds, and the decision is proceed, or a pivot on price or pitch only. The ruling cites the id of each commitment, offer row, outreach row and roadmap version, plus the pivot-or-proceed record.
- **Fail:** no proven money commitment. A proceed decision with no paid or signed deals also fails, as does a commitment that traces to no priced offer or no outreach, a pass bar with no date or dated after the deals, or selling done by someone other than the founder.
- **Borderline:** only one commitment. Pass only if the priced asks have a clear hit rate and Sean signs off. Note it in the rationale.
- **Borderline:** a card on file whose first charge falls after the trial. It counts if the trial has an end date, but flag it for recheck at that date.
- **Borderline:** the `pivot_or_proceed` record switches to a different kind of customer. The payments on file then came from people the founder no longer targets, so this is a fail, and the new customer type starts its own round.

## Failure routing

- No priced asks, or asks with no price stated: stage 7, `ask-for-money`, steps 1 to 4.
- Warm calls with no commitment or dated next step: stage 7, `ask-for-money`, steps 4 to 6.
- Commitments that trace to no outreach, or a log with blanks or no nos: stage 7, `founder-led-outbound`, steps 5 and 7.
- Selling done by a hire or an agency: stage 7, `founder-led-outbound`. The founder reruns steps 3 to 6 personally.
- Roadmap still at v0 or not matching the deal log: stage 7, `customer-validation-roadmap`, step 6.
- Pass bar missing, undated or set after the results: stage 7, `customer-validation-roadmap`, step 7. Set a new bar and score it against a fresh round of deals. Old deals cannot be rescored.
- New customer type, or the stage 3 shortlist would not pay: return to stage 3 and redo the list with `earlyvangelists-and-commitment`.
