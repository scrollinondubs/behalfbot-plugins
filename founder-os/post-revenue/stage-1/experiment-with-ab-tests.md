---
id: post-revenue-experiment-with-ab-tests
type: card
track: post-revenue
stage: 1
order: 3
title: Experimenting with A/B testing software
gate: post-revenue-stage-1-unkink-the-hose
submit: [text]
sources: [optimizely-academy]
author: Sean Tierney
requires: [post-revenue-find-the-leak]
teaches: [ab-testing, statistical-significance]
fits_when: [has-paying-customers, has-steady-traffic]
produces: [ab-test]
---
## What this is
An A/B test shows two versions of a page or email to different visitors at the same time and counts which one does better. Optimizely's Academy is a good teacher here: how to form a hypothesis, how much traffic you need, what statistical significance means, and how to avoid calling a winner too early.

**A test without a hypothesis is just a coin toss with extra steps.** Decide what you believe and why before you build the variant.

## What you make
One A/B test on the step you chose to fix. Your agent can build the variant and set up the tool; you write the hypothesis and decide when the test is done.

## How to submit
Write up the test: the hypothesis, the two versions, the metric, the sample size or run time you set in advance, and the result with its confidence level. Say what you will ship.

## Done when
- The hypothesis says what you change, what you expect, and why.
- You set the sample size or run time before starting, and did not stop early because one side was ahead.
- You report the result with its confidence, and call it inconclusive if it is.
- You said what you will ship or test next.

## Coach checks
- Low traffic is the usual blocker. If a page gets a few hundred visitors a month, help them test a bigger change on a higher-traffic step, or accept a well-designed test that is still running with a stated end date.
- Peeking and stopping early is the most common mistake. Ask when they decided to stop.
- Tests of tiny changes (button colour) on small traffic will not reach significance. Push toward a meaningful difference: headline, offer, page structure.
- Any tool passes, including a hand-rolled split your agent built.

## Source
Optimizely Academy, on experimentation and A/B testing. Read the original: https://academy.optimizely.com/
