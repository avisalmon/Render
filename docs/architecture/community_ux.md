# Community — UX Concept

> Companion to [main_spec.md §Chapter 6](../main_spec.md). **PROPOSED
> 2026-06-12 — for review.** The design thinking and screen concepts behind
> the seven community epics. Redline freely; nothing is built.

## 1. The experience in one sentence

A member finishes a lesson, asks one question and gets a real answer, publishes
what they built on the exhibition wall, gets stars and a badge, enters the
monthly challenge, and comes back every week because the feed shows people like
them doing things like that.

## 2. What great platforms do (and what we borrow)

| Platform | The move | What we borrow |
|---|---|---|
| **Stack Overflow** | Accepted answers turn chat into a permanent knowledge base | Q&A with accepted answers, tags, canonical pins (EPIC-6.2) |
| **Dribbble / Behance** | The portfolio wall IS the community; showing off is the engine | Showcase exhibition wall + profile portfolio (EPIC-6.3) |
| **Kaggle** | Competitions create cadence — but metric-racing alienates learners | Challenges, but course-anchored and human-judged (DEC-39) |
| **Duolingo / AI Ascent** | Badges, tiers, leaderboards drive habit | Reputation + badge system, proven in AI Ascent production (EPIC-6.1) |
| **Discord** | Channels feel alive — but knowledge evaporates | Chat ONLY after the durable layer, with promote-to-forum (EPIC-6.6, DEC-36) |
| **Strava** | A feed of *other people's effort* motivates yours | Chronological activity feed of real member work (EPIC-6.4) |
| **Meetup / Luma** | RSVP + recording archive turns events into content | Events with .ics, reminders, recorded archive (EPIC-6.7) |

## 3. The member journey

```
 Lesson page ──"שאלו את הקהילה"──► Forum thread (pre-tagged to the lesson)
     │                                   │ answer accepted → +15 points, badge
 Course done ──"פרסמו מה בניתם"──► Showcase project ──► stars, comments, featured
     │                                   │
     ▼                                   ▼
  Monthly challenge (submission = the project)──► community vote + judging ──► podium, badge
     │                                   │
     ▼                                   ▼
  Feed + weekly digest ◄──── everything lands here ────► profile portfolio grows
```

The loop: **learn → ask → build → show → compete → belong → return**.
Every arrow is one click, and every object links back to a course.

## 4. Screen concepts (wireframes)

### 4.1 Community home — the feed (`/community/`)

```
┌────────────────────────────────────────────────────────┐
│ קהילת babook        [הכל] [אני עוקב] [התחום שלי]         │
│ ┌────────────────────────────────────────────────────┐ │
│ │ ✏️ שתפו משהו...   [טיפ] [שאלה] [פרויקט]             │ │  ← one composer, 3 routes
│ └────────────────────────────────────────────────────┘ │
│ ⭐ דנה פרסמה פרויקט: "בוט וואטסאפ עם Claude"  [25⭐]      │
│ ✅ לשאלה "איך מגבילים טוקנים?" התקבלה תשובה של יוסי       │
│ 🏆 האתגר החודשי: "סוכן AI ראשון" — 12 הגשות, 5 ימים נותרו│
│ 💡 טיפ מאת רון: "תמיד תבקשו מ-Copilot טסטים קודם"  ❤️ 14 │
│ 📅 שעת מומחה עם אבי — יום חמישי 19:00  [הרשמה]           │
└────────────────────────────────────────────────────────┘
   sidebar: המובילים החודש (leaderboard) · תגיות חמות · האתגר הפעיל
```

### 4.2 Exhibition wall — דוכן ההשוויץ (`/community/showcase/`)

```
┌────────────────────────────────────────────────────────┐
│ דוכן ההשוויץ 🏗️   [הכל | AI | מטצים | חדשנות]  [+ פרסמו] │
│ ── נבחרת השבוע ─────────────────────────────────────── │
│ ┌────────┐ ┌────────┐ ┌────────┐                        │
│ │ cover  │ │ cover  │ │ cover  │   ← featured row       │
│ │ ⭐ 41   │ │ ⭐ 38  │ │ ⭐ 22   │                        │
│ └────────┘ └────────┘ └────────┘                        │
│ ── הכל ──────────────────────────────────────────────  │
│ grid of project cards: cover, title, author+avatar,     │
│ "נבנה בעקבות: סוכני קוד", ⭐ count                       │
└────────────────────────────────────────────────────────┘
Project page: story (markdown) + gallery + demo video + repo link +
comments + "עוד מהבונה הזה" + OG card for WhatsApp/LinkedIn sharing.
```

### 4.3 Q&A thread

