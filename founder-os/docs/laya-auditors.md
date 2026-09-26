# Laya auditors: how they work

Laya is a System One model: fast, narrow judgments over one piece of text. The
auditors use it for the per-item tagging that is too tedious for a founder and
too many calls for Claude. Claude confirms the tags and writes the feedback.
Gate decisions stay with Claude and Sean.

Code: `founder_audit/`. Question sets: `laya/*.json`. Skills: `skills/*/SKILL.md`.

## The endpoint

`POST $LAYA_URL/v1/systemone` with `{"state", "questions", "model"}`. laya-serve
and Ollaya both speak it. The answer is `{"model", "answers", "usage",
"routing"}`, with one answer per question: `noul` (probability of yes),
`choice` (option and probabilities) or `score` (expected level).

| Variable | Meaning | Default |
|---|---|---|
| `LAYA_URL` | base URL, e.g. `http://laya:8000` | unset: Claude-only |
| `LAYA_API_KEY` | bearer token, sent only when set | unset |
| `LAYA_TIMEOUT` | seconds per request | 20 |

## Degrading to Claude-only

`LayaClient` sorts failures in two:

- **Unavailable** (unset, unreachable, timed out, 5xx, a body that is not
  JSON, answers missing): the auditor returns `"mode": "claude-only"` with a
  `degraded_reason`, and the skill has Claude tag the items itself. The first
  failure trips the client, so a 40-turn transcript waits for one timeout, not
  40. A run is Laya or Claude-only as a whole, never half of each.
- **Rejected** (4xx): Laya understood the request and refused it. That is a
  bug in a question set or in the chunking, so it is raised, not hidden.

Pattern checks that need no model (bare yes/no answers, closed questions,
hypothetical wording, pain-log structure, Pain-Dream-Fix order) run in both
modes.

## Checkpoints, per question and per language

A question set maps a language to a checkpoint, and any question can override
the map. The pain tagger is built on the #603 run (new-jaxity
`docs/founderos/603-laya-pain-tagger.md`):

| Question | English text | Other languages | Why |
|---|---|---|---|
| `is_pain` | `english` | `multilingual` | AUC 0.78 on english vs 0.53 (chance) on multilingual |
| `money_or_workaround` | `multilingual` | `multilingual` | AUC 0.84 on multilingual vs 0.67 on english |

So English text costs two calls, one per checkpoint. Every answer carries a
`trust` level (`measured`, `weak`, `chance`, `advisory`, `unmeasured`), and
code never acts on a `chance` answer: a non-English pain log is not ranked or
flagged by `is_pain`.

The caller passes the language (`--lang`). Without it, text in a non-Latin
script is routed as non-English, and Latin text goes to the set's default
checkpoint. Laya's own language guesser is not reused because it lives in the
Laya package, not here.

## Long text is chunked, never truncated

Laya cuts a state's tail at the checkpoint's window without saying so: 512
tokens on english, 1,024 on multilingual, question included. In #603, 590 of
2,057 posts overflowed multilingual and 1,587 overflowed english, and the
longest posts held the richest pain.

`tagger.chunk_text` splits on paragraphs, then sentences, then words, to
1,000 characters for english and 2,400 for multilingual, then packs small
pieces back up to the budget. Each chunk is asked separately and answers
combine per question:

- `max` for yes/no and score questions: one painful chunk makes a painful post.
  The result names the winning chunk and quotes it as `excerpt`.
- `mean` for choice questions: option probabilities averaged over chunks.

If a chunk still reaches the window (`usage.input_tokens` per question at the
cap), the result says `truncated: true`.

## Labels

One `labels` row per item and question. `task` is `<set task>.<question>`,
e.g. `mom_test.compliment` or `pain_tag.is_pain`. `model_version` is
`laya:<checkpoint>:<set>@<version>`, which is how the export finds the exact
question text.

1. `audit.py --record` writes an unreviewed row for every tag.
2. The founder accepts or rejects tags in the session, and `labels.py`
   records it. Accept writes the model's own answer as the correction; reject
   writes the right answer (a yes/no flips). Both set `corrected_at`.
3. Only rows with `corrected_at` are exported. Unreviewed tags are never
   training data.

Labels hang on a ledger row the founder owns: the `interviews` row for a
transcript, the `artifacts` row for a draft, each `pains` row for its own
quote. Raw posts from a watering hole are not ledger rows, so ranking writes no
labels. A question whose options are filled in at run time (the pain category,
from the founder's own jobs) is not recorded, because the example cannot be
replayed without those options.

## The export is operator-only

`export_labels.py` reads every founder's reviewed labels, so it refuses to run
without `FOUNDER_OS_OPERATOR=1`, and no skill sets that. Each JSONL row holds
the question text, the input text, the model's answer, the correction and
whether they agreed. `founder_id` and ledger row ids are left out.

## Tests

- `tests/test_auditors.py` runs in CI with no network: a stand-in Laya server
  on 127.0.0.1 answers from keyword rules and, like the real one, drops the tail
  of a long state. That is how the chunking test shows a pain at the end of a
  long post is found by chunking and missed without it.
- `tests/test_laya_live.py` runs only with `LAYA_URL` set. It checks the
  auditors end to end against a real server and prints agreement with
  `tests/fixtures/expected.json`. It asserts no accuracy: no targets are set
  yet (behalfbot-plugins#28).
