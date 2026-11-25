---
name: saas-exit
description: Help the owner leave a hosted SaaS (course or membership platform such as Podia, Kajabi, Teachable or Thinkific, a storefront, a newsletter) for a self-hosted parity app the agent builds. Use when the owner wants to cancel a platform, says a renewal is coming up, or asks to rebuild their courses, memberships or shop on their own stack.
plugin: behalfbot-saas-exit
enabled_when: "chassis.config.yaml modules.saas-exit.enabled == true"
---

# Skill: SaaS exit

Move the owner off a hosted platform onto an app you build and run for them,
without losing a file, a customer, a link or a sale. It is often the first
project of a managed install, because the platform's annual renewal can cost
more than the install.

The order matters. Capture everything before building anything, and build
parity before building anything new.

## 1. Deadline first

- Ask when access ends: renewal date, trial end, plan downgrade, or the day the
  card stops being charged. Record it where the owner and you both see it.
- Work back from it. Capture must be complete with days to spare, because some
  of it depends on the owner's own time.
- If the deadline is close, everything below that is not capture waits.

## 2. Inventory from the platform's own list

- Start from the platform's product list, not from memory or the public site.
  Record every product with its type, price, status and **buyer count**.
- The owner decides the skip list. Typical skips: products with no buyers,
  drafts, past one-off events. Write the skip list down and get a yes on it.
- Prioritise by buyers. The product people paid for most gets captured and
  rebuilt first.
- This inventory is the checklist every later step reconciles against.

## 3. Ask where the originals live before scraping

- Before pulling a single file off the platform, ask the owner where the
  originals are: Google Drive, Dropbox, Zoom cloud recordings, their laptop,
  an old editor project.
- In the worked example most of the media already existed locally.
- Only scrape what the owner cannot find.

## 4. Capture media

- Browser automation (the chassis autopilot) can read page text and links. As
  of 2026-11 it **cannot download files and does not see hrefs in
  snapshots** (tracked in scrollinondubs/behalfbot#313). Do not plan a capture around it.
- Fastest proven path:
  1. Create one shared folder per product (Drive or similar).
  2. Give the owner a **numbered manual-download list**: one line per file,
     the direct editor URL, and the exact click path where the platform hides
     the download.
  3. The owner downloads into the matching folder.
  4. You pull the folder and **verify against the inventory**: file count per
     product, duration of each audio or video file, and names that map to
     lessons.
  5. Report gaps as a short numbered list, not a paragraph. Repeat until zero.
- Keep a manifest per product: lesson title, file name, duration, source.

## 5. Capture text and links

- Pages, sales copy, lesson text, affiliate links, email sequences, FAQs,
  testimonials, thank-you pages, checkout copy.
- A read-only autopilot walk is good for this. Capture **verbatim**, not
  summarised. The owner's words are the copy for the rebuilt pages.
- One doc per area (sales pages, lessons, emails, FAQs and testimonials,
  links). Record the source URL on each block so you can check it again.
- Collect every outbound link and every public URL of the old site. Step 8
  needs them.

## 6. Record what each product includes beyond files

- Bonuses, live calls, office hours, retreat or event details, community
  access, coaching sessions, downloadables, time limits, drip schedules.
- These are promises made to buyers. The rebuilt product page and access
  rules must honour each one, or the migration breaks a sale someone already
  made.

## 7. Exports

- Customers or audience list, with which products each customer owns.
- Invoices or sales history.
- Subscribers for any newsletter, with tags or segments.
- Store exports somewhere private and outside any repo. They are personal data.
- Optionally re-export close to cutover so nobody who bought in between is
  lost.

## 8. Cutover checklist

Work through it with the owner and tick each line:

- [ ] URL redirects from every old public link to its new page
- [ ] Discount and coupon codes recreated, or retired on purpose
- [ ] Affiliates: links, rates, payout terms carried over or wound down
- [ ] Email automations and sequences rebuilt and tested
- [ ] Payment processor connected; active subscriptions moved or recreated
      without double-charging anyone
- [ ] Every existing customer has access to exactly what they bought
- [ ] Welcome email to existing customers: where to log in, what changed
- [ ] DNS switched; old platform domain settings removed only after the new
      site is verified live
- [ ] Optional final re-export from the old platform (step 7)
- [ ] Cancel the old plan only after all of the above

## 9. Build order

- **Parity first.** Everything the old platform did for buyers works on the
  new app before any new feature ships. New ideas go on a list for after
  go-live.
- **Design first, with a sign-off gate.** The owner approves the look on
  static pages before backend work starts. Changing direction after the data
  model exists is expensive.

## 10. Design rounds

- Before any design work, ask the owner for **3 to 5 references**: their own
  existing sites and sites they like the feel of.
- Extract the shared traits and write them down: photography style, display
  typeface, accent colour use, whitespace, density.
- Ask up front: light or dark, which accent colour, any fonts or colours to
  avoid.
- Present **3 directions**, each with desktop and phone screenshots.
- Label any AI-generated stand-in photos as stand-ins, so the owner judges
  layout and not a photo that will be replaced.
- Check text contrast meets WCAG AA in every direction.
- In the worked example abstract briefs produced two rejected rounds before
  the owner's references were used.

## 11. Read-only on the old platform

- Never press Save, Publish, Delete or any toggle on the old platform. Open
  editors only to read or download.
- Change nothing there until cutover. Buyers are still using it.
- If a capture path needs a settings change, stop and ask the owner.

## 12. ROI framing for the owner

- Put the two numbers side by side: the platform's annual cost, including
  transaction fees and add-ons, against the managed install.
- The agent's other work (email triage, content, research, operations) comes
  on top, so the comparison is not like for like. Say so plainly and let the
  owner draw the conclusion.

## Worked example: a Podia exit (2026-11)

The owner sold courses on Podia with a fixed date when access ended.
Asking where the originals lived (step 3) showed most media already existed
locally. What could not be found was captured by the owner from a numbered
download list into per-product Drive folders, then verified by the agent
(step 4). Page text and links came from a read-only autopilot walk (step 5).
Design ran two rejected rounds from abstract briefs before the owner's
references were used (step 10).

## Vendor notes

### Podia

- Lesson editor: to reach an audio lesson's file, click the **waveform icon**,
  not the lesson name.
- The download is **"Download audio file"**, under the player.
- The **Files** page may not load. Fall back to per-lesson downloads.
- Course structure exports as text only. Use it as the inventory skeleton for
  step 2, not as a media export.

Add a section here for each new platform: where the downloads hide, what
exports exist, and what does not work.
