---
id: interviews-without-fooling-yourself
type: framework-card
title: Interviews without fooling yourself
stage: 3
gate: stage-3-discovery
tier: core
sources: [mom-test, lean-customer-development]
---

# Interviews without fooling yourself

## Purpose

Leave every customer conversation with facts about what people already do, spend and put up with. Then check your notes for the flattering noise that passes for validation.

## When to use

Use it at stage 3, before and after each discovery conversation. It covers what to ask and how to audit what you heard. For how to structure the session and when you have talked to enough people, use the sibling card *The problem interview and its exit criteria*.

It is the wrong card if you do not yet know who to talk to. That is stage 2 work. It is also the wrong card once you are ready to ask for money. That comes at stage 7.

## Principles

- Rob Fitzpatrick calls it the Mom Test: ask questions that someone who loves you can't answer with a kind lie, because they're about the person's life, not your idea.
- [[past-behaviour-not-opinions|Past behaviour]] counts as evidence. Predictions about next month do not.
- What someone already pays for a workaround tells you more than any price they name for your product.
- A feature request is a clue to a motive. Chase the motive.
- A conversation that ends with no concrete next step taught you less than it felt like it did.

## Procedure

1. **Write the questions that could sink you.** Before any call, list three to five things that would change the plan if the answer went the wrong way. At least one should make you uncomfortable, such as "do agency owners already pay someone to chase late invoices?" Show: the dated question list.
2. **Turn each one into a question about the recent past.** "Would you use a tool that auto-chases invoices?" becomes "Which client paid you late most recently, and what did you do about it that week?" Show: the rewritten list, with the hypothetical version struck out next to each question.
3. **Hold the pitch until you have their story.** A clinic manager who learns you are building a no-show reminder app starts giving answers shaped to please you. Ask instead about last Tuesday's empty slots, who phoned the missing patients and how long that took. Caught yourself explaining a feature? Name the slip out loud and return to the most recent missed appointment. Show: every slip marked in the interview record, next to the question that steered the talk back to their week.
4. **Pin every generality to a date.** When someone says "we always" or "I'd probably", ask for the specific occasion: when it happened, who was involved, what it cost. Show: at least one dated incident per interview record.
5. **Dig under requests and strong feelings.** Say a designer on your marketplace asks for escrow. Ask what went wrong the last time they worked without it and how they cover that risk now. Do the same when someone sounds angry or embarrassed. Before moving on, repeat what you heard in your own words and ask what you got wrong. Cindy Alvarez recommends this, because the correction often exposes a bigger problem. Show: the stated request and the motive you found, side by side.
6. **Close with a concrete next step.** Every conversation should end with something dated that the other person agreed to do. For how much that step is worth, see the sibling card *Earlyvangelist criteria and commitment signals*. Show: the next step, or "none offered", in the record.
7. **Audit the notes within a day.** Go line by line and mark each one.
   - Compliments such as "love this" or "great idea": strike them. They carry no information.
   - Fluff, Fitzpatrick's word for generic claims, future promises and hypotheticals: flag it. Keep it only if you anchored it to a real event.
   - Answers that opened with a bare yes or no: Alvarez reads these as a sign you asked a leading question. Mark them doubtful.
   - Facts: dated events, money or hours already spent, tools in use, named people. These stay.

   Show: the marked-up record, with a count of surviving facts against struck lines.

## Artifacts produced

- One `interviews` row per conversation: who, their segment, the date, and notes holding the dated incidents, the current workaround and its cost, and the next step. Set `commitment` to what that next step costs them, or `none`.
- `audits` rows for each interview from the step 7 mark-up. Laya can pre-tag the lines; Claude confirms.
- `pains` rows taken only from lines that survived the audit as facts.
- A `big_questions` artifact that shows which questions have answers and which interviews supplied them.

## Anti-patterns

- **The warm glow.** You walk out pleased, then find your notes hold praise but no dates, amounts or tool names.
- **The survey voice.** Your questions start with "would you", "do you think" or "how likely". Every answer comes back in the future tense.
- **Demo creep.** You shared your screen "for context" and the rest of the call was about your product. Everything they said after that point is about you.
- **The wishlist backlog.** Interview notes become feature tickets with no line saying why the person wanted each one.
- **The softball set.** Every question was safe. Nothing you heard could have changed what you build next week.
- **The friendly dead end.** A pleasant chat, a "keep me posted", and no date or named follow-up.

## Gate criteria

The `stage-3-discovery` gate asks for audited interviews, [[commitment-signal|commitment signals]] and [[earlyvangelist|earlyvangelists]] identified. This card supplies the first: interview records where compliments are struck, fluff and leading-question answers are flagged, facts carry dates, and each record names its next step or says none was offered. Those recorded next steps feed the other two items, which are judged with *Earlyvangelist criteria and commitment signals*.

## Sources

- The Mom Test, Rob Fitzpatrick. This card takes the Mom Test itself, the preference for past specifics over predictions, digging under requests, and treating compliments and fluff as noise. Read the original: https://www.momtestbook.com
- Lean Customer Development, Cindy Alvarez. This card takes current behaviour as the baseline, spotting leading questions from yes-or-no answers, and repeating back what you heard so the interviewee can correct it. Read the original: https://www.cindyalvarez.com/lean-customer-development/

## Sean's notes

None yet.
