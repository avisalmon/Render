# QA Session — Avi's walkthrough feedback (TEMPORARY)

> **Temporary working file.** Captures raw QA feedback from Avi's manual
> walkthrough of babook.co.il. Each item is logged verbatim as Avi reports it.
>
> **Process:** once the list is complete, this becomes a proper epic — every
> item gets a spec REQ, a backlog feature, and tests, fixed the_manager.md way
> (TDD → regression → deploy). When all items are DONE and traced into
> spec/backlog, **this file is deleted.**
>
> Started: 2026-06-13. Status: **CAPTURING** (Avi is walking the site).


## ⚡ Build status (EPIC-7, 2026-06-13) — updated as built

**DONE + deployed:** QA-5,9,10,11,12,13,15,17,18,20,22 (quick wins, SPR-7.1);
QA-1,2,3,4,6 + tone (onboarding rework, SPR-7.2); QA-19 (contact email, SPR-7.6);
QA-13 (9 matazim intros live, SPR-7.3). Bugs: BUG-1 fixed.

**PARTIAL:** QA-7 + QA-21 (Khan light theme + toggle built & live behind the
toggle; **dark stays default until Avi previews & confirms**, then flip). QA-8
(animated bg) deferred.

**PENDING (supervised):** QA-14 re-transcription — tooling built & tested;
the hundreds-of-lessons batch is a supervised run (OpenAI cost + quality review).

**ACTs for Avi:** (1) preview the light theme via the nav sun/moon toggle →
confirm to make it default; (2) set `CONTACT_NOTIFY_EMAIL` env var + privacy@/
support@ forwarding; (3) approve running the re-transcription batch.

---
## Items

| QA-ID | Where (page/flow) | Feedback (verbatim intent) | Severity | Status |
|---|---|---|---|---|
| QA-1 | Signup (email/password path) | **Email must be mandatory at signup.** Today a username+password signup (not Google) can have no email logged → anyone can fake "I forgot password" (security hole). An email is required info *before* the account is created. **DECISION (Avi): real email-verification link** for password signups — must be reliable. Google signups can stay trusted (verified by Google). I.e. set `ACCOUNT_EMAIL_VERIFICATION` to require confirmation for the email/password path. | High (security) | CAPTURED |
| QA-2 | `/welcome/` onboarding | **The basics step must NOT be a form — make it an AI chat.** Avi Bot conversationally welcomes the user, asks their **name**, **verifies/confirms the email**, and asks their **role**: student / teacher / professor / industry engineer / other. All in chat, not a static form. | Medium | CAPTURED |
| QA-3 | `/welcome/` onboarding | **Same chat continues**: introduce the site, drop the book-site joke (not really a book-sharing site), and ask the new user's **interests**. **Remember** what he shares — as user attributes and/or a general free-text description on the profile. | Medium | CAPTURED |
| QA-4 | `/welcome/` onboarding | **Finishable anytime + no nagging.** A clear "I'm done with the interview" button. The **only hard-required field is the name** (email is enforced at signup per QA-1). Everything else is optional/skippable. | Medium | CAPTURED |
| QA-5 | Profile (post-onboarding) | Offer/mention that **later the user can go to their profile** to add more — pictures, hobbies, more info. This is **explicitly NOT part of the entry questionnaire**; the entry chat stays short. | Low | CAPTURED |
| QA-tone | `/welcome/` onboarding | Cross-cutting: the whole entry experience must feel **very welcoming, as if Avi is personally talking** (his image present), while clearly stating it's a bot — "Avi Bot". | (applies to QA-2/3/4) | CAPTURED |
| QA-6 | `/welcome/` AI chat — opening line | The **first message must be a FIXED, instant greeting** (hardcoded, NOT AI-generated — no latency, always identical), personalized with the user's **first name** (assume first-name-first, e.g. «יורם» from «יורם חמש»). Exact copy below. The current AI-generated opener is too long/variable. | Medium | CAPTURED |

### QA-6 — exact opening copy (verbatim, hardcoded)

> אהלן [יורם]. איזה כיף שהצטרפת לאתר. זה אתר לשיתוף ספרים אבל מכיוון שעוד לא
> מימשתי שיתוף ספרים יש פה הכל פרט לזה. הדרכות בנושאים טכנולוגיים, בינה מלאכותית
> והובלת חדשנות. קהילת משתמשים ושיתוף ידע, נושאים שמעניינים אותי ובתקווה יעניינו
> גם אותך. תוכל לספר לי איך הגעת לך ומה תהיה מעוניין ללמוד כאן?

