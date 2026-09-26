---
id: cluster-pains-into-jobs
type: framework-card
title: Cluster pains into jobs
stage: 2
gate: stage-2-pain-research
tier: core
sources: [hbr-jobs-to-be-done, christensen-institute-jtbd, jobs-to-be-done-org]
---

# Cluster pains into jobs

## Purpose

Turn a pile of quote-backed pains into a short list of jobs. Each job says what progress a person is after, in which situation, and what they use for it today. With that list you can choose which job to serve. Without it you're building for a mood.

## When to use

Stage 2, once your pain log holds real quotes from real people, each linked back to where it was said. *Sales Safari: a quote-backed pain log* builds that log.

Wrong card if the log is thin or full of your own paraphrases. Collect more quotes first. Also wrong for deciding whether you've heard enough. That's *Problem hypothesis and when you have heard enough*.

## Principles

- A job is progress in a situation. Who the person is matters less than the moment they are stuck in. This is the core of Jobs to be Done, the theory Clayton Christensen and his co-authors set out in HBR.
- People hire something to get a job done, and they fire it when it lets them down. Christensen's word "hire" covers any fix: a tool, a spreadsheet, a freelancer, or putting it off.
- Every job has three sides. The functional side is the task. The social side is how they want to look to others. The emotional side is how they want to feel.
- Doing nothing is a real competitor. A job with no current hire is still a job, and often the widest one.
- Group by situation, not by feature request. "Wants a dashboard" is a solution. Ask what they were in the middle of when they asked for it.

## Procedure

1. **Read the whole log in one sitting.** For each quote, note in a few words the situation behind it: what was happening, what deadline was close, who was waiting. *Show:* every pain entry has a situation note.

2. **Sort by situation.** Put quotes whose situations match into the same pile, even when the complaints sound different. Say you are building for small marketing agencies. "I paste GA screenshots into slides every Sunday night" and "the client asked why March looks different from what I sent" both come from the monthly client report. *Show:* named clusters, each with at least three quotes from more than one person.

3. **Split any pile that holds two situations.** An agency owner building a report before a renewal call is in a different spot from one sending a routine monthly update, even though the tool is the same. If one fix would not help both, split them. *Show:* a list of which piles you split and why.

4. **Fill in the three sides for each cluster.** Functional: get accurate numbers into a deck by Monday. Social: look in control in front of the client. Emotional: stop dreading Sunday nights. Pull each side from a quote where you can. If no quote backs a side, mark it as a guess. *Show:* a table of three sides per cluster, with quote ids beside each.

5. **List what they hire today.** Name the current fix for each cluster: Looker Studio templates, a VA on Upwork, a Notion checklist, or simply sending the report late. Treat "puts it off" or "does nothing" as a real entry. *Show:* a current-hire list per cluster, with the quotes that reveal it.

6. **Write each job as one sentence.** Name the situation, the progress and what that progress buys them. For example: "Agency owners the week a monthly client report is due, who need numbers they trust in a clean deck so the call doesn't turn into an interrogation." *Show:* one sentence per cluster, readable by someone who has not seen the log.

7. **Tag every quote.** Set `pains.job` on every entry to the id of its job. A quote that fits no job goes into an `unclustered` bucket. Do not force it into a job. *Show:* zero entries with an empty `pains.job`.

## Artifacts produced

- An `artifacts` row of kind `jobs`. For each job it holds an id, the one-sentence job, the situation, the functional, social and emotional sides with quote ids, and the current hires including doing nothing.
- A `pains.job` value on every pain entry, pointing at a job id or at `unclustered`.
- A note in that row's `meta` on the piles you split or merged, and why.

## Anti-patterns

- **Persona piles.** The clusters are labelled "freelancers" or "agencies with 10+ staff". That is sorting by who they are, not by the moment. Rename each one after the situation, and see whether it holds together.
- **Feature-shaped jobs.** A job sentence names your product or one of its parts, such as "help me auto-generate reports". Replace the product with the progress the person wants.
- **Function only.** The social and emotional columns are blank or copy the functional one. Go back to the quotes. The feelings are usually there in words like "embarrassed", "dread" and "the client noticed".
- **Invisible competitor.** A current-hire list names only software rivals. If nobody on the list is "does nothing" or "does it by hand", you have probably missed the biggest one.
- **One-quote jobs.** A job resting on a single person's post. Merge it or park it until more evidence turns up.
- **Silent orphans.** Quotes that fit nowhere are quietly deleted. Keep them in `unclustered`. They may be the start of a job you have not named yet.

## Gate criteria

The `stage-2-pain-research` gate asks for a quote-backed pain log clustered into jobs. From this card, the auditor checks that:

- every pain entry has `pains.job` set to a job id or `unclustered`
- each job has a one-sentence statement tied to a specific situation
- each job lists its functional, social and emotional sides, with quote ids behind them or a clear mark where a side is a guess
- each job names its current hires, doing nothing included
- each job rests on quotes from more than one person

## Sources

- Know Your Customers' Jobs to Be Done, Clayton Christensen, Taddy Hall, Karen Dillon and David Duncan (HBR, September 2016). This card takes the idea of a job as progress in a situation, the term "hire", and the point that the situation predicts behaviour better than traits do. Read the original: https://hbr.org/2016/09/know-your-customers-jobs-to-be-done
- Jobs to Be Done theory, Christensen Institute. This card takes the three sides of a job, functional, social and emotional, and the point that jobs change as situations change. Read the original: https://www.christenseninstitute.org/theory/jobs-to-be-done/
- jobstobedone.org, Bob Moesta and Chris Spiek. This card takes the point that people who want progress but do nothing are a real and often overlooked market. Read the original: https://jobstobedone.org/

## Sean's notes

None yet.
