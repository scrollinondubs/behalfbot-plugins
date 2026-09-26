---
id: <stage-N-slug, same as the file name>
type: gate
title: <Stage N gate: short name>
stage: <0-9>
signoff: <claude | claude+sean; stage 3 onward must be claude+sean>
fail_routes_to: <stage number a failed founder goes back to, at most this stage>
---

# <Title>

## Required evidence

<Each item the auditor must find in the ledger, with the table or artifact kind
it lives in and the minimum count. The founder saying so is never evidence.>

## Auditor checks

<The checks the auditor runs on that evidence, one per line. Mark which ones Laya
can pre-tag and which need Claude.>

## Pass/fail rubric

<What a pass looks like, what a fail looks like, and the borderline cases. Every
decision cites the ledger rows it rests on.>

## Failure routing

<Where each kind of failure sends the founder back to, and what they need to
redo. Name the stage and the card.>
