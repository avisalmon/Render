# מט״צים — per-role journey review

2026-09-12. Every role walked through every screen it can reach, against Avi's
five criteria plus the need-to-know rule he added mid-review.

Method: not opinion. A crawler signs in as each role, starts at their entry
point, and follows **only the links that role can actually see**. Anything a
role may open but never reach by clicking is a screen they can only find by
knowing the URL. Then every screen rendered at 390px and looked at.

Nine roles walked: visitor, new member (registered, has not sat the test),
leader candidate, member with no leader, student in training, certified מט״צ,
leader, program manager, root.

---

## Part 1 — What was already broken, and is now fixed

### 1.1 The phone guard's overflow check could never fail  `FIXED`

The most serious finding, because it invalidates a claim the project has been
making since SPR-M.7.

`tests/test_matazim_mobile.py` has asserted "nothing may be wider than the
screen at 390px" for many sprints. It compared `documentElement.scrollWidth`
against `window.innerWidth` inside a context created with `is_mobile=True`.
Under mobile emulation Chromium **grows the layout viewport to fit content that
does not fit**. Measured on the program manager's team screen:

| | window | innerWidth | scrollWidth | verdict |
|---|---|---|---|---|
| `is_mobile=True` (the guard) | 390 | **501** | 501 | "fits" |
| plain 390px window | 390 | 390 | **500** | 110px over |

So the comparison was 501 against 501 and the check passed by construction. The
page really was 500px wide on a 390px phone: נעמי had to scroll sideways to
reach the reject button, and the guard said the page fitted.

Fixed by measuring against `documentElement.clientWidth`, which stays at the
window under emulation. Verified the only way that counts: the defect put back,
the guard fails; the fix restored, it passes.

### 1.2 Roster rows cannot wrap  `FIXED`

`.mz-training li` is `display: flex` with no `flex-wrap`, and the actions on the
right are `flex: none` so they may not be squashed. Any row whose actions are
wide therefore pushes the page wider than the phone. The program manager's
candidate row carries a full "אישור כמוביל/ה" button **and** a "לא מתאים" link,
and it was 53px over with the reject action hanging outside its own card.

Fixed by letting the row wrap and letting the name give way first
(`min-width: 0`). This was never specific to one screen: the same rule styles
the leader's waiting list and the roster.

### 1.3 The phone fixture had no candidate leader  `FIXED`

Why 1.1 and 1.2 survived together. The widest row in the product only exists
while somebody is waiting to be approved, and the fixture created leaders with
`approved_at=timezone.now()` only. The row never rendered, so there was nothing
to overflow.

**Fifth time in this session** that a real defect turned out to live in a state
no fixture creates. That is no longer a coincidence, it is the dominant failure
mode of this codebase's tests.

---

## Part 2 — Findings per role

### Visitor

| # | Criterion | Verdict |
|---|---|---|
| 1 | Intuitive to find | **One gap: `/matazim/leaders/`** |
| 2 | Self-explanatory | Yes |
| 3 | Information available | Yes |
| 4 | UX | Yes |
| 5 | Pages exist | Yes |

**V1. The teachers' door is linked from nowhere.** `/matazim/leaders/` is
checked against the home page, about, schools, login, register and track: not
one links it. A teacher told "go to the site and come in as a leader" has no
door. The comment in `base.html` claims "the only route was the כניסת מובילים
door on the home page", so this link existed once and was lost.

### New member (registered, has not sat the entrance test)

This is where the whole funnel starts and it was missing from the first pass of
this audit, which meant the most important journey was the one not being walked.

| # | Criterion | Verdict |
|---|---|---|
| 1 | Intuitive to find | Yes, once the test course exists — see N1 |
| 2 | Self-explanatory | Yes |
| 3 | Information available | Yes |
| 4 | UX | Yes |
| 5 | Pages exist | Yes |

**N1. The entrance-test task is reachable only through the lessons block.** In
`test_lessons.html` the "למשימה" button sits inside `{% if lessons %}`, and the
lessons come from babook's `tinkercad` course. If that course is ever missing or
unpublished, a member sees "השיעורים ייפתחו כאן בקרוב" and **the entrance test
becomes unreachable**, even though the task itself works. Nothing in the deploy
guarantees `tinkercad`: it is not in `load_course_from_manifest`'s slug list and
`seed_matazim` only reads it. It exists in prod because somebody authored it.

The task is not a reward for finishing the teaching. It should be reachable
whichever state the teaching content is in, and the empty state should say what
is actually wrong rather than "coming soon".

### Leader candidate (registered through an open invite, waiting for approval)

The worst-served role in the product. REQ-M.93 creates this state deliberately
and **nothing in the product acknowledges it exists.**

| # | Criterion | Verdict |
|---|---|---|
| 1 | Intuitive to find | **No screen to find** |
| 2 | Self-explanatory | **No** |
| 3 | Information available | **No** |
| 4 | UX | **No** |
| 5 | Pages exist | **No** |

