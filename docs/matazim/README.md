# מט״צים — autonomous program space

This folder is the **only** source of truth for the מט״צים space at
`babook.co.il/matazim`. It is a separate product with a separate spec, a
separate backlog, and its own visual and navigational world.

| File | What it holds |
|---|---|
| `spec.md` | The charter, the separation contract, the data model, the requirements |
| `backlog.md` | Epics and sprints for building it |
| `inventory.md` | What already exists in the repo from the first (embedded) attempt, and what happens to each piece |
| `brief-litala.md` | The client brief from רשת עתיד, in her words, and what it changes here |
| `prototype/` | Her three prototype screens, read 2026-09-09: full screen-by-screen reading and the design system they settle |

**Relationship to the rest of `docs/`**

- `docs/main_spec.md` Chapter 10 and `docs/backlog.md` EPIC-10 describe the
  **first attempt**, where מט״צים was a section inside babook. That approach is
  superseded. Those two sections stay in place as history and get a pointer to
  this folder; no new requirement is ever added to them.
- Chapters 1 to 9 of `docs/main_spec.md` still bind the parts of the platform
  that מט״צים **runs on** (course engine, auth, deploy, admin). They do not
  bind how מט״צים looks or navigates.

Decided with Avi on 2026-09-09.
