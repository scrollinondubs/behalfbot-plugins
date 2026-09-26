---
id: prfaq-v0
type: framework-card
title: PR/FAQ v0: write the launch before the product
stage: 0
gate: stage-0-why
tier: core
sources: [working-backwards]
---

# PR/FAQ v0: write the launch before the product

## Purpose

Write the launch announcement for a product that doesn't exist yet. Once it's on paper, every claim the idea rests on is sitting there in plain view, and you can list them as assumptions before you write a line of code.

## When to use

Stage 0, once you can name a problem you care about. Can't yet say why it matters to you? Do *Find your why* first.

Wrong card once you have usage data or interview notes. Then you're rewriting from evidence, and that's the stage 5 PR/FAQ v2 card.

## Principles

- Picture a bookkeeper on the last day of the month, every receipt already filed, and ask what has to exist for that day to go so smoothly. The feature list comes out of that picture, never the other way round. Colin Bryar and Bill Carr name this habit working backwards.
- The PR/FAQ (their term) pairs a short launch announcement with a set of questions and answers. Vague ideas fall apart once you have to write them down.
- Version 0 is supposed to be wrong. Its job is to show you where.
- Any sentence you can't prove yet is an assumption. Label it.
- Short beats complete. Keep the release to one page and the FAQ to a page or two.

## Procedure

1. **Headline.** Pick a launch date six to twelve months out. Write the headline a customer would read, naming the product and who it helps in their own words. Example: "Nudgebook chases missing receipts so small bookkeeping firms close the month on time." *Show:* the headline plus a one-line subhead.

2. **Press release.** Write the body in under a page. Open on the pain as the buyer feels it: a bookkeeper on the 28th of the month sending a fourth email to a client about one fuel receipt. Then say what their week looks like with your product, how they sign up, and a quote from an invented but believable customer. *Show:* the one-page release.

3. **External FAQ.** List five to ten questions a real buyer would ask before paying, and answer them. What does it cost per seat? How long does setup take? Where does my clients' data go? Does it connect to Xero or QuickBooks? *Show:* the external FAQ with answers.

4. **Internal FAQ.** Write the questions you would rather avoid. Who pays, and how much? Can you build and support this alone? What does each customer cost you to serve? Why hasn't an accounting platform already shipped this? What result would make you drop the idea? "I don't know yet" is a valid answer. *Show:* the internal FAQ, gaps included.

5. **Assumptions list.** Reread every line of all three parts. Move each guess to a list, one claim per line, worded so it could turn out false. For example: "Bookkeepers lose three or more hours a month chasing receipts." "Firms will pay $49 a seat." "Clients will upload from a text message link." *Show:* the list, with each item pointing back to the line it came from.

6. **Hand it on.** Save the list and take it to *Plan A on a Lean Canvas, riskiest assumption first*, which picks what to test first. Don't rank the assumptions here. *Show:* the list saved on your version 0 PR/FAQ.

## Artifacts produced

- A `prfaq_versions` row at version 0: the press release, external FAQ and internal FAQ in `body`.
- The same row's `assumptions` list: each untested claim, the PR/FAQ line it came from, and status `untested`.

## Anti-patterns

- **The changelog release.** The press release lists features and integrations. Count the sentences that mention the customer or their problem. If that's fewer than half, rewrite.
- **Founder voice.** Lines like "We built an AI-first platform" are things no customer would say. Read the release aloud as your buyer. Cut anything they wouldn't say.
- **Softball internal FAQ.** Every answer sounds confident and none says "I don't know". If writing it didn't make you uneasy, you skipped the hard questions.
- **Hidden assumptions.** The release quotes a price, a time saving or a market size, and the list has no matching item. Another warning sign is a list with fewer than five items.
- **Polishing v0.** You're on day three of wording changes. A first draft should take an afternoon.
- **Building alongside.** A repo or landing page gets started before the internal FAQ is written. Close the laptop lid on it. If you arrived with an app already built, it waits too.

## Gate criteria

The `stage-0-why` gate needs a problem the founder cares about and a PR/FAQ v0 with its assumptions listed. From this card, the auditor looks for:

- A press release under one page, in customer language, that names the customer and the problem.
- An external FAQ and an internal FAQ. The internal FAQ has at least one question the founder can't answer yet.
- An assumptions list. Every number or claim in the release traces to an item, and each item could be proven false.

The problem itself, and why it matters to the founder, comes from *Find your why*.

## Sources

- Working Backwards, Colin Bryar and Bill Carr. This card takes the PR/FAQ format and the working backwards habit of starting from the customer's experience, and narrows them to a solo founder's first draft. Read the original: https://www.workingbackwards.com

## Sean's notes

None yet.
