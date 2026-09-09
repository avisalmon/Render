# Inventory and retirement plan

What exists today from the embedded build (commit `fbd6ffc`, SPR-10.1), and
what happens to each piece now that the decision is **start clean**.

**It is in production.** `fbd6ffc` is on `main`, `render.yaml` runs `migrate`
and `seed_matazim` on every deploy, and `templates/base.html` renders the nav
entry for anyone with a membership. Chapter 10's "not deployed" note is stale.
So retirement means dropping live tables, not deleting dev-only code.

## Deleted

| File | Lines | Note |
|---|---|---|
| `app/matazim_models.py` | 359 | Six models. Shapes were right; they are re-declared fresh in `matazim/models.py` with the new names. |
| `app/matazim_views.py` | 881 | Built around the babook shell and babook URL reverses. |
| `templates/app/matazim/` (11 files) | ~1,300 | `_shell.html` extends `templates/base.html`, which is the exact decision being reversed. Copy is worth re-reading before rewriting. |
| `static/matazim.css` | 327 | Written as a `.matazim-theme` scope remapping babook tokens. The new stylesheet stands alone. |
| `tests/test_spr_10_1.py` | 902 | 16 tests. Behavioural assertions (funnel, join codes, permissions) are worth re-reading as a checklist for the new suite. |
| `app/management/commands/seed_matazim.py` | 175 | Replaced by a seed inside the new app. |

## Ported verbatim, not rewritten

The entrance-test checker is 900 lines of working geometry with no presentation
in it. Rewriting it would be waste, so it moves into `matazim/entrance/`
unchanged. **Flagging this as my call, not Avi's**: if "completely clean" was
meant to include this too, say so and it gets rewritten.

| File | Lines |
|---|---|
| `app/matazim_geometry.py` | 437 |
| `app/matazim_check.py` | 168 |
| `app/matazim_targets.py` | 287 |
| `app/management/commands/generate_matazim_targets.py` | 107 |

## Babook hooks removed (RULE-1, RULE-4)

| Location | What it does |
|---|---|
| `templates/base.html:75-76` | Desktop nav icon linking to `matazim_home`. |
| `templates/base.html:181` | Drawer entry linking to `matazim_home`. |
| `app/context_processors.py:25-27,55` | Computes `show_matazim` with a `ProgramMembership` query on **every page load for every logged-in user**. Removing this is a small performance win on top of the separation. |
| `render.yaml` `startCommand` | `seed_matazim` call. |
| `app/urls.py:252-287` | 24 route entries, replaced by a single include. |

## Database retirement

Six tables live in the production SQLite: `app_program`, `app_school`,
`app_programmembership`, `app_programapplication`, `app_entranceattempt`,
`app_programstatuslog`, plus the M2M through-tables for `Program.staff` and
`School.leaders`, created by migrations `0096` to `0098`.

Plan:

1. **Check prod for real rows first** (Q6). `seed_matazim` runs on every deploy,
   so the `Program` row and any seeded schools certainly exist. What matters is
   whether any human applied. If anyone did, we export before dropping.
2. Take a backup, using the existing weekly backup endpoint rather than a new
   mechanism.
3. Ship a `DeleteModel` migration in `app`, in the same deploy as the new
   `matazim` app's `0001_initial`, so the window with neither is zero.
4. Watch the deploy, then confirm `ensure_schema` is happy (it rebuilds missing
   app tables generically, so verify it does not resurrect the dropped ones).

## Not started at all, in either version

Community feed, ימי שיא, project submissions, reporting and export,
certificate issuing, alumni.
