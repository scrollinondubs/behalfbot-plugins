---
id: sales-safari-pain-log
type: framework-card
title: Sales Safari: a quote-backed pain log
stage: 2
gate: stage-2-pain-research
tier: core
sources: [thirty-x-500, sales-safari-2023, sales-safari-101]
---

# Sales Safari: a quote-backed pain log

## Purpose

Build a log of real pains, each one backed by something your audience wrote in public. Every entry shows who said it, where and when. Nothing in it is your guess.

## When to use

Stage 2, once stage 1 has given you a named audience and at least three active [[watering-hole|watering holes]]. You read before you build, and before you talk to anyone.

Wrong card if you have no watering holes yet. Back to stage 1. Also wrong if the log is already thick and you want to know what it adds up to. That's *Cluster pains into jobs* and *Problem hypothesis and when you have heard enough*.

## Principles

- People describe their problems more honestly to peers than to a founder with a survey.
- A pain you can't quote with a link and a date is just your opinion.
- Their exact words matter more than your summary of them. You will reuse those words later.
- One post is a story. The same complaint from different people in different places is a pattern.
- Read to understand the person. Fixing them comes later.

## Procedure

Amy Hoy and Alex Hillman teach this as Sales Safari in 30x500. Picture a Discord where agency bookkeepers swap month-end horror stories: you sit in it, take notes, and send no DMs or polls. Posts nobody wrote for you are your raw data.

1. **Pick your hunting ground for the session.** Open one watering hole from your stage 1 list. It could be a subreddit, a Slack or Discord server, a Facebook group, a product's community forum, or the reviews on a marketplace listing. Set a timer for 45 minutes. *Show:* the watering hole name, its URL, and the session date.

2. **Scan the thread titles first.** Before you open anything, read two or three pages of titles and note the nouns and phrases that keep coming back. Say you are researching bookkeepers who serve small agencies. You might see "month-end", "receipt chasing" and "client won't use the portal" again and again. Those tell you which threads to read closely. *Show:* a short list of repeated phrases.

3. **Read threads slowly, top to bottom, replies included.** Notice anything that hurts: complaints, workarounds, apologies, "is it just me" posts, and people asking strangers for help late at night. The replies count as much as the original post. *Show:* the threads you opened, each with its link.

4. **Capture each pain as a verbatim quote.** Copy the words exactly, typos included. Add the permalink and the post date. Don't tidy the quote up. "I spend every first Monday chasing four clients for the same receipts" is evidence. "Receipt collection is inefficient" is not. *Show:* quotes with link and date.

5. **Note their words, worldview and buys.** Next to each quote, add three things:
   - **Their words.** The terms of art they use without explaining them.
   - **Their worldview.** The belief sitting under the complaint. For example: "clients will never learn a new tool, so I adapt to them".
   - **What they already buy.** The tools, templates, courses and paid help they mention or recommend.

   *Show:* those three fields filled in for each quote, or marked "none seen".

6. **Log each pain as a `pains` row.** Give each distinct pain its own row, even when two come from the same post. *Show:* the new rows.

7. **Repeat across watering holes.** Run more sessions until your log draws on at least three different places and many different authors. *Show:* the watering-hole spread in your log.

8. **Hand off to painstorming.** Painstorming, also Hoy and Hillman's term, is the next step. It takes your raw log and groups the pains into the jobs people are trying to get done. *Cluster pains into jobs* covers it. *Show:* a log ready for that card.

## Artifacts produced

- `pains` rows, one per pain: `quote` verbatim, `source_url` as the permalink, `watering_hole`, `segment` if you know it, and `tags` holding the post date, the author handle (or "anon"), their words, the worldview and what they buy. Leave `job` empty. Clustering fills it.
- An `artifacts` row of kind `safari_session` per run: the watering hole, the date, the repeated phrases and the threads you read.

## Anti-patterns

- **The tidy summary.** Rows read like your own sentences, such as "users struggle with onboarding". Check whether you could paste each quote back into a search and find the original post.
- **Answer mode.** Your notes are full of advice you would give the poster. You read as a helper, not a researcher. Delete every fix from the log.
- **One loud voice.** A third of your rows come from a single long rant. Count distinct authors, not rows.
- **Link rot waiting to happen.** Quotes with no permalink or no date, or a link to the channel instead of the message. The auditor cannot check them.
- **Asking instead of reading.** You posted a poll or a "what's your biggest pain?" thread. That is a survey in disguise, and interviews wait until stage 3.
- **Pains only.** The words, worldview and buys columns are empty. You will be short of them later when you write copy and pick a price.

## Gate criteria

The `stage-2-pain-research` gate asks for a quote-backed pain log clustered into jobs. From this card, the auditor checks three things:

- Every `pains` row carries a verbatim quote, a working `source_url` and a date.
- The rows come from more than one watering hole and many distinct authors.
- The words, worldview and buys fields are filled in where the source showed them.

The clustering into jobs comes from the painstorming handoff, not from this card.

## Sources

- 30x500, Amy Hoy and Alex Hillman. This card takes Sales Safari as a research method from them, along with painstorming as the step that follows it and the practice of noting the audience's language, worldview and purchases next to each pain. Read the original: https://30x500.com/academy/
- Sales Safari updated for 2023, Amy Hoy and Alex Hillman (Stacking the Bricks). This card takes the point that Safari now works in chat servers, groups and social feeds as well as forums, and that any note-taking tool will do. Read the original: https://shorts.stackingthebricks.com/updating-sales-safari-2023/
- Sales Safari 101, Stacking the Bricks. This card takes the framing of Safari as observation of public behaviour rather than cold outreach or surveys. Read the original: https://shop.stackingthebricks.com/sales-safari-101

## Sean's notes

None yet.