`[יורם]` is a **dynamic placeholder, never literal** — it is filled with the
**name the user supplied in the preceding intro step** (first token of that
name, assuming first-name-first). So the greeting is fixed/instant in wording
but the name slots in from the prior introduction. After this opener, the AI
takes over conversationally (per QA-2/3).

> **Sequencing implication:** the name must be known *before* this fixed
> greeting renders. So the flow is: capture the name first (the "prev intro" —
> at signup or a first name prompt), THEN show this personalized fixed opener,
> THEN the AI continues. To reconcile with QA-2 (basics-in-chat): the very
> first thing the chat asks is the name; once given, this fixed greeting fires
> with it; the conversation proceeds from there.

| QA-7 | Theme / global | The site is now dark/black (fine as a default). Add a **theme switch: Dark (current) + Light**, reachable from the **menu or the profile page**. User's choice persists. | Medium | CAPTURED |
| QA-8 | Profile / global | Add a **dynamic animated background** the user can pick in their **profile** — e.g. moving gears/wheels, stars, or other cool options. Driven by user preference, applied site-wide. | Low/Nice | CAPTURED |
| QA-9 | Nav (top bar, near user) | **Remove the EN / English language toggle.** The site is **Hebrew/RTL only** — no option to switch to English. Drop the switcher from the UI entirely. | Low | CAPTURED |
| QA-10 | Nav (user item) | Show the user's **name** (the display_name captured in the intro, e.g. «יורם»), **not the username**. Use the username **only as a fallback** when no name was captured. If the user has an **avatar**, show it as a **circle** next to the name. | Low | CAPTURED |
| QA-11 | Nav (recommendations ⭐ icon) | The stars icon (links to personal recommendations) is **unclear — users won't know to press it**. Add a **visible text label** next to the stars, e.g. «מומלץ עבורך» / «ההמלצות שלי», so it's obvious it opens the site's recommendations for them. | Low | CAPTURED |
| QA-12 | Homepage hero | The hero joke block («📚 אתר שיתוף הספרים #1 בישראל…») **+** the «העולמות של babook / עולם אחד כבר באוויר…» intro line should appear **only on the user's first day** logged in. From the next day onward, **hide it entirely** — it wastes space; returning users should land straight on the site content. | Medium | CAPTURED |
| QA-13 | Courses imported from matazim.co.il | The matazim import grabbed the per-lesson videos but **missed each course's intro video** — on matazim each course has a main page with its own **introduction video** (separate from the lessons). Need to **embed that intro as the new first lesson** (insert at lesson 1, shift the rest down). Avi will provide the **direct YouTube link per course**. **Confirmed understanding 2026-06-13.** | Medium | CAPTURED |

### QA-13 — the 9 affected matazim courses (confirmed)

The matazim-domain courses, each missing its course-page intro video. Avi will
supply `slug → YouTube URL`; insert each as the new lesson 1.

Auto-discovered from the matazim site 2026-06-13 (raw HTML embed + YouTube
oEmbed title). 8 of 9 found; only `arduino` (#2) intro still needed.

| # | Course (slug) | matazim | YouTube intro ID | YT title | Status |
|---|---|---|---|---|---|
| 1 | `tinkercad` | course/3 | `d0idL0XK2F8` | tinkercad intro2 | ✅ found |
| 2 | `fusion360` | course/4 | `Ae-3XfZ3itA` | fusion intro | ✅ found |
| 3 | `arduino-tinkercad` (#1) | course/10 | `308vFRiOm20` | intro to Arduino 1 | ✅ found (Tinkercad sim = Arduino 1) |
| 4 | `arduino` (#2 בקרה וחיישנים) | course/16 | `nQaaHJIdp2U` | lesson 0 intro | ✅ found («ארדואינו 2», 7 lessons match) |
| 5 | `scratch` | course/2 | `83_XBSVUS_Q` | scratch intro | ✅ found |
| 6 | `scratch-advanced` | course/6 | `Qg8PFBOvdYk` | intro to scratch games | ✅ found |
| 7 | `python` | course/5 | `i9-HWYsrh_k` | Python basic intro | ✅ found |
| 8 | `django` | course/1 | `0_bt63WLOHw` | django intro | ✅ found |
| 9 | `video-editing` | course/11 | `uK6P2lTUWwc` | video edit intro | ✅ found |

- Unmapped matazim intros found (courses NOT imported to babook, ignore):
  course/8 "0000 intro external", course/12 "cpu garage 1 intro", course/14
  ESP32 series, course/16 "lesson 0 intro", course/18-19 "Basic Python #1".
- **ALL 9 INTROS FOUND 2026-06-13.** course/16 = «ארדואינו 2» (7 lessons: LED,
  אנלוגי, חיישן מרחק, סיכום) confirms `arduino` (#2); matazim says "do Arduino 1
  first" + it's real hardware (vs Tinkercad sim) → confirms `arduino-tinkercad` =
  #1. This also **resolves QA-15** ordering from the source.
- **Remaining for build:** only the Bunny-upload-vs-YouTube-embed decision
  (recommend Bunny) before inserting each as the new lesson 1.

- **Method confirmed 2026-06-13:** the intro video IS publicly embedded on each
  matazim course page (only the *lessons* are login-gated). Claude can fetch the
  raw HTML of a matazim course URL, extract the YouTube embed ID, AND read the
  title to auto-map to the right babook course. **So Avi only needs to paste the
  matazim course URLs — no manual YouTube-link copying.** (Proven: course/2 =
  Scratch → `83_XBSVUS_Q`.)
- **Open question (Avi to decide):** download each intro YouTube → upload to
  Bunny (consistent player, matches existing lessons) **vs** embed YouTube
  directly. Recommend Bunny for consistency.
- `micropython-thonny` (older flagship, not in this batch) — confirm separately
  if it also needs an intro.

| QA-14 | All scraped/transcribed courses (content quality) | **Re-transcribe every imported course** with OpenAI's **strongest transcription model** (as done for «Co-Coding»), and **rewrite each lesson's text/notes to the highest quality** — faithful to the speaker, clean Hebrew, no em-dashes, proper code/cmd snippets. Apply to **all courses**, not just matazim. | Medium–High (effort) | CAPTURED |
| QA-15 | Arduino courses (titles / ordering) | Make the **learning order explicit in the titles**: «ארדואינו עם טינקרקאד , מבוא לאלקטרוניקה» = **#1** (taken first), «ארדואינו , בקרה וחיישנים» = **#2**. The number must be **clear in the title** so learners know the sequence. (slugs `arduino-tinkercad` = #1, `arduino` = #2.) | Low | CAPTURED |

### QA-14 — scope & approach (for build time)

- Reuse the proven «Co-Coding» method: per-segment re-transcription with the
  stronger model (gpt-4o-transcribe), then faithful-first notes generation,
  no em-dashes, fenced code/cmd snippets, markdown tables.
- **Scope:** all imported courses — the 9 matazim courses (QA-13) + any other
  scraped/transcribed courses. (Hand-authored courses already in good shape can
  be skipped; identify which are scrape-sourced first.)
- **Heavy/long-running + OpenAI cost:** this is a big batch (hundreds of
  lessons). Should run as a controlled background job, course by course, with
  progress reported. Likely belongs to its own sprint and may run while other
  fixes ship.
- **Do QA-13 first** (add the intro lessons) so the new lesson 1s are included
  in the transcription pass.
- **Open question (Avi):** OK to overwrite existing notes in place, or keep a
  backup/diff of the old text first? Recommend a quick DB backup before the run.

| QA-16 | Global navigation | **Back button + breadcrumb on every view.** The site has a hierarchy; reflect it in a **small line at the top** of each page showing where you are and letting you go **back to where you came from**. (Browser back isn't enough — want an in-page back + "you are here" trail.) | Medium | **DONE** (SPR-7.8, REQ-7.8.1) — was wrongly summarized as done earlier; now built as a global bar + back button + central trail map. |
| QA-17 | Nav menu | **Remove «צ'אט AI» from the menu.** Not wanted as a standalone entry point — concern it isn't working well and could **consume too many tokens** to manage. Hide the nav link (keep code dormant). | Medium | CAPTURED |
| QA-18 | First visit (cookie consent) | **Standard cookie-consent banner/popup** on first visit, with the approval **logged** (so there's a record the user accepted). Can be its own popup (the usual pattern) or folded into the onboarding questionnaire. (A banner exists but approval isn't recorded server-side.) | Medium (compliance) | CAPTURED |
| QA-19 | Contact emails (privacy@ / support@) | The privacy page lists **privacy@babook.co.il** and the contact page lists **support@babook.co.il**. Ensure **mail sent to these actually reaches Avi** (forwarded to his admin mailbox or surfaced in admin) and is **actionable** — nothing should be written to a dead address. Verify both addresses exist and route. | High (don't lose user mail) | CAPTURED |

| QA-20 | Footer → contact | Add a **"רוצים להתחבר לאבי סלמון?"** entry, best placed in the **footer**, available site-wide, leading to the **contact form** (with Avi's photo). The existing contact form **lost its image** — it should show **Avi's photo with the background removed**. **DECISION (Avi): source = `docs/Avi_03.jpg`.** No background-removed cutout exists in the repo (checked: only `static/avi-headshot.webp` + `static/avi-bot.jpg`, neither a transparent cutout) → **generate a transparent-background PNG from `docs/Avi_03.jpg` at build time** and use it on the contact form + footer CTA. | Low–Medium | CAPTURED |

| QA-21 | Global design / look & feel | **Adopt Khan Academy's design *style*** (https://www.khanacademy.org) — site **behavior stays exactly as defined here**, only the visual language changes. Khan style = bright/light default, clean & calm, generous whitespace, friendly rounded sans typography, soft rounded cards + subtle shadows, a trustworthy education palette (navy text + a friendly accent, calm not flashy), simple friendly illustration accents, strong clarity/accessibility. Adapt to **Hebrew RTL**; keep babook's playful personality (the book joke) inside this clean frame. **This replaces the current generic dark-SaaS look.** | High (big, cross-cutting) | CAPTURED |

### QA-21 — design-overhaul approach (for build time)

- **Light becomes the default** (Khan is bright) → merges with **QA-7**: ship a
  refreshed **light theme as default + keep a dark theme as the optional toggle**.
- It's a **token + type + component refresh**, not a rewrite — restyle the CSS
  tokens (`--bg-*`, `--accent-*`, radii, shadows), the type scale (friendlier
  rounded Hebrew sans), and the shared components (cards, buttons, nav, hero).
- **Validation step first:** build a **live style-prototype page on babook**
  (real content — a course card, the showcase wall, the hero — re-skinned
  Khan-style) for Avi to approve *before* rolling the new look site-wide.
- Pairs with QA-8 (animated bg as an opt-in flourish, kept tasteful/subtle so it
  doesn't fight the clean Khan calm) and QA-20 (Avi's warmth in the footer).
- Becomes its **own epic** (e.g. EPIC-7 «Design Refresh») given how cross-cutting
  it is; sequence it deliberately among the other QA fixes.

| QA-22 | Login page → Google button | Pressing **«המשך עם גוגל»** jumps to `https://babook.co.il/accounts/login/` (an unnecessary intermediate page) instead of **immediately starting the Google OAuth flow**. Fix: point the button at the provider-login URL directly (e.g. `/accounts/google/login/?process=login&next=…`, as the `/join/` wall already does) so it kicks off Google right away. Likely cause: the button currently links to `socialaccount_signup`, which bounces to `/accounts/login/` when nothing is pending. Check `register.html` too. | Low–Medium | CAPTURED |

### Bugs found during QA (fixed immediately, not part of the improvement epic)

| Bug | Where | Status |
|---|---|---|
| BUG-1 | `/community/showcase/new/` → 500 (`project.*` used as a Django filter argument when project is None → VariableDoesNotExist) | **FIXED + deployed `364fee5`** (+ GET-render regression tests; the suite only POSTed before) |

## Notes / open questions

- **QA-1 "verify the email":** does this mean (a) just confirm/capture it correctly in the chat, or (b) real email verification (send a confirmation link before full access)? Current setting is `ACCOUNT_EMAIL_VERIFICATION="none"`. Assuming (a) for now — flag if you want real verification.
- **Touches existing spec:** REQ-1.1.3 (signup/forgot-password), REQ-5.4.3 (minimal-friction signup), REQ-5.5.7 (welcome basics step — currently a form, to become conversational), REQ-5.5.8 (Avi Bot persona). The conversion will revise these rather than add orphans.
- Implication: the current order is *signup → basics form → AI interview*. New target: *signup (email required) → one continuous Avi Bot chat that covers name/email-confirm/role/interests, finishable anytime, name mandatory*.
- **QA-7/8 theming:** the whole site is CSS-token-based (`--bg-primary`, `--accent-*` etc. in style.css), so a light theme = an alternate token set toggled by a `data-theme` attribute on `<html>`, persisted on `UserProfile` (and a cookie for anonymous). RTL already handled. Animated background = a lightweight CSS/canvas layer behind content, chosen via a profile preference; must respect `prefers-reduced-motion` and not hurt mobile perf. Open question for QA-8: a small fixed set of presets (stars / gears / particles / none) — confirm which vibes you want.

## When capture is done → conversion checklist

- [ ] Group items into themes
- [ ] Assign each a spec REQ (new chapter/epic, e.g. EPIC-7 — QA Hardening)
- [ ] Create backlog features (F-x.y.z) tracing to each REQ
- [ ] Write tests per feature (TDD)
- [ ] Implement → full regression green → deploy → smoke
- [ ] Flip statuses in spec + backlog; append to regression.md + test_plan.md
- [ ] Delete this file
