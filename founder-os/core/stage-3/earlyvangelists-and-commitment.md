---
id: earlyvangelists-and-commitment
type: framework-card
title: Earlyvangelist criteria and commitment signals
stage: 3
gate: stage-3-discovery
tier: core
sources: [startup-owners-manual, mom-test]
---

# Earlyvangelist criteria and commitment signals

## Purpose

Find the handful of people in your interview records who hurt enough to take a rough first version today. Then prove it, name by name, with what the conversation cost them.

## When to use

Stage 3, once your ledger holds a batch of audited interview records. Grading two interviews tells you nothing about a segment.

Wrong card if the notes haven't been audited. Run [[interviews-without-fooling-yourself]] first. Also wrong if you're still working out what to ask or when to stop interviewing - that's the sibling card *The problem interview and its exit criteria*. Pricing talk waits for stage 7.

## Principles

- [[earlyvangelist|Earlyvangelist]] is Steve Blank's word, from his Customer Development method. Talk doesn't earn the label. A freight broker who says your load-matching app "would save us hours" is a maybe. The one who emails you last month's load sheet so you can try it on real data is the one you want.
- Blank lists five tests. Each one gets its own line of proof: they have the problem, they know it, they're out looking for a fix, they've rigged up something in the meantime, and they can spend.
- The workaround is the clearest single tell. A spreadsheet with a macro, a Zapier chain, a contractor paid to do the job by hand.
- Rob Fitzpatrick's commitment and advancement: a closing next step only counts when the person spends something they would miss. That means time, reputation or money.
- Praise is free. Grade it zero.

## Procedure

1. Pull every audited interview record for the segment you are working on. Show: the list of record ids you will grade.
2. Test each record against the five criteria, one row per criterion. Next to each row, write the quote or observed fact that supports it, or write "no evidence". Show: a five-row evidence table on every record.
   Example: an ops lead at a small marketing agency who rebuilds client reports every Monday.
   - Has the problem: loses about four hours a week assembling reports.
   - Knows it: raised it before any question about reporting.
   - Hunting: trialled two dashboard tools last quarter and cancelled both.
   - Workaround: a Google Sheet with Apps Script pulling from three ad accounts.
   - Budget: already pays $60 a month for a sheet add-on and can approve up to $200 without a manager.
3. Flag someone as an earlyvangelist only when all five rows have evidence. Four out of five makes them a candidate, and the empty row becomes the next thing you need to find out. Show: a flag of yes, candidate or no on each record.
4. Read how each interview closed and grade that next step by what it cost the interviewee. Set the interview's `commitment` to none, time, reputation or money, and quote the step word for word in the notes. Show: a commitment field filled on every record.
   - None: "Looks neat, ping me when it ships."
   - Time: booked 45 minutes next Tuesday to walk you through their Apps Script.
   - Reputation: copied you into an email to their head of client services and asked them to take the call.
   - Money: offered a deposit without being asked. Record it. Asking for money belongs to stage 7.
   If one step spends two currencies, set `commitment` to the costlier one and note the other. FounderOS ranks money above reputation above time.
5. Cross-check the flag against the grade. An earlyvangelist whose interview closed at none needs a follow-up that asks for a concrete step. A strong commitment from someone with thin evidence is often a friend doing you a favour. Show: a note on each mismatch and what you will do about it.
6. Write up the earlyvangelist list. Show: each name, their five evidence rows, their commitment grade and the date you will next contact them.

## Artifacts produced

- One `audits` row per interview (`check_name` `earlyvangelist-criteria`) holding the five-row evidence table and the yes, candidate or no verdict. Set `earlyvangelist` to 1 only on a yes.
- `commitment` set on every `interviews` row, closing step quoted in the notes.
- An `artifacts` row of kind `earlyvangelists` listing each person, their segment, the evidence for every criterion, their commitment grade and the next contact date.
- A mismatch note in that artifact wherever the flag and the commitment grade disagree.

## Anti-patterns

- **The warm fan.** Loved the demo, but none of the five criteria has evidence. Tell: the evidence column holds adjectives instead of facts.
- **Budget by assumption.** "They just raised a seed round, so yes." Tell: the budget row names a company, not a person who can sign or a cost they already pay.
- **The meeting as the step.** "Great chat" gets logged as a time commitment. Tell: the field has no date, no named attendee and nothing agreed.
- **Promises graded as done.** "I know people you should meet" gets recorded as reputation before any introduction has happened. Tell: no name appears and no email has gone out. Record none until the introduction happens.
- **Everyone qualifies.** Eleven of twelve interviews are flagged yes. Tell: almost no row says "no evidence". Real earlyvangelists are rare.
- **The planted workaround.** You suggested the spreadsheet and logged the nod you got back. Tell: the workaround quote is in your words, not theirs.

## Gate criteria

The `stage-3-discovery` gate asks for audited interviews, [[commitment-signal|commitment signals]] and identified earlyvangelists. This card supplies the second and third, and it only works on top of the first.

- Every audited interview record carries a commitment grade with the closing step quoted.
- Each flagged earlyvangelist has a quote or observed fact for all five criteria, and the auditor can trace each one back to the interview notes.
- Every mismatch between flag and grade has a written note and a follow-up.

## Sources

- The Startup Owner's Manual, Steve Blank and Bob Dorf. The source of the earlyvangelist criteria and the Customer Development frame this card applies to interview records. Read the original: https://www.steveblank.com/books-for-startups/
- The Mom Test, Rob Fitzpatrick. The source of commitment and advancement, and of grading a next step by the time, reputation or money it costs. Read the original: https://www.momtestbook.com

## Sean's notes

None yet.
