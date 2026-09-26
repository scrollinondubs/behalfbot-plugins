---
id: problem-interview-exit-criteria
type: framework-card
title: The problem interview and its exit criteria
stage: 3
gate: stage-3-discovery
tier: core
sources: [running-lean, running-lean-1st-ed]
---

# The problem interview and its exit criteria

## Purpose

You believe agency owners lose a day a month matching client invoices to time logs. A round of problem interviews (Ash Maurya's term, from Running Lean) puts that belief in front of real agency owners. You leave with three written answers: who hurts most, whether it hurts enough to matter, and what they hack together today. Or you leave with evidence that you picked the wrong segment. Both count.

## When to use

Stage 3. You have a segment and a short list of problems you think it has. You have nothing to demo yet, and that's on purpose.

If your recent calls keep ending in "love it, keep me posted", fix your questions before you fix your script: read [[interviews-without-fooling-yourself]] first. The prototype stays in the drawer until stage 4.

## Principles

- Test the problem. Your product should barely come up until the final two minutes.
- A ranking is something the person says. A workaround is something they do, and it counts for more.
- A problem with no workaround is rarely a must-have, however hard people nod.
- Hold the script steady within a batch so the answers can be compared. Change it between batches.
- The round ends when you meet the exit criteria. Reaching a number of calls does not end it.

## Procedure

1. **Draft the call before you book it.** Imagine you're building for property managers who chase contractor invoices. On one page, write your opening, the facts that qualify someone, the problem story, the ranking step, the questions about their current workaround, and the closing ask. Word each of your one to three problems the way a property manager would complain about it to a colleague. *Show:* the script, with its qualifying questions.

2. **Set the scene.** Take two minutes. Say you are researching and have nothing to sell yet. Tell them you will describe a few problems and ask which ones ring true. *Show:* your opening lines.

3. **Confirm they are in the segment.** Before any talk of problems, ask for a few facts: their role, team size, tools, and how often the task comes up. Say a bookkeeper tells you they have only three clients. Keep the call going, but file their answers in a separate pile. *Show:* the segment fields on the interview record.

4. **Tell a short problem story.** Describe the problem as a scene from their working week: "It's month end. Fourteen clients still owe you receipts, and you're chasing the same PDFs across email, Slack and a shared drive." Then stop talking. *Show:* the story text in the script.

5. **Have them rank the problems.** Read the problems back as a list. Ask them to put the list in order and to say whether anything worse is missing. Shuffle the order between calls, so a problem does not win just by coming first. *Show:* the ranking on each record.

6. **Dig into the current workaround.** This is the longest part of the call, roughly a quarter hour. Take the problem they put first and ask about the most recent time it bit them: "When did you last reconcile Stripe payouts against invoices? Talk me through that afternoon." Note every spreadsheet, app, helper, hour and dollar that shows up. If they shrug at a problem, drop it. Persuading them it hurts only corrupts the record. Copy down their exact wording. Then judge each problem by what they already spend on it, and mark it don't need, nice-to-have, or must-have. *Show:* the workaround and your rating for each problem.

7. **Close with the ask.** Give a one-line description of what you are building. Ask whether they want to see it when it exists, and who else like them you should talk to. *Show:* their follow-up answer and any referral names on the record.

8. **Write it up before the next meeting.** Memory of a call goes soft within the hour. If two of you ran the call, each fills in the record separately, then you reconcile the two. *Show:* the completed record.

9. **Tally each batch.** Weekly works. Put every record into one table with these columns: segment facts, ranking, rating, workaround. Sort by strongest rating and look for what the top rows have in common. Cut problems that nobody rates above don't need. Add any must-have that surfaced unprompted. Move the segment toward the strongest responders. *Show:* the tally table and a dated log of script changes.

10. **Write the exit statement.** Maurya puts a floor of ten interviews under these criteria, but the floor isn't the finish line. You're done when the records fill all three lines. Line one says who to go find next, specific enough to search for: "ops leads at 20 to 80 person logistics firms who still route delivery exceptions through a shared inbox." Line two names the one problem those people rated must-have. Line three quotes how they deal with it today. If any line stays blank, run another batch or pick a new segment. *Show:* a three-line exit statement, with each line linked to the records behind it.

## Artifacts produced

- One `interviews` row per call: segment facts, ranking, workaround, rating, follow-up and referrals in the notes.
- An `artifacts` row of kind `problem_tally` per batch, with the dated log of script changes in `meta`.
- `pains` rows for each problem, quoting the interviewee, tagged with its rating.
- An `artifacts` row of kind `exit_criteria`: the early-adopter profile, the must-have problem and today's workaround, each linked to interview ids.

## Anti-patterns

- **Pitching early.** The record is full of feature requests, or your problem story names your product.
- **Trusting the ranking.** Someone ranks a problem first but spends nothing on it: no tool, no hours, no hack. Flag it as a mismatch and don't count it as a must-have.
- **Editing mid-batch.** Calls in the same week asked about different problems, so the tally won't line up.
- **Blending segments.** The profile reads "small businesses" because strong and weak responders ended up in one pile.
- **Stopping at a number.** You hit ten calls and called it done, but the exit statement is still vague.
- **Next-day notes.** Records are dated a day after the call and read like a summary, with no quotes.

## Gate criteria

This card supplies the following evidence for `stage-3-discovery`:

- Complete problem interview records, enough to fill the exit statement. The gate audits them with `interviews-without-fooling-yourself`.
- The batch tallies and the exit statement, with every claim traced back to records.
- The follow-up and referral answers from each close, as raw input for the sibling card *Earlyvangelist criteria and commitment signals* That card scores commitment. This card only records it.
- The early-adopter profile, which is where the gate starts looking for earlyvangelists.

## Sources

- Running Lean, Ash Maurya. This card takes the problem interview, its structure and its exit criteria from here. Read the original: https://ashmaurya.com/books
- Running Lean (1st edition), Ash Maurya. The earlier version of the same script and of the weekly batch review, used to cross-check this card. Read the original: https://ashmaurya.com/books

## Sean's notes

None yet.
