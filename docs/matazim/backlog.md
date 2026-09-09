# מט״צים — Backlog

Sprint by sprint. Only the sprint in flight is written out in detail. We decide
the next one when this one closes, not before, so this file never pretends to
know more than we do.

Process is [`docs/the_manager.md`](../the_manager.md), unchanged. Status truth
lives in [`spec.md`](spec.md) and here, updated together. Tests are planned in
[`test_plan.md`](test_plan.md) and registered in the repo-wide
[`docs/regression.md`](../regression.md), because pytest runs one suite over one
Django project.

Standing rule: dev first. Nothing reaches production without Avi's word.

---

## SPR-M.1 — The front door  `AWAITING REVIEW`

**Goal:** the app exists, it looks like מט״צים, and it is sealed off from
babook. Design first, functionality later: the home page is built to Litala's
screen 1 with every value hardcoded. No models, no forms, no logic.

**Decisions taken into this sprint (2026-09-09):** photographs supplied by Avi,
everything else drawn as SVG by hand. Typeface is **Rubik**, deliberately not
babook's Heebo, so the two read as different products on sight.

| F-ID | Feature | Traces | Status |
|---|---|---|---|
| F-M.1.1 | Sever the old presentation | RULE-1, RULE-2, RULE-4, REQ-M.3 | DONE |
| F-M.1.2 | New Django app `matazim`, own URL space at `/matazim/` | REQ-M.1, spec 2.2 | DONE |
| F-M.1.3 | Design system stylesheet: tokens, buttons, cards, chips, gradient | REQ-M.1, spec 3.2 | DONE |
| F-M.1.4 | Standalone base template: own header, nav, footer, RTL, from 360px | REQ-M.1, REQ-M.5b | DONE |
| F-M.1.5 | Public home page, all content hardcoded | REQ-M.5, M.5c, M.5d, M.5f | DONE |
| F-M.1.6 | Guard tests for the four separation rules | RULE-1 to RULE-4 | DONE |

### Scope notes

**F-M.1.1 removes presentation only.** Routes out of `app/urls.py`, both nav
entries out of `templates/base.html`, the `show_matazim` context processor, and
the files `app/matazim_views.py`, `templates/app/matazim/`, `static/matazim.css`,
`tests/test_spr_10_1.py`. It is forced rather than optional: the new app needs
`/matazim/`, which the old routes hold, and `base.html` reverses `matazim_home`.

**Nothing is destroyed.** `matazim_models.py`, migrations 0096 to 0098,
`seed_matazim`, and the entrance-test engine (`matazim_geometry`,
`matazim_check`, `matazim_targets`, and the passing `tests/test_spr_10_2.py`)
all stay exactly where they are. Dropping the production tables waits on ACT-M.2.

**Out of scope, deliberately:** login, the member nav, any real data, the other
eight sections, 404 and 500 pages, and the two logged-in screens.

**Cut during the sprint (Avi, 2026-09-09):** the prototype's stats band and its
תוצרים נבחרים showcase. Both were invented, and a public page does not carry
invented figures or invented children's work. The components stay in the design
system; the sections return when there is data and consent behind them, under
REQ-M.5f and REQ-M.5e. Tests now assert their absence rather than their shape.

### ACT items

| ACT-ID | What Avi does | Blocks | Status |
|---|---|---|---|
| ACT-M.1 | Hero photograph, supplied 2026-09-09 (`static/matazim/img/hero.png`). The project thumbnails are no longer needed: the showcase came off the page | Nothing | CLOSED |
| ACT-M.2 | Confirm whether any real person applied on the production tables | The table-drop, which is **not** in this sprint | OPEN |

### Definition of done

All six features DONE in this file and their REQs updated in `spec.md`, every
test in `test_plan.md` green, the whole repo suite green, and `/matazim/`
demoed to Avi on the local server.

---

## Candidates for the next sprint

Not planned, not committed, just the obvious neighbours. We pick one when
SPR-M.1 closes.

- The rest of the public front: המסלול השנתי, בתי הספר המשתתפים, אודות התכנית.
- The threshold: מט״צים-branded register and log in over the shared `User`.
- The member shell: logged-in nav, and המסלול שלי as a static design pass.
- Retire the production tables, once ACT-M.2 is answered.
