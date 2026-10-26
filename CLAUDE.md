# Project instructions — babook.co.il (this repo)

## What is where

[docs/README.md](docs/README.md) is the map of the documentation tree: what
belongs to babook, what belongs to each app, which files are process, and what
is archived. Start there when you do not know where something lives.

**babook keeps three jobs** and everything else is an app: identity and the
person's general profile, the training and certification engine, and the portal
that routes a person to their apps. The split is written out topic by topic in
**Chapter 0 of [docs/main_spec.md](docs/main_spec.md)**, including the rule that
an app consumes babook's engine and never copies it.

## Building or changing any app in this repo

Before starting a new app, or doing any nontrivial work on an existing one
(matazim, ustrip, or whatever comes after them), load and follow the
**building-an-app** skill (`.claude/skills/building-an-app/SKILL.md`) and
read [docs/building_an_app.md](docs/building_an_app.md) in full. That doc
is the living record of the standing rules for how apps get built on this
site (encapsulation, database-only data models, one-time seeding, a full
DRF CRUD API per app, the interview-first kickoff sequence, and more as
Avi adds to it) — do not proceed on Django app work without checking it
first, and do not rely on memory of what it said last time, since it
changes as we learn things.

When Avi says anything like "add this to the methodology file," edit
`docs/building_an_app.md` directly (not this file) — see the skill for
where new entries go.

## Every lesson goes back to FullStackBKM (standing rule, all chats)

This repo is where we learn; **FullStackBKM is where the learning is kept
and shared.** Avi shares it with friends so they always know what he
learned here. Local: `C:\Projects\FullStuckBKM` (old spelling on disk).
GitHub: https://github.com/avisalmon/FullStackBKM. There is no other BKM.

**A post-mortem is mandatory**, not optional, whenever:
- Avi corrects how something was done, or says it was wrong;
- a bug reaches production, or a review, screenshot, or full regression
  finds something the sprint's own tests missed;
- we change how we work (a new step, a better way, a new check);
- a sprint or checkpoint ends (even if the answer is "nothing new").

**Each post-mortem** gets an entry in [docs/postmortems.md](docs/postmortems.md):
what happened, why our process let it happen, the rule that now prevents
it, and where it landed. It lands in **both** places:
1. here: `docs/building_an_app.md`, the relevant `docs/` file or
   `.claude/skills/` skill;
2. in FullStackBKM: written in general terms (no babook specifics, plain
   language its tests accept), edited in `.claude/skills/` or `docs/`,
   mirrored with `python scripts/sync_skills.py`, checked with its
   `pytest -q` and `ruff check .`, committed **and pushed right away**.

**FullStackBKM changes need no approval** and are pushed immediately. This
is the opposite of babook, where pushing still waits for Avi's word.

**Policing:** `python scripts/bkm_drift.py` lists what this repo knows that
FullStackBKM does not; run it at every sprint end. A git pre-push hook
refuses to push babook while a post-mortem entry is still `BKM: pending`
(the only way past is `BKM: deferred - <reason>` written in the entry).

## Publishing: only the release train (standing rule, all chats and the mail bot)

Many agents work on this repo at once, so **nobody pushes to main except the
release train** ([docs/procedures/release_train.md](docs/procedures/release_train.md)).
A pre-push hook refuses everything else.

- When Avi says push, deploy or publish:
  `.\env\Scripts\python.exe scripts\train.py ship --app <app> --run --wait 3600`,
  then report the record it prints. Never `git push` to main yourself, and
  never set `RELEASE_TRAIN` or `RELEASE_TRAIN_OVERRIDE` (that one is Avi's).
- **A commit is "ready to ship"**: any train may carry it (postmortems PM-13).
- While working, run your app's tests. The full suite runs every night, once,
  for everybody; don't run it yourself.
- At the start of work, read the board:
  `C:\Users\avisa\.claude\release-train\board.md`. A failure it names as your
  app's is yours to fix.
- Before editing a shared file (`render.yaml`, `mysite/settings.py`,
  `mysite/urls.py`, `requirements*.txt`, `pyproject.toml`, `CLAUDE.md`):
  `scripts\train.py claim <path> --by <app> --why "<what>"`; `release` it after.
- A test you know fails and cannot fix now goes in `tests/known_failures.txt`
  with its owning app, the date and why, never silently.

**"Poke the train"** (Avi, 2026-10-26): `.\env\Scripts\python.exe scripts\train.py poke`.
It does the most useful thing at once: the watchdog, then a train if anything
is waiting, otherwise the full regression right now. If a train is already
running it says so and leaves it alone. Report what it printed.
