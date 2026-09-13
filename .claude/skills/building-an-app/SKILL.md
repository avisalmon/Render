---
name: building-an-app
description: >
  Standing methodology for building any new app inside this Django site (babook.co.il):
  full per-app encapsulation, database models only (never text/JSON as real data),
  a Django REST Framework CRUD API for every module, and the interview-first kickoff
  sequence (thin intro spec, then a standalone data model file that Avi approves
  before the full spec and normal backlog/sprint flow begin).
  TRIGGER: user says "new app", "build an app", "start an app", "app methodology",
  "add this to the methodology file", "kick off a new app", or asks to build a new
  feature area as its own isolated Django app on this site.
---

# Building an App on This Site

This skill is project-scoped: it lives in this repo only
(`.claude/skills/building-an-app/`), not in the user's global skills, because it is
still being written as we build apps and learn from it. Once it is mature, Avi moves
it to the central/global skill location himself; do not do that unless asked.

**The authoritative content is [docs/building_an_app.md](../../../docs/building_an_app.md), not this file.**
That doc is a living notes file Avi actively dictates additions to during builds
("add this to the methodology file"). Always re-read it at the start of any work this
skill covers — it may have grown since this SKILL.md was last touched. This file is
the trigger and the operational summary; the doc is the source of truth for the rules
themselves and the reasoning behind each one.

## What to do when this skill fires

1. Read `docs/building_an_app.md` in full before doing anything else.
2. If the request is "start a new app": run the kickoff sequence below, one step at a
   time, waiting for Avi at the gate in step 3. Do not skip ahead to writing code or a
   full spec before the data model is approved.
3. If the request is "add this to the methodology file": edit
   `docs/building_an_app.md` directly — add to the section it fits, or a new section —
   and confirm what was written. Do not just acknowledge verbally without writing it.
4. If the request is ongoing work on an app that already exists: apply the Core Rules
   from the doc as standing defaults (encapsulation, database-only data, DRF CRUD API,
   own docs directory, scoped migrate/deploy) unless Avi has recorded a specific
   exception for that app.

## The kickoff sequence (summary — see the doc for the full reasoning)

1. **Interview.** Ask questions until the app's purpose, audience, and boundaries are
   actually clear. Do not assume.
2. **Thin intro spec.** One short chapter, from that conversation: what the app is, in
   plain terms. Not the full spec.
3. **Data model file, standalone.** A separate markdown file (see Rule 4 in the doc)
   describing the main classes/modules and their relationships. Does not need to be
   complete, needs to be understandable. **Stop and wait for Avi's approval here.**
4. **Full spec, high-level chapters.** Only after the data model is approved.
5. **Normal flow.** Backlog, sprints, TDD — scaled to the app's size, per the doc's
   "Process weight scales to the app's size" section.

## Core rules, quick reference (the doc has the full text and reasoning for each)

1. Database data models only — never text or JSON files as the real data. A one-time
   JSON import to seed a model is fine; a JSON file the app keeps reading as its data
   is not.
2. Full encapsulation — an app never touches another app's models/views/data. A
   per-app need for extra user data becomes a one-to-one profile model in that app,
   not a change to the shared `User`.
3. Own base template and menu — never the main site's, and no link back to the main
   site unless explicitly asked for.
4. Own `docs/<app>/` directory: spec.md, backlog.md, a dashboard, and a **separate**
   data model document.
5. Migrate and deploy scoped to the app being worked on — `manage.py migrate
   <app_label>`, not a blanket migrate; don't bundle unrelated apps into one push.
6. Every app gets a full, documented CRUD REST API built on Django REST Framework —
   standard infrastructure from the start, not added later for the screens that
   happen to need it.

If any of the above seems to conflict with what a specific app already does (ustrip,
built before some of these rules existed, is the known case), that is a recorded gap,
not a reason to silently redo the older app's code — only touch it if asked.
