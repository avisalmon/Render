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

## Items

| QA-ID | Where (page/flow) | Feedback (verbatim intent) | Severity | Status |
|---|---|---|---|---|
| QA-1 | Signup (email/password path) | **Email must be mandatory at signup.** Today a username+password signup (not Google) can have no email logged → anyone can fake "I forgot password" (security hole). An email is required info *before* the account is created. | High (security) | CAPTURED |
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

| # | Course (slug) | Track | Lessons | Current 1st lesson | Intro link |
|---|---|---|---|---|---|
| 1 | טינקרקאד (`tinkercad`) | 3d | 9 | כניסה והתחלה | _(pending Avi)_ |
| 2 | Fusion 360 (`fusion360`) | 3d | 6 | התקנה ויצירת מטבע | _(pending Avi)_ |
| 3 | ארדואינו עם טינקרקאד (`arduino-tinkercad`) | hardware | 8 | מה זה ארדואינו? | _(pending Avi)_ |
| 4 | ארדואינו (`arduino`) | hardware | 7 | הבהוב LED | _(pending Avi)_ |
| 5 | סקראץ' (`scratch`) | software | 18 | התקנה והגדרה | _(pending Avi)_ |
| 6 | סקראץ' מתקדם (`scratch-advanced`) | software | 14 | כפילים חלק 1 | _(pending Avi)_ |
| 7 | פייתון (`python`) | software | 21 | התקנת פייתון | _(pending Avi)_ |
| 8 | Django (`django`) | software | 23 | מבוא ל-Django | _(pending Avi)_ |
| 9 | עריכת וידאו Corel (`video-editing`) | media | 15 | חומרי גלם | _(pending Avi)_ |

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
