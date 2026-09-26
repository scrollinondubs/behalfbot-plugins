---
id: stage-1-audience
type: gate
title: "Stage 1 gate: a named audience you can go and read"
stage: 1
signoff: claude
fail_routes_to: 1
---

# Stage 1 gate: a named audience you can go and read

> Illustrative example for the authoring templates.

## Required evidence

- One `audience` artifact naming who the audience is and what job they are
  trying to get done.
- One `watering_holes` artifact listing at least three places marked keep, each
  with a URL and dated activity notes.
- A first bowling-pin segment, recorded in the `audience` artifact, that is
  narrower than the audience itself.

## Auditor checks

- Each kept watering hole has a URL and activity notes from the last 30 days.
  (Laya can pre-tag this; Claude confirms.)
- The notes show members talking about the job, not only about the product
  category. (Claude.)
- The bowling-pin segment is a strict subset of the audience, not a rename.
  (Claude.)
- The audience line names people, not a market size or an industry. (Claude.)

## Pass/fail rubric

- **Pass:** all three pieces of evidence are present and every check holds. The
  decision cites the ids of the two artifacts.
- **Fail:** any piece is missing, fewer than three places are active, or the
  audience is a market ("SMBs", "creators") rather than people.
- **Borderline:** three places where one is barely active. Pass only if the other
  two are clearly busy, and note the weak one in the rationale.

## Failure routing

- Audience too broad or unnamed: stay in stage 1 and rework the audience line
  with `map-the-watering-holes`, step 1.
- Too few active places: stay in stage 1 and repeat steps 2 to 4.
- No problem the founder cares about behind the audience: back to stage 0.