**C1. `/matazim/leaders/` does not know they are a candidate.** It says
"כבר מוזמן/ה? התחברו עם אותו אימייל שמסרתם לצוות, והדף הזה ייקח אתכם ישר לאזור
שלכם." They *are* signed in, with that email, and the page does not take them
anywhere. From their side, registering through the invitation appears to have
done nothing at all. The only button is "על התוכנית".

`matazim/access.py` already has `candidate_of(user)`. The concept exists in the
code; this screen does not use it.

**C2. Their profile treats them as a child pupil.** האזור האישי shows a teacher
waiting for approval:

- **אישור הורה** — a parental-consent panel, to an adult teacher
- **המוביל/ה שלי: טרם שויך** — *their* leader, unassigned
- **שלב בתוכנית: טרם הצטרפתם**
- **מבחן הכניסה: טרם**
- **ההדרכות שלי 0** — "עוד לא התחלתם הדרכה"
- **המסלול שלי** with a button into the student journey

Nothing about being a leader, nothing about waiting, no mention of who to ask.

### Member with no leader yet

| # | Criterion | Verdict |
|---|---|---|
| 1 | Intuitive to find | Yes |
| 2 | Self-explanatory | Yes |
| 3 | Information available | Yes |
| 4 | UX | Yes |
| 5 | Pages exist | Yes |

Clean. REQ-M.65's "nobody's yet" state reads as a normal state, which is what it
was written to do.

### Student in training / certified מט״צ

| # | Criterion | Verdict |
|---|---|---|
| 1 | Intuitive to find | Yes |
| 2 | Self-explanatory | Yes |
| 3 | Information available | Yes |
| 4 | UX | Yes |
| 5 | Pages exist | Yes, within what is built |

**S1. Need-to-know: they carry the whole marketing site forever.** A student
mid-programme reads nine nav items on every page, of which המסלול שלי and
הקורסים are theirs. אודות התכנית, בתי הספר, קהילת מט״צים and ימי שיא are
recruitment copy aimed at somebody who has not joined. REQ-M.5b is marked WIP
and already promises a different logged-in menu; it was never built.

### Leader

| # | Criterion | Verdict |
|---|---|---|
| 1 | Intuitive to find | Yes |
| 2 | Self-explanatory | Yes |
| 3 | Information available | Yes, and better since SPR-M.23 |
| 4 | UX | Yes, after 1.2 |
| 5 | Pages exist | Submissions still missing (REQ-M.19, known) |

**L1. Need-to-know: a leader is offered the student journey.** Their nav carries
המסלול שלי, and they can open `/matazim/learn/scratch/`, `/matazim/test/` and
the test task. A teacher is not a pupil (§4.9 is explicit that these are
different people), and their own area is a separate nav item they have to know
to prefer.

**L2. Their profile is the same student screen.** נעה מורה, with four students
and a class, is told her leader is unassigned, that she has not joined the
programme, that she has not sat the entrance test, and is shown a parental
consent panel. Nothing links her to her own area or names her students.

### Program manager

| # | Criterion | Verdict |
|---|---|---|
| 1 | Intuitive to find | Yes |
| 2 | Self-explanatory | Yes |
| 3 | Information available | Yes |
| 4 | UX | Yes, after 1.1 and 1.2 |
| 5 | Pages exist | Yes |

המובילים שלי is genuinely good: candidates with an approve button, her leaders
with counts, search, personal invite, open invite, all on one screen.

**P1. Need-to-know: she carries the student journey too.** המסלול שלי in her
nav, and the entrance-test task is open to her.

### Root

No findings beyond the above. Crossing every world is correct (§4.4).

---

## Part 3 — What to do

Fixed during the review:

- 1.1 the overflow guard that could not fail
- 1.2 rows that could not wrap
- 1.3 the missing candidate state in the phone fixture

Queued as **SPR-M.24**, in the order they hurt:

| # | Work | Why first |
|---|---|---|
| 1 | The candidate leader gets a screen that knows they are waiting | C1, C2. A real teacher will hit this the first time Avi hands out an open invite |
| 2 | האזור האישי becomes role-aware | C2, L2, P1. A teacher shown a parental-consent panel is the clearest need-to-know failure in the product |
| 3 | The nav becomes role-aware | S1, L1, P1, and REQ-M.5b which has promised this since SPR-M.1 |
| 4 | The teachers' door gets a link | V1 |
| 5 | The entrance task stops depending on the teaching content | N1 |

Not in scope, already known and tracked: submissions and feedback (REQ-M.19),
notifications (REQ-M.33), deadlines and the calendar (REQ-M.34).

## Part 4 — What this review could not do

It checked the product against itself. Nine synthetic roles, walked by a
crawler, judged by me. It cannot tell us where a real fourteen-year-old gives
up, or what נעמי tries to do that the product has no screen for at all. That is
still item 3 of the earlier review, and it is still the one thing nothing here
substitutes for.
