# The Manager — Design & Validation Process

> Master process file for delivering babook.co.il.
> When Avi says **"what's next"**, **"run the next sprint"**, **"continue"**, or any equivalent — Copilot follows this file end-to-end without skipping steps.

---

## Cardinal Rules

1. **Never `git push` without explicit Avi approval.** "Deploy" / "push" / "go live" are the only triggers.
2. **Never auto-install packages.** Add to `requirements.txt`, tell Avi to run pip.
3. **Never skip a step in this workflow.** If blocked, stop and ask.
4. **Always trace work to REQ-IDs.** Commits, PRs, tests, and notes reference `REQ-x.y.z` and `F-x.y.z`.
5. **Status truth lives in two files only:** [backlog.md](backlog.md) and [main_spec.md](main_spec.md). Update both together.
6. **Always use `env\` virtual environment.** Activate via `env\Scripts\activate`. Never install globally.
7. **Keep `requirements.txt` up to date.** Any new dependency gets added there; Avi runs pip.
8. **Tracking integrity is non-negotiable.** Every REQ has a backlog feature. Every feature has tests. Every test traces to a feature. No orphans.

---

## Files This Process Touches

| File | Role |
|---|---|
| [.github/copilot-instructions.md](../.github/copilot-instructions.md) | Workspace conventions (env, deploy, project layout) |
| [docs/main_spec.md](main_spec.md) | Source of truth: requirements (`REQ-*`), decisions (`DEC-*`), acceptance |
| [docs/backlog.md](backlog.md) | Epic → Sprint → Feature, tracked status |
| [docs/the_manager.md](the_manager.md) | This file — process definition |
| [docs/dashboard.html](dashboard.html) | Live progress visualization (updated every sprint) |
| [docs/test_plan.md](test_plan.md) | Test plan per sprint, mapped to features |
| [docs/regression.md](regression.md) | Cumulative regression suite (which tests must always pass) |
| [docs/research/](research/) | Research phases 1-4, competitive landscape, scope reference |
| [docs/procedures/](procedures/) | BKMs (CI/CD, backup, rollback, env vars, etc.) |

---

## The Sprint Workflow

Every sprint follows these 10 steps in order. No exceptions.

### Step 1 — Context Load

- Read [docs/main_spec.md](main_spec.md) — current requirements, decisions, directions.
- Read [docs/research/](research/) — competitive intel, feature skeleton, scope reference.
- Read [docs/backlog.md](backlog.md) — current statuses, sprint order.
- Read [docs/regression.md](regression.md) — existing test coverage.
- Identify the **next sprint** (first with status `TODO` or `WIP`).

### Step 2 — Sprint Planning

- List the sprint's features, their REQ traces, and any `ACT-*` items that need Avi mid-sprint.
- **Sanity check:** Does this sprint make sense given what was learned in the previous sprint? Does it align with the spec's intent and the research findings?
- **If the plan does not make sense → STOP.** Present concerns to Avi with specific reasoning. Propose alternatives. Wait for Avi's decision before continuing.
- If plan is sound, confirm to Avi: *"Next: SPR-x.y — Title. N features. I'll need you for ACT-X, ACT-Y mid-sprint. Proceeding?"*
- **Wait for go-ahead.**

### Step 3 — TDD: Write Tests First (Red Phase)

- Open / create [docs/test_plan.md](test_plan.md).
- Append a section for the sprint: each feature → 1+ test cases.
- Each test row: `Test ID` (`T-F-x.y.z-n`) | `Description` | `Type` (unit/integration/e2e) | `Feature traced` | `Status` (`PLANNED`).
- Implement the test cases in `tests/` using `pytest-django`.
- Run `pytest -k "<sprint marker>"` — confirm **all new tests fail** (red).
- Mark them `RED` in test_plan.md.

### Step 4 — Implement (Green Phase)

- For each feature in the sprint:
  1. Mark `F-x.y.z` as `WIP` in [backlog.md](backlog.md) and matching `REQ-*` in [main_spec.md](main_spec.md).
  2. Write the minimal code to pass the feature's tests.
  3. Run that feature's tests — turn green.
  4. Mark feature `DONE` in both files.
  5. Commit with message: `F-x.y.z REQ-a.b.c: <short title>`.
- After all features green: run the **whole sprint test set** — confirm green.
- **ACT items:** If a feature needs Avi input (credentials, photo, DNS, etc.), pause on that feature, tell Avi exactly what to do, wait, then continue.

### Step 5 — Full Regression

- Run **entire regression suite** (`pytest`) — not just the sprint's tests.
- Must be **all green**. If anything broke, fix before proceeding. Never move forward with red tests.
- Update `requirements.txt` if any new packages were added during the sprint.

### Step 6 — Sprint Review & Demo

- **STOP. Do not proceed.**
- Summarize to Avi:
  - Features completed (IDs + titles)
  - Tests added (count, names)
  - Files touched
  - Any deviations from spec or decisions made along the way
- **Guide Avi through a demo** of the added features:
  - Exact commands to run locally (`python manage.py runserver`)
  - URL paths to visit
  - What to look for / verify
  - Expected behavior per feature
- **Wait for explicit approval** ("approved", "looks good", or equivalent).
- If Avi requests changes → add them as proper REQs/backlog/tests (see "Mid-Sprint Changes" below), implement, re-run regression.

### Step 7 — Next Sprint Planning Review

- Present the plan for the **next sprint** to Avi:
  - What features will be built
  - Expected duration / effort
  - Any ACT items Avi should prepare in advance
  - Any spec gaps or decisions needed
- **Wait for Avi's approval to continue.**
- If Avi wants changes to the upcoming plan → update backlog accordingly.

### Step 8 — Post-Mortem

- Reflect on the completed sprint:
  - **What went well** — keep doing these things.
  - **What can improve** — process friction, missing info, bad estimates, tech debt.
  - **Are we heading in the right direction?** — Check against north-star metric (inbound corporate inquiries) and spec intent.
- **Update files if post-mortem reveals improvements:**
  - Update [the_manager.md](the_manager.md) if process changes are needed.
  - Update [main_spec.md](main_spec.md) if requirements need clarification.
  - Update [backlog.md](backlog.md) if sprint structure needs adjustment.
- Propose changes to Avi if direction shift is warranted.

### Step 9 — Update Dashboard

- Update [docs/dashboard.html](dashboard.html) to reflect:
  - Overall progress (epics done / total)
  - Current sprint status
  - Test coverage summary
  - Upcoming work preview
  - ACT items pending from Avi

### Step 10 — Production Deploy Check

- Ask Avi: **"Should we deploy this sprint to production and test on babook.co.il?"**
- If yes → follow deploy procedure:
  - `git status` clean
  - Avi says "push" → `git push origin main` → Render auto-deploys
  - Smoke test on https://babook.co.il
  - If smoke fails → execute [docs/procedures/rollback.md](procedures/rollback.md)
  - Report outcome (commit hash, URL, smoke results)
- If no → sprint stays local, move to next sprint when Avi says "what's next".

---

## Epic Boundaries

- **If a sprint finishes an epic** and the next epic is NOT fully defined (stage = `DEFINITION`, no REQ table, no backlog sprints): **STOP.** Tell Avi the epic is complete and the next one needs spec work before implementation can begin.
- **Never implement an unspecced epic.** The flow is: DEFINITION → SPECCED (REQs written) → TRACKED (backlog created) → Implementation starts.

---

## Mid-Sprint Changes (Retroactive Integration)

When Avi requests new things during a sprint review:

1. **Add as proper REQ** in [main_spec.md](main_spec.md) with the next available ID in the relevant epic.
2. **Add as backlog feature** in [backlog.md](backlog.md) in the appropriate sprint.
3. **Write tests** for the new requirement.
4. **Implement** following the same TDD flow.
5. **The relationship between spec ↔ backlog ↔ tests must remain perfect.** As if the new requirement was there from the start. No "added later" markers — it's just part of the system.

---

## Tracking Integrity Checks

Run these checks at the start and end of every sprint:

| Check | Rule |
|---|---|
| Every `REQ-*` has a `F-*` in backlog | No orphan requirements |
| Every `F-*` traces to at least one `REQ-*` | No untraced features |
| Every `F-*` with status `DONE` has at least one test | No untested features |
| Every test traces to a `F-*` | No orphan tests |
| `backlog.md` and `main_spec.md` statuses match | Single source of truth |
| `ACT-*` items have statuses | Avi's actions tracked |
| `requirements.txt` matches actual imports | No missing dependencies |
| `regression.md` lists all passing tests | Full regression documented |

---

## Quick Command Map

| Avi says | Copilot does |
|---|---|
| "what's next" / "next sprint" / "continue" | Steps 1-6 (context → review), stop at review |
| "approved" / "ship it" / "looks good" | Steps 7-10 (next plan → deploy check) |
| "demo" / "show me" | Output local-test instructions only |
| "status" / "where are we" | Step 1 context load → summary, no action |
| "rollback" / "revert" | Execute rollback BKM |
| "deploy" / "push" / "go live" | Step 10 deploy only (assumes regression green) |
| "stop" / "hold" | Halt mid-step, do not proceed |
| "post-mortem" | Step 8 only |
| "plan next" | Step 7 only |

---

## Definition of Done — Sprint

A sprint is `DONE` only if **all** are true:

- [ ] All features in the sprint marked `DONE` in backlog
- [ ] All matching `REQ-*` marked `DONE` in spec
- [ ] All sprint tests green
- [ ] Full regression green
- [ ] Tests added to regression.md
- [ ] Avi approved review/demo
- [ ] Dashboard updated
- [ ] Post-mortem completed
- [ ] `requirements.txt` current

---

## Definition of Done — Epic

All sprint DoDs met across every sprint in the epic, **plus:**

- [ ] Epic-level acceptance criteria from spec are met
- [ ] Epic status updated to `DONE` in backlog
- [ ] Next epic's readiness assessed (SPECCED? TRACKED? Or needs work?)

---

## Environment & Technical Rules

- **Python venv:** Always `env\Scripts\activate` before any Python command.
- **Package management:** Add to `requirements.txt`, tell Avi to install. Never `pip install` directly.
- **Database:** SQLite at `data/db.sqlite3` locally. Migrations via `python manage.py makemigrations` + `python manage.py migrate`.
- **Tests:** `pytest` from project root. All tests in `tests/` directory.
- **Local server:** `python manage.py runserver` for demo/verification.
- **Static files:** `python manage.py collectstatic --noinput` when CSS/JS changes.
