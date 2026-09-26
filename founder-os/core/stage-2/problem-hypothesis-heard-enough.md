---
id: problem-hypothesis-heard-enough
type: framework-card
title: Problem hypothesis and when you have heard enough
stage: 2
gate: stage-2-pain-research
tier: core
sources: [lean-customer-development]
---

# Problem hypothesis and when you have heard enough

## Purpose

Give your pain research a claim the evidence can prove wrong, and a clear point where the reading stops. You leave with a hypothesis that's either backed by independent quotes or plainly marked broken.

## When to use

Start of stage 2, before the first reading session. Come back every time the pain log grows by about ten entries. Also useful when the log feels big and you can't say what it proves.

Wrong card if you can't yet name the people you're studying. That's stage 1. For reading threads and logging quotes, use *Sales Safari: a quote-backed pain log*. Grouping quotes into jobs is *Cluster pains into jobs*.

## Principles

- Three slots, all filled: who hurts, what hurts, and the moment it happens. That is the problem hypothesis, in Cindy Alvarez's term. "Freelance bookkeepers hate admin" gives the log nothing to push against, while "freelance bookkeepers lose an afternoon each month matching Stripe payouts to invoices" can fail on the first ten quotes.
- Narrow beats broad. A tight claim gets confirmed or killed within days. A loose one soaks up every quote.
- Write it before you read, so the log has something to argue with.
- Independence counts. Volume does not. Ten posts from one angry user are one data point.
- You have heard enough when new reading stops changing the picture. Alvarez's test is surprise. Once fresh sources only repeat what you already have, stop.

## Procedure

1. Write the hypothesis as one sentence: who, what goes wrong, and during which task. Example: "Agency owners running five to twenty client Webflow sites lose billable hours chasing clients for content sign-off before each launch." *Show:* the sentence, dated.
2. Under it, add a kill line: what the log would show if the hypothesis were false. Example: "Sign-off delays come up only as mild grumbling, or owners say their project tool already handles it." *Show:* the kill line next to the hypothesis.
3. Read and log against it. The Sales Safari card covers how. Tag each `pains` row `supports`, `contradicts` or `surprise`. *Show:* log entries, each with a tag.
4. Every ten entries, run a check. For each emerging job, count the distinct people and the distinct [[watering-hole|watering holes]] behind it. Count how many of the last ten entries were tagged `surprise`. *Show:* a short check note with those counts.
5. Apply the FounderOS stopping rule. A job has enough behind it when quotes come from at least five different people in at least two separate places, and the last ten entries added no new job and no new twist on an existing one. *Show:* a stopping note naming which jobs passed and the counts that got them there.
6. If no pattern has formed after twenty or so entries, narrow the "who". Pick one role, company size or tool stack and read again. Alvarez reads scattered answers as a sign that the audience is too wide. *Show:* a revised hypothesis, with the old version kept and dated.
7. If `contradicts` outweighs `supports`, or the kill line has come true, call it. Rewrite the hypothesis from what the log does show. If the people themselves were the wrong group, go back to stage 1. *Show:* the hypothesis marked invalidated, with links to the entries that sank it.

## Artifacts produced

- An `artifacts` row of kind `problem_hypothesis` holding the current sentence, the kill line, a status (open, supported, narrowed or invalidated), and every earlier version with the date it changed.
- A `supports`, `contradicts` or `surprise` value in the `tags` of every `pains` row.
- An `artifacts` row of kind `saturation_check` for each batch of ten entries. The last one is the stopping note, listing each job with its count of distinct people and distinct sources.

## Anti-patterns

- **The unfalsifiable sentence.** "Small businesses struggle with operations." Tell: try to write the kill line. If you can't, the hypothesis is too vague to test.
- **Hypothesis after the fact.** It was written once the reading was done, so it matches the log perfectly. Tell: there is no dated version older than the log entries.
- **One loud voice.** A job has twelve quotes, but they trace back to two Reddit accounts. Tell: the distinct-person count is far below the quote count.
- **Reading forever.** The log has 150 entries and the last forty are all repeats. Tell: the `surprise` tags stopped long ago and you're still reading.
- **Quiet rescue.** The wording of the hypothesis drifts to fit the quotes, and nothing is ever marked wrong. Tell: the sentence has changed but there is no new dated version and no invalidated mark.
- **Stopping at the first hit.** Three quotes agree on day one and the job gets called proven. Tell: the stopping note cites a single watering hole.

## Gate criteria

The `stage-2-pain-research` gate wants a quote-backed pain log clustered into jobs. From this card's work, the auditor checks for:

- A dated problem hypothesis, written before most of the log, with its kill line and any revisions.
- Every job offered as evidence meeting the stopping rule: five or more distinct people, two or more sources, and a final check showing ten entries with no new job and no new twist.
- If the hypothesis was invalidated, the entries that sank it and the revised hypothesis now being tested.

## Sources

- Lean Customer Development, Cindy Alvarez. This card takes three ideas from it: the problem hypothesis built from a person, a problem and a task; narrowing the audience when no pattern forms; and stopping once new evidence no longer surprises you. The book applies these to interviews, and this card adapts them to reading. Read the original: https://www.cindyalvarez.com/lean-customer-development/

## Sean's notes

None yet.
