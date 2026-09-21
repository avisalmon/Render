# Instructions for any assistant working in C:\Projects\Render

**The standing rules live in [`CLAUDE.md`](../CLAUDE.md) in the repo root, and
in the two process files it points at. Read those; this file is a pointer so
that a tool which looks here finds the same answer rather than a second one.**

- [`CLAUDE.md`](../CLAUDE.md) — the standing rules for working in this repo.
- [`docs/building_an_app.md`](../docs/building_an_app.md) — the authority for
  building a new app. Read it in full before any nontrivial app work; it
  changes as Avi adds to it, so re-read rather than remember.
- [`docs/the_manager.md`](../docs/the_manager.md) — the sprint loop for the
  main site.
- [`docs/README.md`](../docs/README.md) — the map of the documentation tree.

Two rules are repeated here because getting them wrong is expensive and nobody
should have to follow a link to learn them:

- **`git push` deploys to production at babook.co.il. Never push without Avi
  saying so.** Commit freely; push on his word only.
- **The virtualenv is `env`**, always, and nothing installs packages without
  him. New dependencies go into `requirements.txt` and he runs pip.

This file used to carry its own copy of the workspace conventions, which drifted
(it still pointed at a `C:\Users\asalmon\` path that no longer exists). One
truth, pointed at from wherever somebody looks.
