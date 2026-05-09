# The Manager — Process & Workflow

> Master process file for delivering babook.co.il.
> When Avi says **"what's next"**, **"run the next sprint"**, **"continue"**, or any equivalent — Copilot follows this file end-to-end without skipping steps.

---

## Cardinal rules

1. **Never `git push` without explicit Avi approval.** "Deploy" / "push" / "go live" are the only triggers.
2. **Never auto-install packages.** Add to `requirements.txt`, tell Avi to run pip.
3. **Never skip a step in this workflow.** If blocked, stop and ask.
4. **Always trace work to REQ-IDs.** Commits, PRs, tests, and notes reference `REQ-x.y.z` and `F-x.y.z`.
5. **Status truth lives in two files only:** [backlog.md](backlog.md) and [main_spec.md](main_spec.md). Update both together.

---

## Files this process touches

| File | Role |
|---|---|
| [.github/copilot-instructions.md](../.github/copilot-instructions.md) | Workspace conventions (env, deploy, project layout) |
| [docs/main_spec.md](main_spec.md) | Source of truth: requirements (`REQ-*`), decisions (`DEC-*`), acceptance |
| [docs/backlog.md](backlog.md) | Epic → Sprint → Feature, tracked status |
| [docs/dashboard.html](dashboard.html) | Live progress visualization |
| [docs/test_plan.md](test_plan.md) | Test plan per sprint, mapped to features |
| [docs/regression.md](regression.md) | Cumulative regression suite (which tests must always pass) |
| [docs/procedures/](procedures/) | BKMs (CI/CD, backup, rollback, env vars, etc.) |

---

## The workflow — what happens when Avi says "what's next"

### Step 0 — Boot
- Read [.github/copilot-instructions.md](../.github/copilot-instructions.md) (workspace rules).
- Read [docs/main_spec.md](main_spec.md) (current requirements & decisions).
- Read [docs/backlog.md](backlog.md) (current statuses).
- Read [docs/regression.md](regression.md) (existing regression coverage).
- State the boot summary back to Avi in 3–5 lines.

### Step 1 — Identify the next sprint
- Find the **first sprint** with status `TODO` or `WIP` in [backlog.md](backlog.md).
- List its features, REQ traces, and any `ACT-*` items that will need Avi during the sprint.
- **ACT items do NOT block sprint start.** Start the sprint, implement everything possible, and when a specific feature needs Avi input (credentials, account setup, DNS, etc.), pause *on that feature*, tell Avi exactly what to do, wait for response, then continue.
- Confirm to Avi: *"Next: SPR-x.y — Title. N features. I'll need you for ACT-X, ACT-Y mid-sprint. Proceeding?"* and **wait for go-ahead.**

### Step 2 — Plan tests (TDD setup)
- Open / create [docs/test_plan.md](test_plan.md).
- Append a section for the sprint: each feature → 1+ test cases.
- Each test row: `Test ID` (`T-F-x.y.z-n`) | `Description` | `Type` (unit/integration/e2e) | `Feature traced` | `Status` (`PLANNED`).
- Show the plan to Avi for sanity check before writing code.

### Step 3 — Write failing tests first
- Implement the test cases in `tests/` using `pytest-django`.
- Run `pytest -k "<sprint marker>"` — confirm **all new tests fail** (red).
- Mark them `RED` in test_plan.md.
- If a test passes accidentally — investigate; the test is wrong or already covered.

### Step 4 — Implement features
- For each feature in the sprint:
  1. Mark `F-x.y.z` as `WIP` in [backlog.md](backlog.md) and matching `REQ-*` in [main_spec.md](main_spec.md).
  2. Write the minimal code to pass the feature's tests.
  3. Run that feature's tests — turn green.
  4. Mark feature `DONE` in both files.
  5. Commit with message: `F-x.y.z REQ-a.b.c: <short title>`.
- After all features in the sprint are `DONE`: run the **whole sprint test set** — confirm green.

### Step 5 — Sprint review with Avi
- **Stop. Do not proceed.**
- Summarize to Avi:
  - Features completed (IDs + titles)
  - Tests added (count, names)
  - Files touched
  - Any deviations from spec / decisions made along the way
- Offer a **demo**: short instructions for Avi to verify locally (`python manage.py runserver`, URL paths to visit, accounts to use).
- **Wait for explicit approval** ("approved", "looks good", "ship it", or equivalent).
- If Avi rejects or asks for changes → loop back into Step 4 for the affected features.

### Step 6 — Promote to regression
- Append the sprint's tests to [docs/regression.md](regression.md).
- Re-run **full regression** (`pytest`).
- Must be green. If not — fix before deploy. Never deploy red.

### Step 7 — Update tracking artifacts
- [backlog.md](backlog.md): sprint status → `DONE`. All features `DONE`.
- [main_spec.md](main_spec.md): all touched `REQ-*` → `DONE`.
- [docs/dashboard.html](dashboard.html): no edit needed; it auto-renders from backlog.
- Commit: `SPR-x.y complete: <sprint title>`.

### Step 8 — Deploy (CI/CD)
- Confirm Avi explicitly says **"deploy"** / **"push"** / **"go live"**.
- Follow [docs/procedures/cicd.md](procedures/cicd.md):
  - `git status` clean
  - `git push origin main` → Render auto-deploys
  - Watch Render build log
  - Smoke test on https://babook.co.il (key URLs, login, health check)
  - If smoke fails → execute [docs/procedures/rollback.md](procedures/rollback.md)
- Report deploy outcome to Avi (commit hash, URL, smoke results).

### Step 9 — Loop
- Return to Step 0 only when Avi says "what's next" again. Never auto-continue.

---

## Quick command map (Avi → Copilot)

| Avi says | Copilot does |
|---|---|
| "what's next" / "next sprint" / "continue" | Run Steps 0 → 5, stop at review |
| "approved" / "ship it" / "looks good" | Run Steps 6 → 8 (regression + deploy) |
| "demo" / "show me" | Output local-test instructions only |
| "status" / "where are we" | Run Step 0 boot summary, no action |
| "rollback" / "revert" | Execute rollback BKM |
| "deploy" / "push" / "go live" | Step 8 only (assumes regression already green) |
| "stop" / "hold" | Halt mid-step, save state, do not proceed |

---

## Definition of Done (per sprint)

A sprint is `DONE` only if **all** are true:
- ✅ All features in the sprint marked `DONE` in [backlog.md](backlog.md)
- ✅ All matching `REQ-*` marked `DONE` in [main_spec.md](main_spec.md)
- ✅ All sprint tests green
- ✅ Tests added to [regression.md](regression.md)
- ✅ Full regression green
- ✅ Avi approved review/demo
- ✅ Deployed to babook.co.il and smoke-tested green (or formally deferred)

---

## Definition of Done (per epic)

Same as the sprint criteria, applied across **every sprint** in the epic, **plus** the epic-level acceptance criteria from the spec (e.g. §1.9 for EPIC-1).
