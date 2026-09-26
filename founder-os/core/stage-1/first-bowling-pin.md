---
id: first-bowling-pin
type: framework-card
title: First bowling-pin segment
stage: 1
gate: stage-1-audience
tier: core
sources: [bowling-pin-strategy, running-lean]
---

# First bowling-pin segment

## Purpose

Pick one small group inside your audience that you can win outright, and write down the two groups that win will open up next. You leave with a first pin and a short chain behind it.

## When to use

Stage 1, once you have a named audience and a few active [[watering-hole|watering holes]]. It turns "freelance bookkeepers" into "bookkeepers in the UK who run payroll for restaurants", plus the next two groups to go after.

Wrong card if you can't name the audience yet. Go to *Audience first, product second*. Don't know where they talk? Run *Watering holes: find where they already talk* first. How you pitch your [[foothold]] to the market is stage 5.

## Principles

- The [[bowling-pin|bowling pin]] strategy, in Chris Dixon's version of Geoffrey Moore's idea from *Crossing the Chasm*: win one tight group completely, then use that win to knock over the groups next to it.
- A pin is a group whose members know each other. A list of people who happen to share a job title is not a pin.
- Winning a small group outright beats being a minor option in a big one. Fifty users who all talk to each other are worth more than five hundred scattered strangers.
- The first pin has to hurt enough to put up with a rough early product.
- Choose the first pin by what it lets you reach next as well as by how big it is.

## Procedure

1. **List the candidates.** Using your named audience and the watering holes you kept, write down five to eight narrower groups inside it. Cut by role, trade, region, tool stack or company size. A scheduling SaaS for clinics might list solo physios, dental group practices, vet clinics in one state, and clinics already on a certain practice-management system. *Show: the candidate list.*

2. **Score each candidate on four tests.** Give each a 1 to 5 score:
   - **Connected.** Do members talk to each other in one place you can point to, such as a Slack, a subreddit or an annual meetup?
   - **Pain.** Is the problem bad enough that they would take a half-built tool and send you bug reports instead of leaving?
   - **Standing.** Do you already have a way in there: a past job, a friend who is a moderator, a reputation?
   - **Spread.** Do these people also belong to other groups you want later?

   Following Ash Maurya's advice in *Running Lean*, weight the tests instead of adding them up flat. Pain and your ability to reach them come first. How big the group is comes last. *Show: a scored table with one line of evidence for each score.*

3. **Pick the first pin and write it in one line.** Take the top scorer. Then check it is small enough that you could name most of the people who matter in it. "Etsy sellers" fails. "Etsy sellers of hand-dyed yarn who run preorder drops" passes. *Show: a one-line pin statement plus ten real names or handles from inside it.*

4. **Name the next two pins.** For each one, write down the actual link that will carry your win across: people who belong to both groups, a tool both use, an event both attend, a supplier they share. Say a freelance-translator marketplace starts with legal translators working German to English. Legal translators in other language pairs sit in the same professional association, and law firms that hire them also buy certified financial translation. *Show: a three-pin chain with the link written on each arrow.*

5. **Record the losers too.** Note why the runners-up lost, so you can revisit them when the first pin stalls. *Show: the full ranking saved to the ledger.*

## Artifacts produced

- A `bowling_pin` entry in the `audience` artifact's `meta`: the one-line first pin, its four scores with evidence, and the ten names.
- The pin chain in the same entry: the next two pins, each with its link to the one before it.
- The ranked runners-up, each with a one-line reason it lost.

## Anti-patterns

- **Biggest pin first.** The chosen segment is the one with the largest market figure. Tell: the Connected and Standing scores are low and the pitch deck number is high.
- **The island.** The pin scores well but the next-two column is empty or vague ("then everyone else"). If a win there reaches no one, it is a customer group, not a pin.
- **The unreachable pin.** You picked a group you have no route into. Check whether you can name even three of its members without searching.
- **Too wide to win.** The pin is still a job title. If its members would not recognise each other's names, narrow again.
- **Pain on paper.** The Pain score comes from what you imagine, not from threads you read in the watering holes. Every score should cite a post, a conversation or a complaint.

## Gate criteria

The `stage-1-audience` gate looks for a first bowling-pin segment that is clearly narrower than the named audience and connected enough that its members know each other. It expects the scored ranking behind the choice and two next pins, each with a stated link. The named audience and the three or more watering holes come from the sibling cards and are checked alongside it.

## Sources

- The bowling pin strategy, Chris Dixon. Where this card gets the idea of winning a narrow, connected niche first and hopping to its neighbours, along with the tests for a good starting group. Read the original: https://cdixon.org/2010/08/21/the-bowling-pin-strategy
- Running Lean, Ash Maurya. Where this card gets the habit of breaking a broad customer group into candidates and ranking them with pain and reach weighted highest. Read the original: https://ashmaurya.com/books

## Sean's notes

None yet.
