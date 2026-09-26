---
id: sprint-test-your-app
type: framework-card
title: A five-day Sprint on the app you already have
stage: 4
gate: stage-4-solution-test
tier: core
sources: [sprint]
---

# A five-day Sprint on the app you already have

## Purpose

Stage 3 proved the pain exists. Stage 4 asks whether the app you already vibecoded makes that pain go away for the people who feel it. You get five working days to find out, using the Sprint, the method Jake Knapp built with John Zeratsky and Braden Kowitz. Here it's adjusted for a founder who arrives with code instead of a blank whiteboard.

By the end of the week you have proof a reviewer can inspect and a build that looks different from the one you started with, because five target customers showed you where they clicked, stalled and quit.

## When to use

Use this card at stage 4, after the stage 3 gate has passed and you hold a short list of earlyvangelists who described the pain in their own words. It fits best when you arrive with a vibecoded app and a strong urge to demo it.

It is the wrong card if you still can't say who has the problem. Go back to stage 3. It is also wrong if your open question is which kind of MVP to run. That belongs to 'Choose the MVP type that tests your riskiest assumption'. Pricing and trimming the release come later, in 'The solution interview and cutting the MVP to what was proven'.

## Principles

- Treat the app as raw material. Reshape it around your questions.
- What someone does on the screen outweighs what they say they would do.
- One person makes the call. Two co-founders reaching consensus produce a blend that nobody tested.
- Ideas come from working alone and comparing afterwards. Group brainstorms reward the loudest founder.
- Five of the right customers are enough to see what repeats.
- Sprint questions, in the book's vocabulary, are the doubts about your app that a tester's clicks can settle.

## Procedure

Run this with one or two helpers at most.

1. **Name the Decider first.** Knapp, Zeratsky and Kowitz call this role the Decider: the one person whose call ends a debate. In a solo company that is you. With a co-founder, agree which of you it is for this week and write it down. Show: the Decider's name on the plan.
2. **Write down what the app still has to prove.** Stage 3 showed GCs fear an uninsured crew on site. It did not show your app fixes that. Maybe subs ignore texts from unknown numbers; maybe the office manager does the admin, not the owner. Write each doubt as something a tester's behaviour settles, e.g. "a sub completes an upload on a phone without calling the office". Show: three to six, each linked to an interview id.
3. **Map the route and circle one step.** Draw the path from "never heard of you" to "problem gone" in about ten boxes, left to right. For the compliance tool it might run: a GC spots a post in a contractors' Facebook group, starts a trial, uploads the sub list, subs get a text with an upload link, certificates land, and the GC walks onto site knowing every crew is covered. Ring the box your riskiest question hinges on. The rest of the week belongs to that box. Show: a photo of the map with the target ringed.
4. **Draw rivals to your own build.** The app you arrived with is one candidate, not the default. On paper, and apart from each other, you and any helper each draw another way for the sub to get from text message to finished upload. Make at least one of them look nothing like what you built. Show: the alternatives next to the current flow.
5. **Choose, then check your app against the chosen flow.** The Decider picks a winner from unsigned sketches. Now pull up every screen your vibecoded app has today and match it to a moment in the winning flow, from the GC first hearing about you to the last certificate landing. Most apps built before discovery carry settings pages, dashboards and onboarding tours that no moment needs. Mark each screen keep, change or cut. Show: the winning flow as a numbered list of moments and the keep/change/cut list.
6. **Reshape the app into a prototype (one day).** Work on a throwaway branch. Strip out login, load a seed file, and make the data believable: forty subs, two due to expire this week, one already lapsed ("Northside Roofing, expired 12 Sept"). Hide every screen the flow does not use. Polish the ones it does, because a typo or broken table turns a tester into a bug reporter. That evening, someone new to the build clicks through it start to finish while you watch and say nothing. Fix what trips them. Show: a log of screens kept, changed, cut and added, and the build link.
7. **Test with five customers, one at a time.** Invite five people from your stage 3 earlyvangelist list who match the target. Run each session as a Five-Act Interview, the structure from the Sprint authors: settle them in, ask about their current work, introduce the prototype, hand them realistic tasks, then debrief. A helper watches over screen share and writes one observation per sticky note, green for good and red for trouble. Show: five recordings or sets of session notes.
8. **Count before you conclude.** Build a grid: sprint questions down the side, the five testers across the top, notes in the cells. Empty cells are the point. A question only two testers touched is still unanswered. A behaviour counts as a finding when at least three of five showed it, for example four subs finishing the upload from the text link alone. Anything seen once or twice goes on a parked list and changes no code. Close each row with yes, no or unclear and the count. Show: the grid photo and a one-page summary.

## Artifacts produced

- `sprint_plan`: who the Decider is, every sprint question, and the customer map with the target step circled.
- `sprint_sketches` and the chosen flow with its keep, change or cut list.
- `prototype`: the build link and the reshape log.
- `interview_record` for each of the five sessions, linked to that person's stage 3 earlyvangelist entry.
- `sprint_results`: a photo of the board, the repeated reactions tagged good, bad or neutral, and a one-line verdict for every sprint question.

## Anti-patterns

- **The demo.** The founder walks the customer through the app as it stands and asks what they think. How to spot it: there is no reshape log, and the notes hold opinions instead of actions.
- **The committee.** Both co-founders' ideas end up in the prototype. How to spot it: the chosen flow has two routes to the same step, and no name sits beside the choice.
- **Polishing past the build day.** The prototype eats a second week. How to spot it: real auth, database migrations and Stripe wired in.
- **Friendly testers.** Friends, investors or other founders stand in for customers. How to spot it: testers who never appear in the stage 3 notes.
- **Rescuing the tester.** The interviewer jumps in to explain a screen when someone gets stuck. How to spot it: recordings where the founder talks more than the customer. Question craft itself lives in the stage 3 card 'Interviews without fooling yourself'.
- **Pattern of one.** One vivid reaction drives a rebuild. How to spot it: a planned change with a single sticky note behind it.

## Gate criteria

The `stage-4-solution-test` gate looks for:

- **Sprint test results.** Evidence from five solo sessions with target customers picked from the stage 3 earlyvangelist list: the photographed board, the patterns found and a verdict on each sprint question.
- **App reshaped, not reused as-is.** A reshape log showing how the tested prototype differs from the app the founder arrived with, traceable to the chosen flow and the Decider's call.

## Sources

- Sprint, Jake Knapp with John Zeratsky and Braden Kowitz. This card takes the five-day structure, the Decider, sprint questions and the Five-Act Interview, adapted for a small founding team testing an app it already built. Read the original: https://www.thesprintbook.com

## Sean's notes

None yet.
