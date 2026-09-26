---
id: find-your-why
type: framework-card
title: Find your why
stage: 0
gate: stage-0-why
tier: core
sources: [start-with-why-talk]
---

# Find your why

## Purpose

One sentence on why this problem matters to you. Not a tagline. A sentence you'd defend with a straight face, backed by things you did before the idea existed, that still fits the problem and audience you picked.

## When to use

Stage 0, before or alongside your first PR/FAQ. Especially if you can walk through the product screen by screen but go quiet when someone asks why you, of all people, should spend the next two years on it.

Wrong card if you already have a why with dated evidence behind it. Go to *PR/FAQ v0*. Also wrong if you want to turn the why into taglines or a homepage. That's stage 5 and 6.

## Principles

- Simon Sinek's golden circle has three rings: why, how, what. FounderOS uses it as a founder-fit check and nothing more.
- Sinek's rule, Start With Why, means the belief comes first and the product comes after. At stage 0 the founder does not have a product yet, so the belief is all there is to test.
- Revenue is something you hope to get. It is not a reason, so a why that mentions money or a market size has not been written yet.
- Believe your history over your pitch. Past behaviour is evidence. How excited you feel today is not.
- A why that sits comfortably next to any problem or any audience is too loose to guide anything.

## Procedure

1. **Write the outer rings first.** One line for the what (the thing you plan to build). One line for the how (what will make yours work differently). *Show:* two lines.
2. **Draft the why as a belief.** One sentence, starting "I believe". No product name, no numbers, no mention of money. *Show:* the draft sentence.
3. **Test it against your past.** List three or more moments from before this idea when you acted on that belief. Each needs a rough date and what you did. A freelance bookkeeper who spent six years chasing late invoices for clients, and built spreadsheets to shame slow payers, has a list. *Show:* the dated list.
4. **Rewrite or drop.** If the list is thin, the sentence is a pitch. Rewrite the why until it matches what your history shows, even if the new version is less exciting. *Show:* the final sentence and a note on what changed.
5. **Run the fit check.** Write one line saying how the chosen problem follows from the why, and one line saying how the chosen audience follows from it. Mark each line fits, strains or breaks. *Show:* two lines and two verdicts.
6. **Defend it out loud.** Read the sentence to someone who knows your work history and ask them where it rings false. *Show:* their objection and your answer, one line each.

## Artifacts produced

- An `artifacts` row of kind `why_statement`: the final sentence, plus the what and how lines.
- An `artifacts` row of kind `why_evidence`: the dated list of past actions behind the belief.
- An `artifacts` row of kind `fit_check`: the problem line and the audience line, each with its verdict, plus the objection from step 6 and your answer.

## Anti-patterns

- **The trend pick.** The founder chose "AI scheduling for dental clinics" from a list of hot niches and has never worked with a dentist. Tell: the evidence list starts after the idea did.
- **The market-size why.** "Because it's a $4B market." That answers why an investor might care. Tell: the sentence would still work for a totally different product.
- **The retrofit.** The founder built a Chrome extension last month and is now writing a belief to justify it. Tell: every evidence item is about the product and none is about the problem.
- **The borrowed audience.** The why is about freelancers getting paid on time, but the target customer is enterprise finance teams. Tell: the fit check says strains and the founder shrugs.
- **The poster slogan.** "I believe in empowering people." Tell: you cannot tell which problem it belongs to.

## Gate criteria

The `stage-0-why` gate looks for a problem the founder cares about, backed by the `why_statement`, at least three dated items in `why_evidence`, and a `fit_check` where neither verdict says breaks. The gate also needs a PR/FAQ v0 with its assumptions listed. That comes from *PR/FAQ v0*, and it should name the problem and audience this card has checked.

## Sources

- How great leaders inspire action (TED talk), Simon Sinek. This card takes the golden circle and the Start With Why ordering and uses them only as a founder-fit test. Read the original: https://www.ted.com/talks/simon_sinek_how_great_leaders_inspire_action

## Sean's notes

None yet.
