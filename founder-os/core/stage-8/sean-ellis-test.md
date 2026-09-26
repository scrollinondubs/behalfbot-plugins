---
id: sean-ellis-test
type: framework-card
title: The Sean Ellis test: 40% very disappointed
stage: 8
gate: stage-8-traction-and-pmf
tier: core
sources: [running-lean, lean-analytics, sean-ellis-pmf]
---

# The Sean Ellis test: 40% very disappointed

## Purpose

Ask the people who lean on your tool one blunt question, then treat their answers as a gate check. Picture a contract-redlining SaaS with 140 weekly users: at the end you hold a percentage with a date on it, the reply count behind it, and a sharper view of which lawyers depend on you.

## When to use

Run it once people come back without you chasing them. Say you sell a bookkeeping add-on for Shopify merchants, the same accountants open it at every month-end close, and you have not sent a nudge since July. Now you need a number an outsider can check. The question is Sean Ellis's own, and Ash Maurya's Running Lean calls it the Sean Ellis test and uses it to judge product/market fit.

Treat the result as a second opinion on signals you already have from calls and dashboards. If churn is low and customers keep asking for extra seats, the survey should agree, but it will never hand you a roadmap. On a pilot with a dozen accounts, the replies still show you who your fans are, so read them and keep the percentage out of the gate submission.

This is the wrong card if you are still deciding which number to push. Use the sibling card 'One Metric That Matters and the stage you are in' for that.

## Principles

- Restrict the sample to people who completed the core action in the last couple of weeks. Someone who signed up in March and never imported a file has no real feeling to report.
- The share who pick "very disappointed" is the score. Ellis puts the line at about 40%: products above it tend to grow on their own, and products well below it tend to stall.
- Fewer than 30 answers gives you a direction and nothing more. Wait for 100 or more before you rely on the score.
- The very-disappointed group is the prize. Their role, their situation and their words tell you who to build for.
- One reading is a snapshot. The gate wants a number that moves, so plan the second run before you send the first.

## Procedure

1. **Define real usage.** Write one sentence naming the action that proves someone got value. For an invoicing tool, "sent three or more invoices through us" beats "created an account". Next to it, write the score you expect. Show: the definition and your prediction, both dated.
2. **Pull the list.** Export the users who meet that bar and were active in the last two weeks. Remove teammates, friends and anyone you paid to test. Show: the list, its size and the pull date.
3. **Send the survey.** Lead with a single question that has the user imagine losing you, such as "Suppose ClaimDesk shut down tomorrow. How would you feel?" Allow exactly four replies: very disappointed, somewhat disappointed, not disappointed, and "I no longer use it." After that, two or three free-text fields: the tool they'd fall back on, the biggest thing ClaimDesk does for them, and who they think would get the most out of it. Selling B2B? Tone the shutdown scenario down. An operations lead who migrated forty field reps last quarter may take it as a warning and escalate to their account manager. Show: the survey exactly as sent.
4. **Give it two weeks.** Keep the survey open for fourteen days. Under 30 replies, label the result directional and do not submit it to the gate. Show: the response count and the close date.
5. **Score it.** Divide very-disappointed answers by total answers. If lots of people picked "stopped using it", your list was wrong, so go back to step 2. Show: the percentage for each answer.
6. **Segment the must-haves.** Filter to the very-disappointed group. Cut it by role, company size, plan, signup channel and the benefit they named. Look for the cluster that runs well above 40%. Say a clinic scheduling tool scores 24% overall. Among solo physiotherapists who book through the embed widget, it scores 58%, and every one of them mentions ending phone tag. That group is who the product is for. Show: the segment table and one line naming the core user and what they value.
7. **Change something, then re-run.** Act on what that group told you. Aim acquisition at people like them, rebuild the first session around the benefit they named, and drop the feature nobody mentioned. Survey a fresh qualified sample with the same question. Show: a second dated result beside the first, with the change between them named.

## Artifacts produced

- A `pmf_survey` artifact for each run: date, the real-usage definition, number sent, response count, the share for each answer, and the segment table for the very-disappointed group.
- A one-line core-user statement: who the must-have users are and the benefit they name.
- A `pmf_rerun` entry linking two runs and the change made between them.

## Anti-patterns

- **Surveying every signup.** You get a pile of "not disappointed" from people who logged in once. Check whether the list had a usage filter and a recent pull date.
- **Calling it at eleven answers.** A headline percentage with no n beside it. Ask for the count before you accept the score.
- **Stopping at the average.** The founder reports 26% overall and never looks at the must-have group by segment. Ask to see the table.
- **Surveying a waitlist.** Most answers say "stopped using it" or come from people who never started. Go back to activation and retention first.
- **Building for the lukewarm.** The roadmap fills with requests from "somewhat disappointed" users while the must-haves get nothing. Check whose words each planned feature came from.
- **A stale score.** A single run from last quarter is still quoted as current. Look at the date.
- **Scaling on hope.** The founder buys ads or designs growth loops before the score clears the line. That work belongs after fit, not in this card.

## Gate criteria

The `stage-8-traction-and-pmf` gate asks for a PMF score and a metric that moves. From this card it looks for:

- a dated survey result that shows its response count, with 30 or more responses before the score counts
- the very-disappointed share, both overall and in the segment table
- a named core user and the benefit they value
- a second run after a stated change, so the reviewer can see whether the score moved

If you also track the matching retention number, set it up with the sibling card 'A cohort dashboard across AARRR'.

## Sources

- Running Lean, Ash Maurya. This card takes the name Sean Ellis test, its tie to product/market fit, the B2B caution on wording, and the point that surveys confirm rather than discover. Read the original: https://ashmaurya.com/books
- Lean Analytics, Alistair Croll and Benjamin Yoskovitz. This card takes the practice of writing down the score you expect before sending, and asking questions you can later segment by. Read the original: https://leananalyticsbook.com
- Using Product/Market Fit to Drive Sustainable Growth, Sean Ellis (GrowthHackers). This card takes the survey question and its answer set, the 40% line, sampling on recent real usage, the 30 and 100 response thresholds, and studying the must-have group. Read the original: https://medium.com/growthhackers/using-product-market-fit-to-drive-sustainable-growth-58e9124ee8db

## Sean's notes

None yet.
