---
id: one-metric-that-matters
type: framework-card
title: One Metric That Matters and the stage you are in
stage: 8
gate: stage-8-traction-and-pmf
tier: core
sources: [lean-analytics]
---

# One Metric That Matters and the stage you are in

## Purpose

Choose one number that shows each week whether the product is getting better at the thing you are betting on. Write down beforehand what result counts as good, so the number is allowed to tell you no.

## When to use

Use it at stage 8, once real users touch the product often enough to produce weekly data. A few dozen active accounts or a handful of paying customers is enough to start.

It is the wrong card if nobody is using the product yet. Go back and get usage first. It is also the wrong card for asking users how they would feel if the product disappeared. That is the sibling card 'The Sean Ellis test: 40% very disappointed'. For retention tables by signup week, use 'A cohort dashboard across AARRR'.

## Principles

- Alistair Croll and Benjamin Yoskovitz call this the One Metric That Matters. It is a single number the whole team watches, because a team can't steer by twenty.
- Lean Analytics names five stages: empathy, stickiness, virality, revenue, scale.
- The right number depends on where you are. On a meal-prep ordering tool where most caterers disappear after uploading one menu, the only question that matters is whether they come back. Average order value can wait.
- Commit to a target before the data arrives. Croll and Yoskovitz call this a line in the sand. Set in advance, it stops you from reading the result however suits you afterwards.
- A rate beats a total. Totals only climb. A ratio can fall, and that is what makes it useful.
- If a change in the number would not change next week's work, it belongs with what Croll and Yoskovitz call vanity metrics.

## Procedure

1. **Place yourself, with evidence.** Use data you already hold. A shift-swap app has 40 restaurants signed up, staff at only nine posted a swap in month two, and three pay. The founder wants to talk about the three. The data says people don't come back, which is stickiness. Show: "We are in [stage] because [evidence]."

2. **Write down how cash reaches you,** in one line, then open the matching chapter of Lean Analytics for its shortlist of numbers. A product that charges two ways gets two lines. Show: the line, the shortlist, your current values.

3. **Pick the one metric.** Look where stage and model meet, and pick the number most closely tied to the risk that could kill you now. Some examples:
   - A SaaS tool for freelance bookkeepers, in stickiness: the share of workspaces that reconcile at least one bank feed each week.
   - A marketplace that matches agencies with contract designers: the share of posted briefs that get a qualified proposal within 48 hours.
   - A B2B approval workflow, in early revenue: the months it takes to earn back the cost of winning a team account.

   Show: the metric's exact definition (numerator, denominator, time window) and the query or tool that produces it.

4. **Draw the line in the sand.** Set the bar while you still can't see the answer. Write down the threshold, the date you'll judge it and the move you'll make on either side. A founder with a client-portal tool might write: "By 3 November, 40% of new teams share a portal with a client in their first week. If we hit it, we start charging. If we miss, the Zapier integration waits and we fix setup." Use the book's typical ranges as a starting point and tune them to your niche. Show: the dated target and the two decisions attached to it.

5. **Record it weekly.** Use the same definition on the same weekday, with one row per week. Next to each number, note what shipped that week. Show: a weekly series with at least four points.

6. **Replace it when it stops deciding.** Once the metric has held above the line for several weeks and no longer changes what you work on, you have answered that stage's question. Pick the next stage's metric and draw a new line. You can adjust a target if you write down why. Quietly lowering it so the chart looks healthy is cheating. Show: a changelog entry with the old metric, the new metric and the reason for the switch.

## Artifacts produced

- An `omtm` artifact: the stage and its evidence, the business model, the metric definition, and the line in the sand with its date and attached decisions.
- A `metric_series` artifact: weekly values, each with a note on what shipped.
- An `omtm_change` entry each time the metric is replaced or its target moves.

## Anti-patterns

- **The climbing total.** Cumulative signups, lifetime GMV, all invoices ever sent. Spot it: the chart has never dipped. Divide by active accounts or by time.
- **The Monday wall of numbers.** The founder reviews a dozen figures every week and changes nothing. Spot it: nobody can name the number that would stop a feature.
- **The line drawn afterwards.** The target appears once the data is in, set just below the result. Spot it: the target is dated after the first data point.
- **The stage skipper.** Tracking referral invites while half of new users never come back a second time. Spot it: the metric belongs to a later stage than your evidence supports.
- **The retired-in-place metric.** The same OMTM for six months, sitting comfortably above its line. Spot it: it hasn't triggered a decision in weeks.
- **The quiet redefinition.** "Active" slides from weekly to monthly with no note. Spot it: the definition in the ledger no longer matches the query.

## Gate criteria

The `stage-8-traction-and-pmf` gate asks for a PMF score and a metric that moves. From this card it looks for:

- A written OMTM naming the stage, the business model and the exact definition, with a line in the sand dated before the series starts.
- A weekly series of at least four points that shows movement linked to named changes. If the metric didn't move, the founder shows an honest record of that and what they did next.

The PMF score itself comes from the Sean Ellis card.

## Sources

- Lean Analytics, Alistair Croll and Benjamin Yoskovitz. This card takes from it the One Metric That Matters, the five stages, the line in the sand and the split between vanity metrics and metrics you can act on. Read the original: https://leananalyticsbook.com

## Sean's notes

None yet.
