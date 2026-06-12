# Onboarding & First-Time Experience — UX Concept

> Companion to [main_spec.md §Chapter 5](../main_spec.md). **Approved by Avi and
> implemented 2026-06-12.** Open questions resolved: (1) AI interview is the
> default, user-skippable (DEC-30); (2) the registration ask happens strictly at
> gated actions, no proactive nudges (DEC-34); (3) corporate visitors get a
> "for your team" learner path (DEC-35); (4) all sprints shipped in one pass.

## 1. What great platforms do (and what we borrow)

| Platform | The move | What we borrow |
|---|---|---|
| **Duolingo** | Asks *why* you're learning + your level **before** account creation; commitment and motivation first, friction last. | Value-first ordering; capture goal + level; make the first action feel like progress, not paperwork. |
| **Coursera / LinkedIn Learning** | Interest/skill selection on entry → an immediately personalized catalog ("Recommended for you"). | A `LearnerProfile` of interests that re-orders the homepage from minute one. |
| **Notion / modern SaaS** | A short "get started" checklist drives users to the product's *aha* moment fast; progressive disclosure. | The onboarding checklist (REQ-5.6.5) and dropping users straight into a first lesson, not a dashboard. |
| **Reverse trial (Superhuman, Canva)** | Let people taste the good stuff, *then* ask them to commit. | Free preview lesson as the taste; the wall appears only at the next gated action. |
| **AI interview onboarding (our research_2)** | A conversation extracts goals/profile better than a static form. | The AI interview as the primary onboarding, with a static form as the guaranteed fallback. |
| **Deep-link intent preservation (everywhere good)** | A shared link → login → returns you to the *exact* page you wanted. | `?next=` preserved through OAuth; the deep-link course becomes the primary interest. |

**The one principle that ties it together:** *earn the registration, then reward
it.* Don't gate exploration; gate the high-value action — and when you do, make the
gate feel like an invitation tied to what the visitor already wanted.

## 2. The four entry points (intent differs by door)

A first-time visitor does not arrive in one way. The journey adapts to the door:

```
A. Homepage  /            → broad intent      → orient across the 3 worlds, let them pick
B. Course link /courses/X → specific interest → "you came for X" — lean into X's domain
C. Locked lesson /…/N     → high intent (gate)→ contextual wall → register → land on N
D. /corporate/            → prospect (B2B)    → lead funnel (existing), NOT the learner funnel
```

Doors B and C are the highest-converting and least-served today: someone shared a
link to a specific course, the visitor clicked with real interest, and right now we
do nothing with that signal. Chapter 5's biggest win is treating that arrival as
"this is their main interest" and carrying it all the way through signup.

## 3. The journey, end to end

```
 ┌─────────────┐   ┌──────────────┐   ┌────────────┐   ┌──────────────┐   ┌─────────────┐
 │  ARRIVE     │ → │  EXPLORE     │ → │  GATED      │ → │ REGISTER     │ → │ ONBOARD     │ → ACTIVATE
 │ capture     │   │ free browse  │   │  ACTION     │   │ (return to   │   │ AI interview│   first
 │ entry+intent│   │ + free lesson│   │ context wall│   │  intent)     │   │ → profile   │   lesson
 └─────────────┘   └──────────────┘   └────────────┘   └──────────────┘   └─────────────┘
   §5.2              §5.3               §5.4              §5.4               §5.5 / §5.6     §5.6.4
   (silent)          (no friction)      (soft→hard)       (?next= kept)      (conversational) (aha)
```

Anonymous the whole left half. Registration sits at the gated action, not the front
door. Onboarding happens once, right after the first registration.

## 4. Screen concepts (wireframes)

### 4.1 First-visit welcome strip (anonymous, dismissible, RTL)

Shown once. If they arrived on a course (door B), it acknowledges that.

```
┌───────────────────────────────────────────────────────────── ✕ ─┐
│  👋 ברוכים הבאים ל-babook — שלושה עולמות: AI · מייקרים · חדשנות   │
│  הגעת בשביל «יסודות Copilot»? התחילו עם השיעור הראשון — חינם.     │
│  [ צפו בשיעור חינם ]   [ עיינו בקטלוג ]                            │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Context-aware wall (the conversion moment — door C)

Replaces the generic login redirect. Names what they wanted.

```
┌──────────────────────────────────────────────┐
│   🔒  כדי להמשיך ל«שיעור 2 — סוכני קוד»        │
│       הירשמו בחינם — שומר התקדמות, ללא תשלום   │
│                                                │
│   [  המשך עם Google  ]   [  המשך עם GitHub  ]  │
│   ──────────────  או  ──────────────           │
│   שם:    [_______________]                     │
│   אימייל:[_______________]                     │
│   סיסמה: [_______________]                     │
│   [ הרשמה והמשך לשיעור → ]                      │
│                                                │
│   כבר רשומים? התחברו   ·   ✓ צפייה חינם בשיעור 1│
└──────────────────────────────────────────────┘
        after submit → lands on lesson 2 (?next=)
