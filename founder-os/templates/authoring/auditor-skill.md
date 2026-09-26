---
name: <founder-os-slug, same as the directory name>
description: <One paragraph. What the auditor checks, and the phrases that should trigger it.>
plugin: behalfbot-founder-os
enabled_when: "chassis.config.yaml modules.founder-os.enabled == true"
type: auditor-skill
stage: <0-9, the stage whose work it audits>
# gate is optional. If set, it must be a gate in gates/.
gate: <gate id>
question_set: <name of a question set in laya/, without .json>
---

# <Auditor name>

<One paragraph: whose framework this checks against, credited, with a pointer
to the original. Laya tags each item; Claude confirms and writes the feedback.>

## When to run

<What the founder has in hand, and the ledger row to save it to first so labels
and audits have something to hang on.>

## Laya pass

<The scripts/audit.py command, with --lang, and what each field of its JSON
output means. Say how far each tag can be trusted: measured, or not yet.>

## Claude pass

<How to turn the tags into feedback: order, what to cite (turn or paragraph
numbers), and the verdict.>

## Without Laya

<What changes when the output says "mode": "claude-only": Claude tags the items
itself with the same questions, says Laya was unavailable, and writes no labels.>

## Label capture

<Which tags to show the founder, and the labels.py accept/reject commands. Only
reviewed tags become fine-tuning labels. The export is operator-only.>

## Ledger writes

<Every write: the row saved before the audit, labels, and the Claude audits row.>
