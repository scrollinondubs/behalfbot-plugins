---
id: solution-interview-reduce-mvp
type: framework-card
title: The solution interview and cutting the MVP to what was proven
stage: 4
gate: stage-4-solution-test
tier: core
sources: [running-lean, running-lean-1st-ed]
---

# The solution interview and cutting the MVP to what was proven

## Purpose

Most vibecoded apps ship with more features than any customer asked for. Picture a shift-scheduling tool with a chat tab, a payroll export, a calendar sync and a swap inbox, when the restaurant managers you spoke to only worry about Friday call-outs. Ash Maurya's solution interview, from Running Lean, puts working screens and a real price in front of the people who confirmed the problem, and records which parts they want to keep.

Whatever they insist on keeping becomes your minimum viable product, Maurya's name for the least you can ship and still solve the problem you promised to solve. The card ends with an activation flow: the path a brand-new account follows until that problem is solved for the first time.

## When to use

Use it at stage 4, once the problem interviews have given you people who ranked your problems and described how they cope today. This is the card for the founder with a vibecoded app that has more screens than anyone asked for.

It is the wrong card if nobody has confirmed the problem yet. Go back to the stage 3 card, 'The problem interview and its exit criteria'. If you have not decided what form your MVP takes, open 'Choose the MVP type that tests your riskiest assumption' first.

## Principles

- Show something concrete. People explain problems well and picture solutions badly, so give them screens to react to.
- Test against their ranking. Every screen you show answers a problem the person already put near the top.
- Name the price. Ask what someone would pay and you get a low guess. Say a number and you learn whether it holds.
- Features start out. Nothing from the current build is kept by default.
- The first session delivers the promise. Activation is the route from signup to the moment the top problem gets solved.

## Procedure

1. **Book the people who already ranked the problem.** Filter your stage 3 rows down to the managers who put Friday call-outs at number one. Text each a slot for this week. Then add two or three kitchen managers you have never met, maybe from a local hospitality WhatsApp group. They owe you nothing, so they will tell you when a screen bores them. Show: 10 to 15 booked sessions, each linked to an interview id.
2. **Build the demo around their top problems.** Pick the screens that answer their highest-ranked problems and cut a path through only those, either live in the build or as a two-minute recording. Seed it with data from their world. A restaurant manager should see a Friday rota with three call-outs and a swap request waiting, not "User 1" and lorem ipsum. If a screen shows something the code can't do and you have no plan to build, take it out. Show: the demo, with each screen labelled by the problem it answers.
3. **Run the solution interview.** Open by reading their own ranking back to them and checking it has held: "In March, Sunday brunch cover was top of your list. Has anything moved?" Then go through the screens one at a time. On each, ask them to replay a real shift from the past fortnight using it. Tag each feature within the hour, based on what they did rather than what they said. Leaning in, asking when they can have it, or grabbing the trackpad counts as must-have. Nodding along is nice-to-have. A shrug, or talk drifting elsewhere, is don't-need. Show: one tagged feature sheet per session.
4. **State the price.** End the demo on one figure, $49 per location per month, and say it as a fact rather than a question. Then stop talking. Whatever they do next goes in the log under one of three tags: instant yes, yes after hesitation, no. Note what they measure it against too. A manager who says "the agency charges me $60 extra every time someone calls in sick" is doing your pricing maths for you. Some grumbling means you're close to what they'll bear. If three managers in a row agree without blinking, the figure is too low, so quote $69 to the next batch. Show: the price tag and comparison for every session.
5. **Freeze the demo for a week, then decide whether to keep going.** Hold the script and screens steady for a week of sessions, then change one thing at the weekend so any shift in next week's answers has a single cause. You are done when four checks in your log come back yes. The people who said yes fit your early-adopter profile. They all marked the same problem must-have. You can name the few features that fix it. They accepted $49. Maurya calls these the exit criteria. Show: the four answers, each citing session ids.
6. **Cut the app.** Treat the current build as empty. Go through its feature list, and each item earns its way back only with a reason from the interview sheets: it was tagged must-have for the top problem, or a must-have breaks without it. The swap-request inbox might stay. The payroll export you built last month goes to the backlog as a nice-to-have, and the team chat nobody wanted gets deleted. Show: the feature list before and after, with interview evidence beside every feature that stayed.
7. **Define the activation flow.** Start from the finish line: the first Friday a manager's open shift gets covered without a phone call. Work back to signup and write each step as an event your analytics will record. For the rota tool: `account_created`, `location_added`, `staff_invited` (link sent by SMS), `shift_posted_open`, `shift_claimed`. Keep each event to a single action. When a cohort thins out between two events, you know which screen to fix. Before any real user arrives, open a private window, register with an unused email, and play a manager who has never heard of you until `shift_claimed` fires. Show: the numbered events, and a note that the fresh account reached `shift_claimed`.

This card and 'A five-day Sprint on the app you already have' feed each other. The Sprint reshapes a prototype in a week. This card decides which features survive into the build you actually ship.

## Artifacts produced

- `solution_interview` records: person, profile fit, feature tags, price response and verbatim quotes.
- An `exit_criteria` artifact: the four criteria, each marked met or not, with evidence.
- An `mvp_scope` artifact: every feature marked keep, backlog or delete, with its interview evidence.
- An `activation_flow` artifact: each numbered action between account creation and the user's top problem being fixed for the first time.
- New or updated pain entries if a must-have problem surfaced in the interviews.

## Anti-patterns

- **The feature tour.** You demo all fourteen screens because they exist. Spot it: your notes are full of features nobody tied to a problem.
- **Asking for a number.** You ask "What would this be worth to you?" and write down whatever they offer. Spot it: the price column records their guesses, and your own figure never appears.
- **Strangers in the chair.** You demo to people who never confirmed the problem. Spot it: no problem ranking on file for them.
- **Keeping what was hard.** The calendar sync took a week to build, so it stays. Spot it: kept features with no interview evidence next to them.
- **Hiding instead of cutting.** Don't-need features move into a settings menu. Spot it: the codebase and navigation are the same size as before.
- **The fantasy demo.** A screen shows an AI assistant or an integration that exists nowhere in the repo or on the roadmap. Spot it: a demo screen that maps to no file in the build and no ticket in the plan.
- **Onboarding that stops short.** The flow ends at profile setup, and the user never sees the problem solved. Spot it: the last activation step names no outcome.

## Gate criteria

The `stage-4-solution-test` gate needs Sprint test results and an app that was reshaped, not reused as-is. From this card, it looks for:

- the exit-criteria sheet with all four criteria backed by interview records
- a before-and-after scope that shows features removed, each removal traced to interview tags
- the activation flow, walked end to end on a fresh account

If the app has the same feature list it had before the interviews, it fails, however many interviews were run.

## Sources

- Running Lean, Ash Maurya. The solution interview, stating the price, cutting the MVP down to features the interviews proved, and defining the activation flow. Read the original: https://ashmaurya.com/books
- Running Lean (1st edition), Ash Maurya. The exit criteria for the solution interview, and the weekly batches for adding or dropping features. Read the original: https://ashmaurya.com/books

## Sean's notes

None yet.