```

### 4.3 AI onboarding interview (`/welcome/`, once, post-signup)

Reuses the existing chat UI/infra (REQ-1.6). Greets by name; if door B/C, opens on
that interest. "דלג" always present.

```
┌──────────────────────────────────────────────  דלג ›  ┐
│  🎓  היי אבי! כמה שאלות קצרות ונבנה לך מסלול אישי.       │
│                                                         │
│  ראיתי שהגעת בשביל «סוכני קוד». זה המוקד שלך,            │
│  או שמעניין אותך המסלול הרחב של AI?                      │
│                                   [ רק זה ]  [ הרחב ]    │
│                                                         │
│  …מה המטרה שלך?  (עבודה / סקרנות / פרויקט / קריירה)      │
│  …מה הרמה שלך?   (מתחיל / יודע קצת / מנוסה)              │
│  …כמה זמן בשבוע? (שעה / 2-3 / יותר)                      │
│                                                         │
│  ▸ בונה לך מסלול: «AI למתחילים» — שיעור ראשון מוכן.      │
│  [ קחו אותי לשיעור הראשון → ]                            │
└─────────────────────────────────────────────────────────┘
```

Static fallback (skip / AI down) — three taps, same output:

```
[ בחרו תחומים: ☐AI ☐מייקרים ☐חדשנות ]  →  [ רמה: מתחיל/בינוני/מנוסה ]  →  [ מטרה ]  →  מסלול מומלץ
```

### 4.4 Personalized homepage (logged-in)

```
┌──────────────────────────────────────────────┐
│  המשך לצפות:  «סוכני קוד» — שיעור 2 (4:13) ▸   │   ← REQ-1.3.16 (exists)
├──────────────────────────────────────────────┤
│  מומלץ עבורך  (כי בחרת AI · מתחיל)             │   ← NEW REQ-5.6.3
│  [ קורס ] [ קורס ] [ קורס ]                    │
├──────────────────────────────────────────────┤
│  התחלה מהירה:  ✓שיעור ראשון ☐בוחן ☐רפלקציה     │   ← NEW REQ-5.6.5 checklist
├──────────────────────────────────────────────┤
│  שלושת העולמות … (קטלוג גנרי)                  │   ← existing worlds
└──────────────────────────────────────────────┘
```

## 5. Logged-out vs logged-in, in one sentence each

- **Logged out (guest):** *Explore everything, taste one free lesson per course,
  but to keep progress, go deeper, reflect, chat, or earn a certificate — register.*
  Never hits a dead 403; every gate is an invitation tied to what they wanted.
- **Logged in (member):** *A personalized home, full lessons within entitlement,
  progress/quizzes/reflections/certificates, AI chat, and profile.* The access
  matrix (§5.1) is the precise contract.

## 6. Risks & how the spec handles them

| Risk | Mitigation in spec |
|---|---|
| AI interview feels long or breaks | Bounded turns + cheap model (REQ-5.5.6); static fallback (REQ-5.5.4); always skippable (REQ-5.5.5). |
| Wall annoys low-intent browsers | Value-first (DEC-29): wall only at a genuinely gated action; soft nudges before that (REQ-5.3.3). |
| OAuth round-trip drops the `next` | Explicit end-to-end `?next=` preservation requirement (REQ-5.4.2 / DEC-33) with a test. |
| Over-engineering recommendations | Deterministic taxonomy mapper, no ML (DEC-32) — explainable and testable. |
| Privacy creep | Session-only for anonymous; Plausible only; consent banner respected (REQ-5.2.4 / DEC-31). |

## 7. Open questions for review

1. **Onboarding placement** — AI interview as the *default* (skippable), or
   opt-in ("personalize my path") with the static form as default? (Spec proposes
   AI default + skip.)
2. **Wall timing** — also show a soft "register to track progress" banner *after*
   the free lesson finishes, or keep the wall strictly at gated actions only?
3. **Scope of v1** — ship the access model + wall + return-to-intent first
   (highest ROI, no AI), then the AI interview + personalization as a second
   sprint? (Recommended — see EPIC-5 sprint order.)
4. **Corporate door (D)** — leave `/corporate/` on its existing lead funnel
   untouched, or also offer corporate visitors a "for your team" learner path?
