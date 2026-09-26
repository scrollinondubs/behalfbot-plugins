---
id: prfaq-v2
type: framework-card
title: PR/FAQ v2: rewrite the launch from the evidence
stage: 5
gate: stage-5-position-and-story
tier: core
sources: [working-backwards]
---

# PR/FAQ v2: rewrite the launch from the evidence

## Purpose

Turn the launch announcement you guessed at in stage 0 into one that holds up. Every claim in it should trace back to something a real customer said or did. Every line that still can't be traced should be labelled as a guess.

## When to use

Use this card at stage 5. By now you have a PR/FAQ v0, a ledger of interviews and tests, and a one-sentence job and foothold segment from the sibling card "One sentence for the job, one segment for the foothold".

It's the wrong card if the job sentence or the foothold is still open. Finish those first. If you have no v0 at all, go back to "PR/FAQ v0: write the launch before the product" at stage 0.

## Principles

- PR/FAQ is Amazon's name, as Colin Bryar and Bill Carr document it, for the working backwards document: a press release for a launch that hasn't happened yet, followed by the questions people will ask about it.
- v0 was a set of bets. v2 is where you settle up on them.
- A quote you made up in stage 0 has no place in v2. Either a real person said it or it goes.
- Objections you actually heard are worth more than objections you imagine.
- Old versions stay in the ledger. The diff between them shows how much you've learned.

## Procedure

1. **Gather the inputs.** Open v0, the job sentence, the foothold segment, and every interview record and test result in the ledger. Show: one working file that links to each of them.
2. **Rewrite the headline and opening paragraph.** The headline names who the foothold customer is and the job they get done. The opening paragraph describes that job in words the customer used. For example, v0 said "AI invoicing for freelancers", and v2 says "Design agencies with under ten staff send client invoices the day a project closes, without chasing timesheets." Show: the new headline and opener next to the old ones.
3. **Swap in real quotes.** Delete every invented customer quote from v0. Replace each with a line from the ledger, attributed by role and linked to the interview record it came from. If the ledger has no quote that fits, the claim that quote was propping up is weaker than you thought. Show: each quote with its record id.
4. **Rebuild the external FAQ from objections.** Go through your interview notes and test results and pull out every pushback, hesitation, and "but what about". Turn each into a question a buyer would ask, then answer it straight. A marketplace founder might find that sellers asked "Who handles refunds?" in six of nine calls, while nobody asked about the fee structure v0 spent three answers on. Show: the question list, each tagged with the records it came from.
5. **Mark up the internal FAQ.** For each answer, add a status: confirmed (with the evidence), still assumed, or dropped. Pricing a B2B workflow tool might read "confirmed: four of five ops leads accepted $49 per seat in the pricing test", while churn stays "still assumed". Show: the internal FAQ with a status on every answer.
6. **Write the diff against v0.** List every assumption from v0 in one of three groups: died, confirmed, or still open. Then add anything new the evidence turned up. Show: the diff as its own document.
7. **Save v2 beside v0.** Keep both versions in the ledger with their dates. Never edit v0 in place. Show: both versions listed.

## Artifacts produced

- A `prfaq` artifact at version 2, with the headline and opener built from the job and foothold.
- Quote references on v2 that point to `interview` records in the ledger.
- An external FAQ where each question is tagged with the interview or test records it came from.
- An internal FAQ with a confirmed, still-assumed, or dropped status on every answer.
- A `prfaq_diff` artifact comparing v2 with v0.
- The untouched `prfaq` v0, still in the ledger.

## Anti-patterns

- **The polish pass.** v2 reads better than v0 but makes the same claims. Look at the diff: if nothing died, you edited the prose and never checked it against the evidence.
- **Ghost quotes.** A quote with no linked interview record. It is still a stage 0 invention.
- **The wish-list FAQ.** The external questions are the ones you'd like to answer, such as integrations and your roadmap. Check each question against the records. If none of them mention it, nobody asked.
- **Everything confirmed.** Every internal answer is marked confirmed. After a handful of interviews and a few tests, some answers have to still be guesses. If none are, you're hiding them.
- **Overwriting v0.** The ledger holds only one PR/FAQ, with today's date. The stage 5 reviewer has nothing to compare against, and you lose the record of what you got wrong.
- **Headline for everyone.** The headline talks about the whole market when it should name the foothold segment. If the foothold customer wouldn't recognise themselves in it, rewrite it.

## Gate criteria

The `stage-5-position-and-story` gate needs three things: a one-sentence job, a foothold segment, and a PR/FAQ v2. The first two come from the sibling card. This card supplies the v2, and the gate checks that:

- its headline and opener use the job sentence and name the foothold segment
- every customer quote links to a ledger record
- external FAQ questions trace back to objections that were actually heard
- every internal FAQ answer is marked confirmed, still assumed, or dropped
- a diff against v0 exists, and v0 is still in the ledger

## Sources

- Working Backwards, Colin Bryar and Bill Carr. This card takes the PR/FAQ format and the working backwards habit of writing the customer announcement before building, and applies them to a second draft rewritten from evidence. Read the original: https://www.workingbackwards.com

## Sean's notes

None yet.
