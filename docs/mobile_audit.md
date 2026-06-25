# Mobile adaptation audit (2026-06-25)

How this was tested: real Chromium at **390 × 844** (iPhone-class), full-page
screenshots of every main surface, logged-in and logged-out, plus an automatic
horizontal-overflow check on each page.

**Headline:** every page fits the 390px viewport — **no horizontal scroll
anywhere**, so the base/grid is sound. The problems are component-level. They are
**dominated by the top navbar**, which is broken on mobile and appears on every
page, plus the cookie banner and a few page-specific layouts. Most page *bodies*
are already acceptable on mobile.

Priority key: **P0** = breaks/looks broken on every page · **P1** = a specific
page is hard to use · **P2** = polish.

---

## P0 — global (every page)

### 1. Navbar is overcrowded and overlaps on mobile
The top bar tries to show, in ~390px: hamburger + brand + **search box** + courses
icon + community icon + (sometimes) classes icon + notifications bell + messages
envelope + "מומלץ עבורך" + avatar + **user display name** + logout. There is **no
mobile collapse**, so items collide:
- the **search box overlaps the bell icon** (seen on the classroom page),
- **"כניסה / הרשמה" overlaps the search box** for logged-out users (seen on /search/),
- the **user name ("אבי המורה")** wraps to two lines and eats width.

This is the single biggest reason the site "feels bad" on mobile — the top of
every screen is a mess. The search box I added recently made it worse.

**Proposed fix (mobile breakpoint, ≤ ~768px):**
- Move the **search box out of the bar** on mobile — either an icon that expands a
  full-width search row under the bar, or put it inside the hamburger drawer.
- **Hide the user display name and the "מומלץ עבורך" text** on mobile (keep the
  avatar; both already live in the drawer / profile).
