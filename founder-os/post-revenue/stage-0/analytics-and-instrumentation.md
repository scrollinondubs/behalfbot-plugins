---
id: post-revenue-analytics-and-instrumentation
type: card
track: post-revenue
stage: 0
order: 2
title: Analytics and instrumentation setup
gate: post-revenue-stage-0-lifecycle-basics
submit: [text, link]
sources: [startup-metrics-for-pirates, lean-analytics, sean-ellis-pmf]
author: Sean Tierney
requires: [post-revenue-intro-to-lifecycle-marketing]
teaches: [aarrr, one-metric-that-matters, instrumentation]
fits_when: [has-paying-customers, has-website]
produces: [metrics-dashboard]
---
## What this is
Dave McClure's Startup Metrics for Pirates names five stages: Acquisition, Activation, Retention, Revenue, Referral. AARRR, said like a pirate. It is the same idea as lifecycle marketing seen through numbers: an increasing continuum of engagement, with a metric at each step.

This card is practical. You set up a real analytics system that tells you how many people reach each step. Vibecode Lisboa uses Amplitude. Mixpanel, KISSmetrics and Google Analytics all work too. Pick one and move on. **Your agent does the wiring; you decide which events matter.**

Lean Analytics adds one discipline worth borrowing: pick the one metric that matters most right now, and set the number you would call good before you look at it.

## What you make
A working dashboard with a number for each of the five AARRR stages, the events behind each number, and the one metric you will watch most closely for the next month.

## How to submit
Write which tool you chose, the event or query behind each of the five stages, and your one metric with its target. Add a link or screenshot link to the dashboard if you can share it.

## Done when
- Each of the five stages has a definition you wrote down (for example, "activated means created a first project within 7 days").
- The dashboard shows real numbers from real users, not test data.
- You named one metric to watch and the number that would count as good, written before you looked at the current value.
- You checked one number against reality, such as comparing the revenue figure with your payment provider.

## Coach checks
- Vanity metrics (page views, total sign-ups ever) fail as the one metric. Push toward a rate or a cohort number that can move week to week.
- Activation is the stage founders define most loosely. Make them name the moment a new user first gets real value.
- If the referral stage has no event yet, accept a written definition and a note on how it will be tracked.
- The reconciliation check matters: tracking that silently drops events is worse than none. Ask what they compared and what they found.
- Do not demand a specific tool. Any tool that reports the five numbers passes.
- If they have enough users, the Sean Ellis question ("how would you feel if you could no longer use this?") is a good optional add for retention. Do not require it.

## Source
Dave McClure, Startup Metrics for Pirates: AARRR! (500 Startups, 2007), with ideas from Lean Analytics (Alistair Croll and Benjamin Yoskovitz) and Sean Ellis on product/market fit. Read the original: https://www.slideshare.net/slideshow/startup-metrics-for-pirates-long-version/89026
