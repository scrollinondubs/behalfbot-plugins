# FounderOS evals

Every skill and card has to earn its place. An eval runs the same task on the
same items twice: once as plain Claude, and once with a FounderOS skill or card
loaded. If the FounderOS arm does not score clearly better, the skill or card
is not helping, and we say so. Null results are published exactly like wins.

## What gets scored

Six fixture sets in `fixtures/`, all synthetic and written for these evals. No
book or course text is in them.

| Set | Stage | Items | What the model answers |
|---|---|---|---|
| `assumptions` | 0 | 5 | Which PR/FAQ assumptions are falsifiable, and which is riskiest |
| `audiences` | 1 | 6 | Is the audience line people doing a job; is the bowling pin a real subset |
| `pain-logs` | 2 | 6 | Which pain-log entries do not count as evidence, and pass/fail on the stopping rule |
| `interviews` | 3 | 8 | Fact turns, struck turns, pitch before first fact, commitment, verdict |
| `profiles` | 3 | 8 | Blank's five earlyvangelist criteria and the overall call |
| `ebombs` | 6 | 6 | Pain, dream or fix per paragraph, product mentions, premature pitch |

Each item carries its expected answer and a `note` saying why. `run_evals.py
validate` checks that every expected answer follows the set's own rules (a
verdict that contradicts the fact count fails validation), that turn and
paragraph numbers exist, and that each set has both passing and failing cases.

Subjects (`run_evals.py subjects` lists them with the files each loads):

- **every auditor skill**, with its question set and its own deterministic
  pass on the item (`scripts/audit.py` output). With a Laya URL the auditors
  also run as `+laya` subjects, whose pass includes Laya's tags.
- **one core card per set**, with the concept notes it links.
- **the stage skills for stages 0 to 3**, with the stage's cards and, for
  stages 2 and 3, the auditor they call.

All arms get the same task text, which spells out the definitions a fair judge
needs. What an arm adds over plain Claude is the method, the worked examples
and the auditor output, never the answer key.

## Scoring and the decision rule

Each item scores 0 to 1: the mean of its components (exact match on verdicts
and labels, F1 on sets of turns, entries or paragraphs). An unparseable reply
scores 0 and is kept. A subject's score is its mean over items and repeats.

- **win**: at least 0.05 above plain Claude on the same set
- **loss**: at least 0.05 below
- **null**: anything in between

The results also give the delta per repeat and how many items got better or
worse, so a win that rests on one repeat or one item is visible.

## Running it

CI runs only the deterministic half, `tests/test_evals.py`: fixture
validation, scoring, and the whole pipeline with a mocked model. It also checks
that a live run is committed and complete.

The live eval is manual. It needs a logged-in `claude` CLI and costs money:

```bash
python3 founder-os/scripts/run_evals.py live --run-id <yyyy-mm-dd>-live \
  --model sonnet --repeats 2 --jobs 8 [--laya-url http://127.0.0.1:<port>]
```

Each call is `claude -p` from an empty working directory with a replaced system
prompt, no tools and no MCP servers. It writes three files to `results/`:
`<run-id>.json` (the summary the lint reads), `<run-id>.calls.jsonl` (every
prompt hash, answer and score) and `<run-id>.md` (the table). Commit all three.

## Promotion

A card moves from `contrib/` to `core/` only with `eval: <run-id>` in its
frontmatter, pointing at a results file where `card:<id>` has verdict `win`.
The lint enforces it. The cards that were in core before this harness existed
are listed in `seed-cards.txt`; that list only shrinks. See
[`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## Caveats

- The same author wrote the fixtures, the expected labels, and (for the stage
  skills) the skills. The fixtures were written before the live run and not
  changed after it, but they are one person's reading.
- The sets are small (5 to 8 items). A 0.05 margin on 5 items is one
  component on one item. Read the per-repeat deltas before trusting a verdict.
- The task text is detailed on purpose, so plain Claude starts strong. A null
  result here means "the skill adds nothing to a well-specified task", which is
  a real finding, not a failure of the harness.
