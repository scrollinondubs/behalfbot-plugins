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

1. `get_founder(founder_id)` for their current stage and context.
2. `list_stage_progress(founder_id)` for what they have already passed.
3. The artifacts from earlier stages this stage builds on: <list them>.

If the founder's current stage is not <N>, stop and hand over to the skill for
their actual stage. Never coach ahead of the ledger.

## Current stage only

Load only the core cards for stage <N>: <card ids>. Do not mention later stages
or their frameworks, even if the founder asks. Say that it comes later and bring
them back to the work in front of them.

## Procedure

<The coaching loop for this stage: what to ask, which card to work through, what
to have the founder produce, and when to send them away to do fieldwork.>

## Ledger writes

<Every write this skill makes, and when. For example: each artifact the founder
produces, each pain entry, and a gate decision only through the gate's auditor,
never directly from this skill.>
