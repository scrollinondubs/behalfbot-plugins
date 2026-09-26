---
id: plan-a-riskiest-assumption
type: framework-card
title: Plan A on a Lean Canvas, riskiest assumption first
stage: 0
gate: stage-0-why
tier: core
sources: [running-lean, running-lean-1st-ed, lean-customer-development, love-the-problem]
---

# Plan A on a Lean Canvas, riskiest assumption first

## Purpose

Put the whole business on one page as a set of guesses, then find the one guess that kills the idea if it's wrong. That guess gets tested first. Everything else waits.

## When to use

Stage 0, right after your PR/FAQ v0. The assumptions you pulled out of the PR/FAQ are the raw material here.

Wrong card if all you have is a feature you want to build and no problem behind it. Go find the problem first. Also the wrong card once your list is ranked and you want to know how to test it. That's stages 2 to 4.

## Principles

- Ash Maurya calls the first version of a business **Plan A**. Most of it will turn out wrong. Writing it down is how you find out which parts.
- The **Lean Canvas** is Maurya's one-page take on Alex Osterwalder's Business Model Canvas. It gives the problem its own box next to the solution, so a feature list has nowhere to hide.
- A good assumption is a claim one result could kill.
- Unknown is not the same as dangerous. Worry about the gaps where a wrong answer costs you months or the whole business.
- For a vibecoder the build is rarely the risky part. You can ship a prototype over a weekend. Finding out nobody pays takes longer and hurts more.

## Procedure

1. **Start with what you already wrote.** The press release names a customer, a pain and a promise. Drop each onto the page. Whatever stays blank is where the PR/FAQ was fuzzy, often how you'd reach bookkeepers and what they'd pay. Put a question mark there instead of making something up. *Show: the canvas, gaps marked.*

2. **Split the segments.** Ask who would pay, then who else. The invoice chaser could serve a solo designer with one late client or a bookkeeper tracking forty clients' receivables. Different prices, different places to find them, different businesses. Give each of your top two or three its own canvas. *Show: one labelled canvas per segment.*

3. **Turn every box into sentences.** Go box by box and write each phrase as a claim: "bookkeepers" becomes "bookkeepers chase late invoices for their clients every week." Add the PR/FAQ list. Cindy Alvarez's point holds here: write them all down before you judge any, since the claim you're too sure of to write is usually the load-bearing one. Fifteen or twenty lines is normal. *Show: the numbered list.*

4. **Make each one falsifiable.** "Agencies struggle with late payments" can't fail. "Most agency owners we reach have an invoice more than 45 days overdue right now" can. Every line gets a who, a number and a threshold. *Show: each line paired with the result that would prove it wrong.*

5. **Tag the dangerous ones.** For each line ask two things: how likely am I wrong, and what does being wrong cost? Email versus SMS reminders is a coin flip that costs an afternoon to reverse. Tag it "uncertain" and leave it. Whether a bookkeeper pays $39 a month per client is a coin flip that costs the company. Tag it "risky". *Show: every line tagged, with a one-line reason.*

6. **Choose where to start.** Two segments still standing? Keep the one whose people you could get on the phone this week. Park the other with a date to revisit. *Show: the kept canvas labelled Plan A, the parked one dated.*

7. **Put a number one at the top.** Sort the risky lines by what a wrong answer would cost you. The line at the top is your first test, even if it scares you. Especially if it scares you. *Show: the ordered list, number one circled.*

## Artifacts produced

- An `artifacts` row of kind `lean_canvas` for each segment you sketched, with Plan A marked in `meta`.
- The `assumptions` list on your version 0 `prfaq_versions` row, rewritten falsifiable, each tagged uncertain or risky, risky ones ranked.
- An `artifacts` row of kind `riskiest_assumption`: the top-ranked line and why it beat number two.

## Anti-patterns

- **The feature-list canvas.** Your reminder engine gets four lines and the customer's pain gets three words. That ratio should be the other way round. Maurya's post on loving the problem, not your solution, makes the case.
- **The research spiral.** Plan A turns into three days of market-sizing spreadsheets. Past an afternoon, you're polishing guesses.
- **Everyone is the customer.** The segment box says "small businesses". Keep cutting until you could message five of them by name today.
- **Wording that can't lose.** "Users will love it." "Strong demand exists." If no result could make a line false, rewrite it.
- **Ranking by comfort.** Your number one is the thing that's easiest to test, or a technical puzzle you'd enjoy. Ask whether a "no" on it would actually sink you.
- **One canvas, three audiences.** Designers, agencies and bookkeepers share one customer box. Split them and see which canvas survives.

## Gate criteria

The `stage-0-why` gate asks for a problem you care about and a PR/FAQ v0 with its assumptions listed. From this card it expects:

- A Plan A canvas whose problem box matches the problem you named.
- The PR/FAQ's assumptions, rewritten falsifiable and tagged uncertain or risky.
- One [[riskiest-assumption|riskiest assumption]], stated plainly, with the reason it ranks first.

## Sources

- Running Lean, Ash Maurya. The terms Lean Canvas and Plan A, one canvas per segment, and ranking risk before building. Read the original: https://ashmaurya.com/books
- Running Lean (1st edition), Ash Maurya. The earlier treatment of documenting Plan A and choosing where to start. Read the original: https://ashmaurya.com/books
- Lean Customer Development, Cindy Alvarez. Writing every assumption down before judging any of them. Read the original: https://www.cindyalvarez.com/lean-customer-development/
- Love the problem, not your solution, Ash Maurya (LEANSTACK blog). Why the problem box matters more than the solution box. Read the original: https://blog.leanstack.com/love-the-problem-not-your-solution/

## Sean's notes

None yet.