```
┌────────────────────────────────────────────────────────┐
│ ❓ איך אני נותן ל-agent גישה רק לתיקייה אחת?              │
│ tags: [ai-l2] [copilot] [קורס: סוכני קוד]    👁 89        │
│ ┌─ ✅ תשובה מקובלת ─────────────────────────┐ ▲ 12       │
│ │ (avatar) יוסי · מנטור 🥈: משתמשים ב-...    │            │
│ └──────────────────────────────────────────┘            │
│ ▲ 4  תשובה נוספת...                                      │
│ 🤖 סיכום AI (לשרשורים ארוכים)                            │
│ [כתבו תשובה...]                                          │
└────────────────────────────────────────────────────────┘
On ask: AI suggests existing threads + lessons BEFORE posting (dedup).
```

### 4.4 Challenge page

```
┌────────────────────────────────────────────────────────┐
│ 🏆 אתגר יוני: בנו סוכן AI ראשון       ⏳ נותרו 5 ימים    │
│ התקציר · הקריטריונים · הפרסים (תג אלוף + פיצ'ר בראשי)    │
│ [הגישו פרויקט] ← submission is a showcase project        │
│ ── הגשות (12) ── wall of submission cards, ⭐ vote        │
│ ── אחרי השיפוט ── 🥇🥈🥉 podium + judges' notes           │
└────────────────────────────────────────────────────────┘
```

### 4.5 Public member profile (`/c/<username>/`)

```
┌────────────────────────────────────────────────────────┐
│ (avatar)  דנה כהן · מורה 🏅🥈🛠️   עוקבים: 31  [עקבו]     │
│ "מורה למדעים שמתאהבת ב-AI"     [פתוחה לשיתופי פעולה ✓]   │
│ נקודות: 220 · תשובות מקובלות: 6 · פרויקטים: 3            │
│ ── הפרויקטים שלי ── (showcase cards)                     │
│ ── תעודות ── (existing certificates)                     │
│ ── פעילות אחרונה ── (answers, tips)                      │
└────────────────────────────────────────────────────────┘
```

## 5. Information architecture

```
/community/                feed (home)
/community/forum/          categories → threads
/community/showcase/       exhibition wall → project pages
/community/challenges/     active + past → challenge pages
/community/events/         upcoming + recordings
/community/members/        directory (find collaborators)
/community/chat/           channels (EPIC-6.6, later)
/c/<username>/             public profile
```

Nav: the existing "קהילה" item in the worlds dropdown goes live; a bell icon
(notifications) joins the navbar for members.

## 6. Tone & safety

- Hebrew-first, warm, the babook humor (the book-sharing joke lives here too).
- Upvote-only; no downvote dogpiles (DEC-38). The accepted answer and staff
  pins carry the quality signal.
- Minors (matazim students): no DMs, publishing reviewed, uploads moderated
  (DEC-41). This is a school-friendly community by design.
- Avi appears as host (שעת מומחה, judge, Avi Bot draft answers) — but the
  content engine is the members (anti creator-dependence).

## 7. Build order & why (DEC-36)

1. **EPIC-6.1 Foundation** — identity/reputation/safety; invisible but everything needs it
2. **EPIC-6.2 Forums** — durable knowledge; immediate value even with 10 members
3. **EPIC-6.3 Showcase** — the bragging wall; the emotional hook + share-outward growth
4. **EPIC-6.4 Feed & Tips** — only now is there content to feed; digest revives dormant users
5. **EPIC-6.5 Challenges** — cadence; needs showcase as the submission vehicle
6. **EPIC-6.6 Chat** — amplifies an already-alive community; never before it
7. **EPIC-6.7 Events** — converts lurkers to contributors; feeds recordings back in

Each epic ships alone, methodology-first (spec → backlog → tests → regression
→ deploy), and the community is usable after every single one.

## 8. Open questions — RESOLVED (Avi, 2026-06-12)

1. **Naming** — keep «דוכן ההשוויץ», add the formal subtitle «גלריית
   הפרויקטים של קהילת babook»; ratings + comments are core (DEC-44).
2. **Anonymous visibility** — read-public for forum/showcase/challenges/events,
   with a soft "הירשמו כדי להגיב ולדרג" note; every interaction (comment, rate,
   post, vote, RSVP) requires login via the /join/ wall (DEC-45).
3. **First challenge** — the **MicroPython kit** (matazim/hardware, anchored to
   `micropython-thonny`) (DEC-47a).
4. **Digest** — explore only after ~50 active members (DEC-46).
5. **Leaderboard** — public with opt-out (recommended + accepted); students
   shown by display name only (DEC-47).
