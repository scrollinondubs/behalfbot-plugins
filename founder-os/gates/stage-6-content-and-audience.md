---
id: stage-6-content-and-audience
type: gate
title: "Stage 6 gate: content people answer, on a channel that works"
stage: 6
signoff: claude+sean
fail_routes_to: 6
---

# Stage 6 gate: content people answer, on a channel that works

> Ruled by Sean on 2026-09-26. The minimums below are in force.

## Required evidence

- At least 4 `artifacts` of kind `ebomb`. Each has a `pains` id, a one-line promise, a live URL and at least one watering hole link.
- At least 3 `pains` rows behind each e-bomb's pain, with a distinct `source_url` on each.
- 1 `content_wall` artifact that lists every `ebomb` and the `sales_page`.
- 1 `email_list` artifact with weekly counts and a signup source for each subscriber.
- 1 `response_log` artifact with a row for every `ebomb`: replies, signups, shares, questions.
- 1 `sales_page` artifact with a URL and a version number. It has 5 to 8 pain lines, and each carries a `pains` id.
- 1 Laya `audits` row per sales page paragraph, tagging it pain, dream or fix.
- 1 `segment_test` artifact sent to 50 to 200 subscribers, dated before the sales page went live.
- 1 `traction_goal`, 1 `channel_brainstorm` with every channel row filled in, at least 2 `channel_test` and 1 `chosen_channel` artifact.

## Auditor checks

- Every `ebomb`, `content_wall` and `sales_page` URL loads. (Laya.)
- Every `ebomb` links a `pains` id that has 3 or more distinct sources. (Laya.)
- Each e-bomb still fixes its problem once every product mention is deleted. (Claude.)
- Each watering hole post answers the question in the comment itself. (Claude.)
- Every sales page paragraph has exactly one tag, and every pain line has a `pains` id. (Laya pre-tags; Claude confirms.)
- Pain lines read like the logged quotes, not founder prose. Dream lines contain no pain words. (Claude.)
- The `segment_test` send date comes before the sales page publish date. (Laya.)
- Every `channel_test` has a pass mark dated before the test began. (Laya.)
- The `chosen_channel` numbers match the signup sources in `email_list`, and most growth after the choice date comes from that channel. (Claude.)
- `response_log` and `segment_test` show replies, clicks or signups above zero. (Laya pre-tags; Claude confirms.)

## Pass/fail rubric

- **Pass:** every item is present and every check holds. The list is responsive, meaning at least 10% of the segment test's recipients replied or clicked. The decision cites the ids of each artifact and `audits` row it rests on.
- **Fail:** a required artifact is missing. An e-bomb has no quoted pain. An e-bomb pitches the product. A pain line has no source. A pass mark was set after the results came in. Or the only proof of response is opens, views or subscriber count.
- **Borderline:** clicks but zero replies. Pass only if the signups trace to e-bombs, and name the silence in the rationale.
- **Borderline:** a channel passed its test, but list growth came from somewhere else. Fail until growth after the choice date follows the chosen channel.
- **Borderline:** a segment under 50 because the list is small. Pass if the replies are specific, and note the size.

## Failure routing

- E-bomb has no quoted pain, or the pain log is thin: back to stage 2, the Sales Safari card, then `e-bombs` step 1.
- E-bomb is a product pitch or can't be followed alone: stay in stage 6, `e-bombs` steps 3 and 4.
- No watering hole delivery: `e-bombs` step 5.
- Silent list or no response log: `e-bombs` steps 7 and 8.
- Unsourced pain lines or untagged paragraphs: `pain-dream-fix` steps 1, 2 and 5.
- No segment test, or it came after publishing: `pain-dream-fix` step 6.
- Pass marks set late, or no test for an inner-ring channel: `bullseye-one-channel` step 5.
- No channel chosen, or growth doesn't follow it: `bullseye-one-channel` step 6.
