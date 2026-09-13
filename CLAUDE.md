# Project instructions — babook.co.il (this repo)

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
