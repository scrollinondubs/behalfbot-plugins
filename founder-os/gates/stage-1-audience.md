---
id: stage-1-audience
type: gate
title: "Stage 1 gate: a named audience you can go and read"
stage: 1
signoff: claude
fail_routes_to: 1
---

# Stage 1 gate: a named audience you can go and read

> Ruled by Sean on 2026-09-26. The minimums below are in force.

## Required evidence

- **`artifacts` kind `audience`, exactly 1 current row.** It holds a behaviour line naming role, recurring job and current spend. It also holds the scoring table (at least 5 candidates) and at least 5 named audience members. A "yes" in the scoring table doesn't count as a name.
- **`artifacts` kind `parked_idea`, 1 row** if the founder came in with an app. Otherwise 0.
- **`artifacts` kind `watering_holes`, 1 row** with at least 3 places marked keep. Each needs a URL, a type, an activity note dated within 30 days of the audit and an on-topic reason. The row's `meta` holds the search sheet (at least 5 entries per column) and a longlist of at least 10 URLs.
- **`bowling_pin` entry in the `audience` row's `meta`, 1 entry.** It needs the one-line pin and at least 5 scored candidates with one line of evidence per score. It also needs 10 names or handles from inside the pin, 2 next pins with a stated link each, and a reason for every runner-up.
- **`audits`, 1 row per check below**, written against the artifact ids.
- `pains`, `interviews` and `prfaq_versions`: none required. Rows there don't make up for anything missing above.

## Auditor checks

- The `audience`, `watering_holes` and `bowling_pin` evidence exists and meets every count above. (Laya pre-tags.)
- Every kept watering hole has a URL and an activity date within 30 days. (Laya pre-tags.)
- Each next pin has a non-empty link field. (Laya pre-tags.)
- The audience line describes people's work. It is not a market ("SMBs"), a demographic ("Gen Z") or a product feature. (Claude.)
- The audience wasn't reverse-fitted to the parked app. The line reads as a job the founder knows, not the app's pitch. (Claude.)
- The activity notes show members replying to each other, and the talk is about the audience's job. A vendor help forum fails this. (Claude.)
- At least one kept place came from searching, not from the founder's own feed. (Claude.)
- The pin is narrower than the audience, not a rename. Its members plausibly know each other. (Claude.)
- Pain and Connected scores cite posts, conversations or complaints, not guesses. (Claude.)
- Each pin link is a real tie: shared members, a tool, an event or a supplier. "Then everyone else" fails. (Claude.)

## Pass/fail rubric

- **Pass:** every count is met and every check holds. The decision cites the `audience` and `watering_holes` artifact ids, the `parked_idea` id if there is one, and the `audits` row ids.
- **Fail:** any count falls short, or any Claude check fails. Common fails: an audience line that could head a pitch deck, fewer than 3 kept places with fresh dates, or a pin that is still a job title. The decision names the failing `audits` rows.
- **Borderline, stale date:** a kept place was active but was last checked more than 30 days ago. Don't route. Ask for a re-check and re-audit that row.
- **Borderline, handles only:** the 10 pin names are handles only. Pass if they show up in threads in the kept watering holes. Flag them if they don't.
- **Borderline, posted already:** the founder has posted in a watering hole. The place still counts. Flag it in the rationale so stage 2 weights what it reads there with care.
- **Borderline, weak second pin:** the first next pin has a solid link and the second is vague. Pass with a flag only if every other check is clean.

## Failure routing

All failures stay in stage 1.

- Audience line reads like an industry, an age group or the app's pitch: `audience-first`, step 3.
- No parked paragraph when an app exists: `audience-first`, step 1.
- Fewer than 5 named members: `audience-first`, step 4.
- Fewer than 3 kept places, or a thin search sheet: `find-the-watering-holes`, step 1.
- Stale dates or no member-to-member replies: `find-the-watering-holes`, step 4.
- Off-topic places or vendor showrooms: `find-the-watering-holes`, step 5.
- Scores without cited evidence: `first-bowling-pin`, step 2.
- Pin too wide, not a subset, or fewer than 10 names: `first-bowling-pin`, step 3.
- Missing or vague next pins: `first-bowling-pin`, step 4.
