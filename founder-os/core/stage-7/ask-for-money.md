---
id: ask-for-money
type: framework-card
title: Ask for money: state the price, count the commitments
stage: 7
gate: stage-7-validation-and-sales
tier: core
sources: [running-lean, mom-test]
---

# Ask for money: state the price, count the commitments

## Purpose

Find out who will pay. Put a real price in front of prospects and ask for something they would miss. You come away with a log of priced offers and what each prospect actually gave up.

## When to use

Use it at stage 7, once discovery has confirmed a problem worth solving and you have something to show: a working build, a clickable prototype or a scoped pilot.

It is the wrong card if you still cannot describe the problem in the customer's words. Go back to the stage 3 card 'Interviews without fooling yourself'. If you have nobody to pitch yet, start with 'Founder-led outbound'.

## Principles

- A price is a guess you are testing, so say it yourself. Ash Maurya's point: a buyer asked to name a figure has every reason to go low.
- Anchor the number to two things the buyer already knows: what fixing the problem is worth, and what their current workaround costs.
- Friction is a measuring tool. A deposit, a signed pilot or a card on file tells you more than an easy yes.
- Rob Fitzpatrick's name for real intent in The Mom Test is commitment: the prospect hands over something it would hurt to lose. A head of ops who books their team into a two-week trial, forwards you to the CFO or pays a pilot fee has paid in all three of Fitzpatrick's currencies: time, reputation and money.
- Advancement, also Fitzpatrick's term, means the prospect moves to a concrete next step toward buying. A call that ends without one has failed, however warm it felt.

## Procedure

1. Write the offer before the call. Include one price, one billing term, what the buyer gets, and what the pilot must prove by what date. Show: the offer as a one-page doc.
2. Work out the anchor. List what this buyer spends on the problem today, such as ops hours, a contractor or a clunky tool they already license, and turn it into a monthly figure. For example, a founder whose tool matches Stripe payouts to invoices learns the finance lead spends ten hours a month doing it by hand. At $60 an hour that is $600, so $249 a month costs less than half the workaround. Show: the anchor figure written next to your price.
3. Say the price in the meeting, then stop talking. "It's $249 a month, billed quarterly. That's under half what the manual reconciliation costs you now." Note whether they agreed straight away, pushed back or asked about terms. Show: their response, in their words, logged within the hour.
4. Ask for friction that fits where you are. Early on, that means a paid pilot with a signed one-page agreement, or a refundable deposit. Later, it means a card on file with the first charge after the trial. On a marketplace, it could be a supplier paying a listing fee up front. Show: the signed pilot, the deposit receipt or the Stripe customer record.
5. If money is not on the table yet, ask for a different currency. An intro to whoever owns the budget costs them reputation. Two weeks of their team running the tool on live data costs them time. Show: the intro email, or the calendar invite with named attendees.
6. End every meeting with a dated next step: what happens, who does it, by when. If you cannot name one, mark the meeting failed. Show: the next step and its date in your log.
7. Log every offer, including the dead ones. A clear no is useful data. The only real miss is never asking. Show: the offer log, with one row per priced ask.

## Artifacts produced

- An `offer_log` artifact with one row per priced ask. Each row holds the prospect, the date, the price stated, the anchor used, the response (accepted, hesitated, rejected or stalled), the currency committed (time, reputation, money or none), and the next step with its date.
- A `commitment` entry for each deposit, signed pilot, card on file or paid invoice, linked to its proof.
- A running tally of offers made, money commitments, other commitments, and meetings that ended with no next step.

## Anti-patterns

- **The ballpark question.** Your notes show you asking "roughly what would this be worth to you?" That hands the pricing job to the buyer, and they will price low.
- **The frictionless yes.** You run a free beta with no end date and no card on file. Sign-ups climb while nobody's commitment gets tested.
- **Counting praise.** Your log says "loved it" where a currency should be. Praise costs the speaker nothing, so log it as zero.
- **"Keep me posted."** The prospect asks you to get back in touch at launch. That is a polite exit, not an order. Ask for something today, or log it as a stall.
- **Discounting before any objection.** The price in the log is lower than the price in your written offer, and the buyer never pushed back.
- **The nice chat.** You cannot say what happens next or when. Mark it failed and go back with a specific ask.

## Gate criteria

The `stage-7-validation-and-sales` gate needs paying customers or signed pilots. From this card, it looks for an offer log where every row shows a stated price and the buyer's response. It also looks for proof of each money commitment: a paid invoice, a deposit receipt, a card on file or a signed pilot agreement with a price in it.

Time and reputation commitments show momentum but do not pass the gate on their own. The sibling card 'Customer validation and the sales roadmap' covers whether the numbers justify pushing on.

## Sources

- Running Lean, Ash Maurya. This card takes the rule to tell customers the price instead of asking them, anchoring the price against what they use today, and raising friction to test real intent. Read the original: https://ashmaurya.com/books
- The Mom Test, Rob Fitzpatrick. This card takes commitment and advancement, the currencies of time, reputation and money, and the rule that a meeting with no next step has failed. Read the original: https://www.momtestbook.com

## Sean's notes

None yet.