- Keep only the essentials in the bar on mobile: hamburger, brand, bell, avatar.
  Push courses/community/classes/logout into the drawer (they're already there).
- Guarantee min tap targets (44×44) and no overlap.

### 2. Cookie banner eats the top of every page
The consent banner renders as a 3–4 line slab at the very top on mobile, pushing
all content down on first visit.
**Fix:** a slim single-line bar on mobile (smaller text, inline "אישור"), or a
compact bottom sheet.

### 3. Welcome/intro strip adds more top clutter
On some pages a beige "ברוכים הבאים… / חזרה" strip stacks under the cookie banner,
so a phone user can see two full bars before any real content.
**Fix:** collapse/shorten it on mobile (or show once, smaller).

---

## P1 — specific pages

### 4. Lesson page: playlist sits ABOVE the video
On mobile the lesson list (all lessons + durations) renders first; you must
scroll past the whole list to reach the video you're watching.
**Fix:** on mobile, **video first**, then the playlist below (CSS order / column
reorder), or make the playlist a collapsible "שיעורי הקורס" accordion.

### 5. Class management roster table is cramped
The "תלמידים והתקדמות" table squeezes 5 columns into 390px — names wrap to two
lines, headers are tight, the view/remove controls are small.
**Fix:** on mobile, render each student as a **stacked card** (name on top;
courses / certificates / projects as labeled chips; full-width "צפייה" + "הסרה"),
instead of a table. (Apply the same pattern to any other data table.)

### 6. Showcase wall filter row is busy
The stand-filter chips + sort buttons form a multi-row cluster of small buttons
above the cards.
**Fix:** make the stands a horizontal **scroll strip** (one row, swipeable) and
move sort into a compact dropdown on mobile.

---

## P2 — polish

### 7. Galleries render one tile per row
The classroom project gallery and lesson "exhibition" show one large tile per row
on mobile; 2-up would be denser and nicer.
**Fix:** 2-column grid for gallery tiles on mobile.

### 8. Native file input shows English ("Choose File / No file chosen")
On the profile settings (avatar) and uploads.
**Fix:** style a custom upload button with Hebrew label.

### 9. Tap-target + spacing pass
Some icon-only links (footer, card action icons, the cert/trophy chips) are below
the 44px comfortable tap size on mobile.

---

## Pages that are already OK on mobile (verified)
Home, courses catalog, course detail, community hub, certificate, **profile
(new design)**, public profile, showcase cards, project detail, classroom body,
search results page, join wall, register. These need only the global P0 fixes.

---

## Not yet audited (recommend a phase-2 pass — likely worse, lower traffic)
Admin dashboard (`/admin-dashboard/`), authoring studio (`/studio/`), forum
thread view, events pages, direct messages / inbox, leaderboard, CrashTech pages.
These are data/table heavy and were out of scope for this first pass.

---

## Suggested order of work
1. **P0 navbar** (one change, fixes the worst of it on every page).
2. **P0 cookie banner + intro strip** (reclaim the top of every page).
3. **P1 lesson video-first** (core learning flow).
4. **P1 roster cards** + reusable table→cards helper.
5. **P1 showcase filters**, then **P2** polish.

> **Status (2026-06-25):** all P0/P1/P2 items above were implemented and
> verified at 390×844. See the Phase 2 pass below for the rest of the site.

---

## Phase 2 — whole-site sweep (2026-06-25)

Covers everything the first pass deferred: admin dashboard, authoring studio,
CrashTech (the full ~25-page cluster), forum thread view, tips, chat channels,
events, direct messages, leaderboard, members, classroom + per-student, and the
studio editors.

**How this was tested:** a logged-in crawler (superuser + a CrashTech-host
session) visited ~120 pages at **390 × 844**, screenshotted each full-page, and
ran an automated horizontal-overflow check on every page (`scrollWidth` vs
viewport, with the off-canvas drawer excluded). Data-/table-heavy surfaces were
then reviewed visually. The site had real seed data in every cluster (2
hackathons with 8 teams/challenges, forum threads, tips, chat channels, 4
classes, events, showcase projects), so the audited pages were populated, not
empty shells.

**Headline:** the worry that these "data/table heavy" pages would be *worse*
turned out mostly **unfounded** — they were built responsively (stacked cards,
2-up action grids, small tables that fit). Across ~45 distinct templates only
**three** real problems surfaced, all now fixed.

### Fixed

1. **Lesson pages with code blocks overflowed horizontally** (the whole page
   shifted; e.g. lessons 2 & 3). Root cause: `.lesson-layout` uses
   `align-items: flex-start` for the desktop sticky sidebar; when it stacks into
   a column on mobile the items size to *content*, so the widest line in an
   Arduino `<pre>` block stretched `.lesson-main` to ~457px. **Fix:** stretch the
   column on mobile (`align-items: stretch`) and let code blocks scroll inside
   their own box (`.lesson-main pre { overflow-x:auto }`). The video-first order
   from phase 1 is preserved.
2. **Admin / staff dashboard tables were too wide** (cost table ~481px,
   copilot "All Seats" latent). **Fix:** a global rule makes `.table` data tables
   scroll horizontally inside their card on phones (`.cls-table` excluded — it's
   already stacked cards). The page no longer scrolls; the table does.
3. **CrashTech *manage* — challenge action row overflowed** (~28px) when a
   challenge had three buttons (בונוס / עריכה / מחיקה). **Fix:** let the row wrap
   (`flex-wrap`), so the buttons drop below the title on narrow screens.

### Verified clean (no changes needed)

CrashTech detail / manage / teams / participants / judges / hardware / judge
queue / leaderboard / glory / gallery / certificate; admin alerts-config,
copilot & AI-usage & community-health dashboards; classroom + per-student;
studio home / course-editor / lesson-editor; forum thread; tips list/detail;
chat home + channels; events page + detail; direct-message inbox + thread;
members directory; community leaderboard; course certificate. None scroll
horizontally at 390px; all use cards / responsive grids / fitting tables.

### Coverage notes

EventSeries and forum *answers* had no seed rows, so the series page and a
populated thread-with-answers weren't exercised (the empty-state thread was).
Pure POST/action endpoints (votes, RSVPs, deletes, etc.) were excluded by design.
