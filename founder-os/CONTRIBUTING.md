# Contributing to FounderOS

FounderOS takes outside cards. It also stays small on purpose. A coach that
loads forty cards per stage gives a founder forty things to read instead of one
thing to do. The rules below are how both of those can be true at once.

The repo-wide rules still apply: DCO sign-off, no credentials, and the rest of
the root [`CONTRIBUTING.md`](../CONTRIBUTING.md). This file covers what is
specific to FounderOS content. The file formats are in
[`templates/authoring/README.md`](templates/authoring/README.md).

## Core and contrib

**`core/` is the only content the coach loads.** It is curated and small, and
the maintainer is its code owner (see [`.github/CODEOWNERS`](../.github/CODEOWNERS)).
Gate specs in `gates/` and the card budget in `budget.yml` are owned the same
way, because changing either one changes what every founder is held to.

**`contrib/` is open to PRs.** It is where new cards land. Founders never see
contrib content unless the operator sets `include_contrib: true`. A contrib card
still has to pass the lint, credit its sources and be original writing, but it
does not need to name a gate or win an eval to get merged.

If you are unsure where something goes, it goes in contrib.

## Every core card names the gate it serves

A core card sets `gate:` in its frontmatter to the id of a gate spec in
`gates/`. The gate is the reason the card exists: it is the evidence the card
helps a founder produce. A card that does not move a founder through a gate
belongs in contrib.

The lint fails a core card with no `gate:`, and a card of any tier that names a
gate that does not exist.

## The card budget

Each stage holds a fixed number of **lead cards**. A lead card is a framework
card in `core/`. Concept notes do not count, and neither does anything in
contrib.

The budget lives in one file, [`budget.yml`](budget.yml). The default is 3 per
stage. A single stage can be given its own number:

```yaml
default: 3
stage-4: 4
```

When a stage is full, **promoting a card means demoting another one in the same
PR.** The lint counts core cards per stage and fails the PR if any stage is over
budget, so "we'll trim it later" cannot get merged. Raising the budget is a
change to `budget.yml`, which is code-owned and needs its own reason.

## Promotion from contrib to core

A card moves into core only with a passing eval showing it beats plain Claude
on the gate it serves. The eval harness is
[behalfbot-plugins#28](https://github.com/scrollinondubs/behalfbot-plugins/issues/28)
and has not landed yet. Until it does, nothing is promoted from contrib.

Cards carry an optional `status:` that tracks where they are in that process:

| `status` | Where | Meaning |
|---|---|---|
| `draft` | contrib | Merged, not yet proposed for core. The default if `status` is left out. |
| `candidate` | contrib | Proposed for core, waiting on an eval. |
| `core` | core | In the coach. |

Setting `status: core` does not promote a card. Moving the file does. A card
under `contrib/` that says `status: core` fails the lint, and so does a card
under `core/` that says anything else.

A promotion PR:

1. moves the card from `contrib/` to the matching place in `core/` and sets
   `tier: core`
2. adds `gate:` if the card did not have one
3. links the passing eval run in the PR body
4. demotes a card from the same stage if the stage is at its budget, and says
   which one in the PR template's FounderOS section

A demoted card moves back to `contrib/` with `tier: contrib`. It is not deleted.

## Use each source's own terms

When a card draws on a framework, **use the author's coined terms, credit them
and link to the original.** Sales Safari stays Sales Safari. The Mom Test stays
The Mom Test. Never rename a mechanism, and never repackage one under a new
label of our own.

Here's the thing: FounderOS should send founders to these sources. A founder who
meets "Sales Safari" in a card can find Amy Hoy and Alex Hillman's material and
buy it. A founder who meets our made-up name for it cannot. Keeping their names
makes us a source of leads for the people whose work this is built on.
Renaming it takes that away from them.

So in practice:

- the first use of a coined term in a card links to the original
- the card's `Sources` section credits the author and has a "read the original"
  link
- a new source gets a row in [`ATTRIBUTION.md`](ATTRIBUTION.md) in the same PR

## No source text

Cards are original synthesis with attribution. No text from a book, course or
paid product goes into this directory, in core or in contrib. A short phrase in
quotes with credit is fine. Paraphrasing a chapter paragraph by paragraph is not
original synthesis, and it is a review blocker.

Write what the founder should do and why, in your own words, then point at the
source for the full argument.

## What CI checks

`scripts/lint_content.py` runs in `validate.sh`, and its test suite runs in the
plugin-tests CI job. For governance it fails when:

- a stage has more core lead cards than `budget.yml` allows
- `budget.yml` is missing or malformed
- a core card names no gate, or any card names a gate that does not exist
- a card in `contrib/` has `status: core`, a core card has another status, or a
  status is not one of the values above

Run it locally before you push:

```bash
python3 founder-os/scripts/lint_content.py
python3 founder-os/tests/test_lint_content.py
```

## The PR template

The repo's PR template has a FounderOS section. For any change to FounderOS
content, answer both questions:

- **Which gate does this move a founder through?**
- **Which core card does this displace, if it's going into core?**

If you cannot answer the first one, the card belongs in contrib.
