---
id: stage-9-fundraise
type: gate
title: "Stage 9 gate: raise only if the numbers already say so"
stage: 9
signoff: claude+sean
fail_routes_to: 8
---

# Stage 9 gate: raise only if the numbers already say so

> DRAFT - needs Sean ruling. No founder is held to this gate until Sean signs
> it off. Numeric minimums that need his call: 3 paying customers in the
> ledger; 8 weekly readings of one metric; 2 funded plans beside the
> zero-dollar plan; 8 to 12 angels on the shortlist; 3 warm routes; 1 sent
> investor update.

This stage is optional. Revenue first is the default, and a founder who
decides "not yet" has finished FounderOS. The gate only asks for pitch and
investor work from founders whose stage 7 and 8 numbers justify a raise.

## Required evidence

Every founder:

- At least one `audits` row with `verdict pass` from `claude` or `sean` for the stage 7 gate, and at least one for the stage 8 gate.
- At least 3 `interviews` rows with `commitment money`. These are the paying customers the traction rests on.
- One `traction_snapshot` artifact with paying customers, MRR and eight weekly readings of one metric.
- One `growth_constraint` artifact containing the constraint sentence, marked yes or no for "cash buys this".
- One `raise_plans` artifact with one zero-dollar plan and two funded plans. Each funded plan has a milestone and a date.
- One `raise_decision` artifact saying "raise" or "not yet", with a written reason.

Only if `raise_decision` says raise:

- An amount and an instrument recorded in `raise_decision`, tied to a milestone from `raise_plans`.
- One `elevator_pitch` artifact and one `executive_summary` artifact, with a ledger id beside every number.
- One `angel_shortlist` artifact with 8 to 12 names. Each name has a fit note, a cheque range and a syndicate flag.
- One `middleman_list` artifact naming at least 3 warm routes.
- At least 1 `investor_update` artifact with a send date in its log.

## Auditor checks

- Stage 7 and 8 pass rows exist in `audits`. (Laya pre-tags.)
- Every required artifact is present and meets its count. (Laya pre-tags.)
- Each ledger id in the pitch and summary points to a real row. (Laya pre-tags.)
- Each cited number matches the value in the row it points to. (Claude.)
- The snapshot metric moved over the eight weeks. It was not flat. (Claude.)
- Cash can buy the constraint, and the funded plans don't show signups rising while retention stays flat. (Claude.)
- The zero-dollar plan passes the survival check, which makes this a type A raise. (Claude.)
- The raise amount follows from the cost math of one funded plan. (Claude.)
- The pitch and summary run traction, then team, then social proof, and the product gets one short paragraph. (Claude.)
- Each fit note names a relevant deal or buyer, not "invests in startups". (Claude.)

## Pass/fail rubric

- **Pass, not yet:** stage 7 and 8 audit rows are present, all four decision artifacts exist, and the reason follows from `raise_plans`. The founder has finished FounderOS and needs no pitch or list. The decision cites the audit row ids and the four artifact ids.
- **Pass, raise:** everything above, plus every raise-branch item with all checks holding. The decision cites each artifact id and every number it checked.
- **Fail:** a stage 7 or 8 pass row is missing. For a raise decision, also a flat metric, a constraint money can't buy, a type B plan, or any pitch number with no ledger row or a mismatched value. Any of those on a founder who wanted to raise can still end as "not yet", which passes.
- **Borderline:** a shortlist of 7 or 13 passes only if every fit note is specific, and the rationale says so. A "not yet" with a one-line reason passes if that line points at a figure in `raise_plans`. With no reason written, it fails.

## Failure routing

- Stage 7 or 8 gate not passed, fewer than 3 paying interviews, or a flat metric: back to stage 8 to grow the numbers.
- Raise decided but money can't buy the constraint: stay in stage 9, redo `should-you-raise`, step 2, and expect the answer to become "not yet".
- A funded plan has no milestone, or the amount doesn't match the cost math: `should-you-raise`, step 4.
- A type B raise or an unreasoned decision: `should-you-raise`, step 5.
- An unsourced or mismatched number: `pitch-traction-team-social-proof`, steps 1 and 4.
- Wrong order or a product-first summary: `pitch-traction-team-social-proof`, step 5.
- Fewer than 3 warm routes: `pitch-traction-team-social-proof`, step 7.
- Shortlist out of range or vague fit notes: `what-angels-screen-for`, step 5.
- No sent update: `what-angels-screen-for`, steps 7 and 8.
