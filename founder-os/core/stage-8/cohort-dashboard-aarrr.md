---
id: cohort-dashboard-aarrr
type: framework-card
title: A cohort dashboard across AARRR
stage: 8
gate: stage-8-traction-and-pmf
tier: core
sources: [running-lean, lean-analytics]
---

# A cohort dashboard across AARRR

## Purpose

Find the one place where users drop out of your product, and see whether this week's fix made a difference. You end up with a small table you update every Monday that names the leakiest step.

## When to use

Use this card at stage 8, once real users are signing up without you inviting each one by hand. You need at least a few dozen signups a week, or every weekly row turns into noise.

Wrong card if you have no product in users' hands yet. Also wrong if you already have a table and are stuck on which number to chase. That belongs to the sibling card 'One Metric That Matters and the stage you are in'.

## Principles

- AARRR is Dave McClure's pirate metrics: acquisition, activation, retention, revenue, referral.
- On a shift-swap app for restaurant managers, the five checkpoints might be: signs up, publishes a first rota, still publishing in week four, pays to add a second site, sends the link to a friend at another restaurant.
- A step only counts if it is one event you can point to in the product, with a user id and a timestamp.
- Group users by the week they joined. A total across all users blends last month's product with this week's, so you can't tell which one you're measuring.
- Ash Maurya's Running Lean calls this a cohort conversion dashboard.
- Say a setup wizard ships on Thursday and the same week a partner agency moves its clients onto your tool. If the wizard caused the rise, every row from Thursday on keeps it. If the agency did, one row spikes and the next falls back. You can only tell with weekly rows and a dated ship log.
- A small table gets read every week. A big one gets opened once and forgotten.

## Procedure

1. **Map each step to one event.** Write one line per AARRR step naming the event that proves it happened. Here is an example for an invoice-approval tool sold to small finance teams:
   - Acquisition: creates an account.
   - Activation: first invoice is approved by a second person on the team.
   - Retention: approves at least one invoice in week 4 after joining.
   - Revenue: starts a paid plan.
   - Referral: a user invites someone from a different company.

   What you can show: a five-line event map.

2. **Check that the events fire.** Sign up as a new user and walk through every step. Then confirm each event landed with your user id and the right date. What you can show: one test user whose five events appear with timestamps.

3. **Fill in the table below.** Signups are a count. Every cell after that is a percentage of the cell to its left. A launch-day crowd of tyre-kickers dents that row's Activated number and nothing further right.

   | Join week | Signups | Activated | Retained wk 4 | Paid | Referred |
   |---|---|---|---|---|---|
   | W31 | 52 | 33% | 41% | 18% | 4% |
   | W32 | 47 | 36% | 39% | 21% | 2% |
   | W33 | 61 | 54% | 44% | 19% | 3% |
   | W34 | 58 | 51% | - | - | - |

   Recent cohorts have blanks because not enough time has passed. Leave them blank. Don't estimate. What you can show: the table with at least four weekly rows.

4. **Name the leakiest step.** Pick the step with the lowest rate that stays low across several cohorts. A single bad week doesn't count. In the table above, retention and paid conversion both sit well under half. Retention comes first, because a customer who pays but never comes back is a cancellation waiting to happen. What you can show: one sentence naming the step and the rows that support it.

5. **Log every change against a week.** Keep a dated list of what shipped: a new onboarding email, CSV import of the vendor list, a pricing page rewrite. In the example, vendor import shipped in W33, and that's the week activation jumped from the mid-30s to above 50%. What you can show: a change log where each entry points to the cohort that first saw it.

6. **Read it every Monday.** Add the new row, fill in older cells as they mature, and write one line on what moved and what didn't. If nothing has moved for three weeks, what you're shipping isn't working. What you can show: dated weekly notes next to the table.

## Artifacts produced

- An `aarrr_event_map` artifact: the five steps, each with its event name and definition.
- A `cohort_table` artifact: weekly rows, step-to-step rates, and the leakiest step named with the date.
- A `change_log` artifact: each product change with its ship date and the first cohort it touched.

## Anti-patterns

- **Page views as acquisition.** The acquisition number climbs every month no matter what you ship. Replace it with an event that means a person committed to something.
- **Login as retention.** People who open the app and leave without doing the core job still count as retained. Define retention as repeating the job itself, like approving an invoice or closing a booking.
- **The all-time funnel.** A single funnel with no join weeks. You can't tell whether last Tuesday's release helped, because every user since launch is mixed together.
- **Forty columns.** Every event you track has its own column and nobody reads past the fifth. Cut back to one per AARRR step. Drill into sub-steps only when you're investigating a specific leak.
- **Shipping without a log.** Activation jumps and no one can say what changed that week. Write the entry on the day you ship.
- **Chasing referral first.** Invite features built while week-4 retention sits at 20%. Fix the step where people are leaving before adding ways to bring more people in.

## Gate criteria

The `stage-8-traction-and-pmf` gate asks for a PMF score and a metric that moves. This card supplies the metric that moves. The auditor wants a cohort table with at least four weekly rows, an event map behind every column, the leakiest step named, and at least one logged change followed by a visible shift in later cohorts. The PMF score comes from the sibling card 'The Sean Ellis test: 40% very disappointed'.

## Sources

- Running Lean, Ash Maurya. This card takes the weekly cohort conversion dashboard from it: measuring each step against the one before, and tying product changes to the cohorts that saw them. Read the original: https://ashmaurya.com/books
- Lean Analytics, Alistair Croll and Benjamin Yoskovitz. This card takes the case for cohort analysis over blended averages, and their account of Dave McClure's pirate metrics. Read the original: https://leananalyticsbook.com

## Sean's notes

None yet.
