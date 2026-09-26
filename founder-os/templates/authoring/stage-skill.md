---
name: <founder-os-stage-N-slug, same as the directory name>
description: <One paragraph. What the skill does and the phrases that should trigger it.>
plugin: behalfbot-founder-os
enabled_when: "chassis.config.yaml modules.founder-os.enabled == true"
type: stage-skill
stage: <0-9>
gate: <id of this stage's gate in gates/>
---

# <Stage N: Name>

## Read the founder context first

Before saying anything, load the founder from the ledger:

1. `stage.py context --founder-id <id>` for their current stage, context,
   progress and gate history.
2. The artifacts from earlier stages this stage builds on: <list them>.

If the founder's current stage is not <N>, stop and hand over to the skill for
their actual stage. Never coach ahead of the ledger.

## Current stage only

Load only the core cards for stage <N> (`stage.py cards` lists them): <card ids>. Do not mention later stages
or their frameworks, even if the founder asks. Say that it comes later and bring
them back to the work in front of them.

## Procedure

<The coaching loop for this stage: what to ask, which card to work through, what
to have the founder produce, and when to send them away to do fieldwork.>

## Gate submission

<How the skill hands over to the gate. Always the same four moves, through
scripts/stage.py: `submit` counts the gate's `evidence:` minimums and marks the
stage gate_pending; Claude rules on every auditor check in the gate spec, one
audits row per check against the submission artifact; from stage 3, Sean signs
off himself (operator-only); `decide` records pass or fail, and a fail routes
the founder to the stage the gate's failure routing names. The founder's word
is never evidence.>

## Ledger writes

<Every write this skill makes, and when. For example: each artifact the founder
produces, each pain entry, and a gate decision only through the gate's auditor,
never directly from this skill.>
