---
id: choose-the-mvp-type
type: framework-card
title: Choose the MVP type that tests your riskiest assumption
stage: 4
gate: stage-4-solution-test
tier: core
sources: [lean-customer-development]
---

# Choose the MVP type that tests your riskiest assumption

## Purpose

Your riskiest assumption is really a question you haven't asked yet. This card picks the cheapest test that can answer it and fixes the kill result on paper before anyone sees the test.

Say you spent a weekend building a booking tool for dog groomers. You can strip that code down, fake parts of it or put a price on it. If you ship it unchanged, you learn nothing.

## When to use

Use this card at stage 4. By then the founder has a ranked assumption list from the stage 0 card 'Plan A on a Lean Canvas, riskiest assumption first' and a working app they built fast. Run it before the Sprint, because the Sprint needs to know what it is testing.

It is the wrong card if there is no ranked list. Send the founder back to stage 0. It is also the wrong card for any assumption that already has payment or usage proof. Take the next one down the list.

## Principles

- One MVP answers one question. Put two assumptions into one test and you can't read either result.
- The cheapest type that can settle the question wins, even if it uses none of your code.
- Commitment outranks interest. A signup shows curiosity. A deposit, a signed pilot or an hour of a buyer's time shows intent.
- Write the pass and fail lines before anyone sees the test. Once results are in, everything looks like a pass.
- A polished app changes what people tell you. Reshape it so they react to the idea rather than the finish.

## Procedure

1. Copy the top untested assumption from the ranked list. Rewrite it as one yes/no question about what customers will do. **Show:** the question on a single line.

2. Match the question to a type. Cindy Alvarez, in *Lean Customer Development*, sorts MVPs into six types. Each one can settle one kind of question and tells you little about the others. The names concierge MVP and Wizard of Oz MVP are hers. **Show:** the chosen type and the line below that justifies it.

- *Does one feature, on its own, bring people back?* Single-use-case. A meeting-notes SaaS switches off search, integrations and summaries, leaving only action-item extraction, and counts accounts that paste in a second transcript the next week.
- *Will buyers stay when they know a human is doing the work?* Concierge MVP. A supplier-onboarding founder chases vendor forms by email for two procurement teams and tells them it is manual. The signal is whether they forward the next vendor.
- *Will people act on a report they assume a machine wrote?* Wizard of Oz MVP. An SEO audit app shows a progress bar, and the founder writes each audit by hand that night. The number that matters is how many recommended fixes customers ship.
- *Will someone pay or sign before it exists?* Pre-order. A clinic-scheduling marketplace takes a $200 setup fee for a launch six weeks out. A hospital group signs a pilot agreement instead.
- *Does the result pull people in when stitched from existing tools?* Other people's product. A freelance-translator marketplace runs on Typeform, Google Sheets and Wise. Track second orders.
- *Do people with this problem show up and reply?* Audience-building. The app does not change. Stage 6 covers it.

3. List how the app gets reshaped for this test: what you strip out, fake, switch off or put a price on. **Show:** the reshaping list, with a before and after screenshot of the changed flow.

4. Pick the test group. If you already have users, follow Alvarez's approach for existing products: start with the handful of accounts that would be hurt if you shut down tomorrow. Those are rarely the people sending you weekly feature requests. For a CRM plugin used by 200 agencies, that might be the eight whose teams log in every day, not the two owners who keep emailing ideas.

   Some feedback bends depending on who asks. Buyers who know you from a previous launch, or who see finished-looking screens, grade you on politeness and polish.

   Alvarez's fix is incognito customer development. A payroll-tool founder with a known following on X could pitch the same idea as "Ledgerline", using grey wireframes and a bare landing page with no link back to them.

   Nothing built yet for the flow you want to test? Tell it as a scene, which Alvarez calls a storytelling demo. "Last Friday of the month. The ops lead at a 20-person agency gets a Slack ping about three overdue invoices, clicks once, and the reminders go out in the agency's own tone."

   Then watch the listener. "That's our Friday, word for word" is a match. "Invoicing lives in Xero, and nobody here reads Slack after lunch" is a correction, and just as useful. A dark-mode request is noise. **Show:** 5 to 15 named test customers and why each was picked.

5. Set pass and fail as numbers with a deadline. Example: a tool that chases late invoices for design agencies. The assumption is that agency owners will pay to stop chasing clients themselves. Pre-order test: pass if 4 of 12 owners pay a $49 deposit within ten days. Fail if fewer than 2 do. A result in between means you rerun once with a sharper offer. **Show:** the pass line, fail line and deadline, dated before launch.

6. Hand the written choice to the Sprint. The sibling card 'A five-day Sprint on the app you already have' runs the test. This card only decides what gets tested. **Show:** the completed `mvp_choice` artifact.

## Artifacts produced

- An `mvp_choice` artifact with these fields: the assumption, the yes/no question, the MVP type, the reshaping list, the test customers, the pass line, the fail line and the deadline.
- An update to the assumption's ledger entry, setting its status to "under test" and linking it to the `mvp_choice`.

## Anti-patterns

- **Shipping the app as-is.** The current build goes to friends and the founder waits. The tell is an empty reshaping list. Stage 4 will not accept it.
- **Curiosity counted as demand.** The pass line is waitlist signups, page views or "they said they'd use it."
- **Choosing the type that shows off the build.** The question is about willingness to pay, but the founder picks single-use-case because it's the one that uses the code.
- **Moving the goalposts.** The pass line was written or edited after results came in. Check the dates.
- **Two assumptions, one test.** The question line contains "and."
- **Power users as the sample.** The test group is the three people who email every week with requests. Most of your users never touch the features those three care about.

## Gate criteria

The `stage-4-solution-test` gate needs Sprint test results and an app that was reshaped, not reused as-is. From this card's work it looks for:

- an `mvp_choice` artifact dated before the Sprint started
- exactly one assumption and one MVP type
- numeric pass and fail lines with a deadline
- a reshaping list that shows visible differences between the shipped app and what test customers saw

Results must be reported against the lines set in advance, not against new ones.

## Sources

- Lean Customer Development, Cindy Alvarez. This card takes her six MVP types and what each can prove, the coined terms concierge MVP and Wizard of Oz MVP, and her techniques for customer development on a product that already exists. Read the original: https://www.cindyalvarez.com/lean-customer-development/

## Sean's notes

None yet.
