# Skills

Every skill is one directory, `skills/<name>/SKILL.md`, because that is the
only place chassis skill discovery looks (see `docs/MANIFEST.md` at the repo
root). Each one is listed in `contracts.skills` in `openclaw.plugin.json`, and
`scripts/lint_content.py` fails when the two disagree. There are three kinds.

| Kind | `type:` | Names | Gate |
|---|---|---|---|
| Stage skill | `stage-skill` | `founder-os-stage-<N>-<slug>` | Walks a founder through one stage and hands over to its gate |
| Auditor skill | `auditor-skill` | `founder-os-<auditor>` | Judges one kind of evidence; a stage skill calls it |
| Coach skill | `coach-skill` | `founder-os-coach-<name>` | None, ever |

## Coach skills

Coach skills can be used at any FounderOS stage. They gate nothing. They never
pass or fail a founder, and they write nothing to the gate record. A coach
reaches for one when a founder gets stuck on something outside the current
stage's cards: blaming others for a miss (`founder-os-coach-extreme-ownership`),
too many priorities (`founder-os-coach-the-one-thing`), a decision going in
circles (`founder-os-coach-mental-models`), or a need for the right thing to read
(`founder-os-coach-pg-essays`).

The lint checks them like any other skill: frontmatter, `plugin`, the name
matching the directory, and a manifest entry. It also fails a coach skill that
names a `gate` or a `stage`, since it has neither.
