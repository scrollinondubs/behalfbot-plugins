---
id: find-the-watering-holes
type: framework-card
title: Watering holes: find where they already talk
stage: 1
gate: stage-1-audience
tier: core
sources: [thirty-x-500, lean-customer-development]
---

# Watering holes: find where they already talk

## Purpose

Say you plan to sell to freelance bookkeepers who serve restaurants. This card ends with the subreddits, Slack groups and review pages where those bookkeepers already complain to each other about month-end close, with no founder in the room. In their 30x500 course, Amy Hoy and Alex Hillman name such spots watering holes. You leave with three or more, each confirmed as lively and relevant, with the evidence written down.

## When to use

Stage 1, right after you've named an audience with *Audience first, product second*. That one-line audience is the input.

Wrong card if the audience is still "small businesses" or "creators". Narrow it first. Also wrong if you're itching to collect pains and quotes. That's stage 2, and it runs on the list you build here.

## Principles

- People talk more honestly in writing, among their own peers, than they do to a founder asking questions.
- A busy thread count matters more than a big member count. Ten thousand members and nothing posted since March is a graveyard.
- Your audience is often a sub-group inside a bigger community. Search inside large spaces before deciding they are not online.
- "They're not online" usually means you haven't searched properly yet.
- This stage is for watching. You read, you take notes, and you post nothing.

## Procedure

1. **Build a search sheet.** Write three columns. First, the names members use for themselves ("dispatcher", "fleet manager", "ops lead"). Second, their jargon and the tools they use ("ELD", "Samsara", "load board"). Third, venue words ("forum", "subreddit", "Discord", "Slack group", "reviews"). *Show:* the sheet, with at least five entries per column.

2. **Search every pairing.** Combine one word from each column in a search engine, in Reddit search, in Discord and Slack community directories, on G2 and Capterra review pages, on Stack Exchange sites, and in GitHub Discussions for tools the audience uses. Save each place that looks plausible. *Show:* a longlist of ten or more URLs.

3. **Ask two people privately.** Message two members of the audience you already know. Ask where they go when they are stuck on something at work. A founder building scheduling software for mobile pet groomers may learn this way about a private Facebook group that no search turns up. *Show:* their answers, added to the longlist.

4. **Check activity, with a date.** Open each candidate. Count the new threads from the last seven days. Check whether members reply to each other, not only to moderators or vendors. Note the date you looked. *Show:* an activity line for each URL, like "2026-09-24: 31 new threads in 7 days, most with 3+ member replies".

5. **Check it is on topic.** Skim the last page of thread titles. Is the talk about the job your audience does, or has it drifted to memes, hiring posts or self-promotion? A subreddit for indie tabletop game makers might turn out to be mostly Kickstarter launches, with almost no talk about printing or shipping. *Show:* a keep or drop mark for each place, with a one-line reason.

6. **Record the keepers.** Write each kept place to the ledger with its URL, type, activity note and check date. If fewer than three survive, go back to step 1 and add terms. *Show:* three or more places marked keep.

## Artifacts produced

- An `artifacts` row of kind `watering_holes`. For each place it holds the URL, the type (forum, subreddit, Slack, Discord, review site, Q&A), a dated activity note, an on-topic note, and keep or drop.
- The step 1 search sheet in that row's `meta`, so stage 2 can reuse the terms.

## Anti-patterns

- **Headcount hunting.** The list gives member counts and no recent dates. Ask for threads from the past week.
- **The founder's own feed.** Every entry is a place you already hang out. Check whether any entry came from searching.
- **Vendor showrooms.** The "community" is a tool company's help forum where staff answer every post. Look for members answering each other.
- **Posting before reading.** You've already dropped a "would you use this?" poll in the dispatcher Slack. Stop. Posting belongs to a later stage, and the thread will skew whatever you read there afterwards.
- **Giving up early.** You decide a B2B audience "isn't online" after two searches. Look at the search sheet. If it's thin, so was the search.
- **Stale snapshots.** Activity notes with no date, or dates from months ago. Re-check before the gate.

## Gate criteria

The `stage-1-audience` gate needs a named audience, three or more active watering holes, and a first bowling-pin segment. This card supplies the watering holes: at least three ledger entries marked keep, each with a URL, an activity note dated within the last 30 days showing member-to-member replies, and a reason it is on topic. The named audience comes from *Audience first, product second*, and the segment from *First bowling-pin segment*.

## Sources

- 30x500, Amy Hoy and Alex Hillman. The watering hole idea, searching with the audience's own words, and studying a community before joining in. Read the original: https://stackingthebricks.com/30x500/
- Lean Customer Development, Cindy Alvarez. Asking a few target customers where they go for advice, and treating reply counts as a first read on what matters to them. Read the original: https://www.cindyalvarez.com/lean-customer-development/

## Sean's notes

None yet.
