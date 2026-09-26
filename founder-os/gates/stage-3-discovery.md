---
id: stage-3-discovery
type: gate
title: "Stage 3 gate: interviews that could have said no"
stage: 3
signoff: claude+sean
fail_routes_to: 3
---

# Stage 3 gate: interviews that could have said no

> Draft. It exists so the first stage 3 core card has a gate to serve. The
> minimum counts are placeholders until the other two stage 3 cards land: the
> problem interview and its exit criteria (Running Lean) and earlyvangelist
> criteria and commitment signals (Startup Owner's Manual).

## Required evidence

- **Audited interviews.** At least 10 rows in `interviews` from the founder's
  target segment (placeholder count). Each one has `audits` rows from the
  line-by-line audit in `interviews-without-fooling-yourself`, step 7.
- **A next step on every interview.** The interview notes record what the
  person agreed to do next, or say "none offered".
- **Commitment signals.** At least 3 interviews where `commitment` is `time`,
  `reputation` or `money` (placeholder count). The notes say what the step
  cost the interviewee.
- **Earlyvangelists identified.** At least 1 interview with `earlyvangelist`
  set, backed by an audit that checks it against the earlyvangelist criteria.
- **Answered big questions.** A `big_questions` artifact showing which
  questions have answers and which interview ids supplied them.

The founder saying any of this happened is never evidence. Only ledger rows count.

## Auditor checks

- Every interview holds at least one dated incident from the person's own
  recent past, not an opinion or a prediction. (Laya pre-tags each line;
  Claude confirms.)
- Compliments are struck and fluff is flagged, and neither is counted as
  evidence anywhere downstream, including `pains`. (Laya pre-tags; Claude
  spot-checks at least three interviews.)
- Answers that open with a bare yes or no are marked doubtful. (Laya pre-tags;
  Claude confirms.)
- At least one big question could have killed the idea, and the artifact shows
  how it was answered. (Claude.)
- Each commitment names a real cost to the interviewee. "Keep me posted" is
  `none`. (Claude.)
- Each earlyvangelist is supported by interview evidence, not the founder's
  impression of the call. (Claude, then Sean.)

## Pass/fail rubric

- **Pass:** every required item is present and the spot-checked audits hold
  up. Claude recommends and cites the interview, audit and artifact ids. Sean
  signs off, as for every gate from stage 3 on.
- **Fail:** interviews without audits, interviews with no dated incidents,
  missing next steps, no commitment that cost anyone anything, or no
  earlyvangelist with evidence behind them.
- **Borderline:** strong, well-audited interviews where every commitment is
  cheap. Hold the gate and send the founder back for follow-up conversations
  that end in a bigger ask.

## Failure routing

- Interviews unaudited or full of opinions: stay in stage 3 and redo the audit
  with `interviews-without-fooling-yourself`, step 7.
- Questions about the future or the product rather than the person's past:
  stay in stage 3 and rewrite them with `interviews-without-fooling-yourself`,
  steps 1 and 2, before booking more calls.
- Nobody commits to anything: stay in stage 3 and run follow-ups that end in a
  concrete ask.
- Interviewees do not recognise the problem at all: back to stage 2 and the
  pain log.
