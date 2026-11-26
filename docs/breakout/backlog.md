# breakout: Backlog

> Sprints for the app in [spec.md](spec.md), on the data model in
> [data_model.md](data_model.md). Status words: **planned**, **building**,
> **built in dev**, **shipped**. Each sprint ends with its tests green,
> screenshots read against the seed, and a post-mortem entry if anything was
> learned. Process: [building_an_app.md](../building_an_app.md). Nothing
> ships without Avi's word; shipping is the release train.

| Sprint | What it delivers | Spec | Status |
| --- | --- | --- | --- |
| **B.1** Skeleton and the first flagship | The `breakout` Django app with every model from the data model and its migrations; Profile on first visit; own base template, header, footer, sign-in in the app's look; DRF CRUD API for every model with the permissions of chapter 10; the library (cards, filters, client-side search) and the read-only experience page; the seed command with "המחשב שנכבה" written in full; the portal registry sweep; `docs/breakout/dashboard.html` | 2, 3, 10, 11 | **built in dev 2026-11-26** (53 tests: `tests/test_breakout_b1.py`, `tests/test_breakout_screens.py`; PM-99) |
| **B.2** The kit | "Print the kit" for N groups: one A4 PDF with the teacher's guide, the player pages and attached printables, scaled shopping list; Download rows; the test that no solution string reaches the player part | 4 | **built in dev 2026-11-26** (`breakout/kit.py`; `tests/test_breakout_b2.py`; the phone flow in `tests/test_breakout_screens.py` downloads it) |
| **B.3** Writing an experience | The editor: about, story, stations (add, edit, delete, reorder), hints, materials from the catalogue, material requests, printable upload through the checking view, final lock, review-and-publish with its checklist, draft and unpublish, version bump; sanitizer on every person-typed text | 5, 9 | planned |
| **B.4** Community | Like, comment (edit, delete), run report (public or private), report; counts on the cards annotated before filtering, tests with two of everything | 6 | planned |
| **B.5** Curation | The curator's desk: reports queue, material requests, hide / unhide with reason, flagship on / off, make a curator; the author's view of a hidden experience | 7 | planned |
| **B.6** Phone, screens, sweep | Every phone width on every page, the class-defined test, no-link-out, Hebrew-only, screenshots at phone, tablet and computer widths read against the seed, the full security sweep list, a second flagship experience | 8, 9, 11 | planned |

## Decisions taken along the way

| Date | Decision | Where |
| --- | --- | --- |
| 2026-11-26 | Headline approved; app for teachers; kids never in the app; signed-in only; Hebrew only; no AI in v1 | spec 0, 1 |
| 2026-11-26 | Data model approved with the section 7 defaults | data_model.md |
| 2026-11-26 | The kit is composed into text blocks first and drawn second, so the "no secret on a player page" promise is tested on the blocks, not by parsing a PDF | breakout/kit.py |
| 2026-11-26 | Player pages come one stack per group (group 1: stations 1 to N, then group 2 ...), each stamped "קבוצה g מתוך N", so the teacher tears the printout into piles | spec 4 |
| 2026-11-26 | The kit is a GET with `?groups=`; the Download row is written on that GET (signed-in only, so no crawler inflates it); junk counts fall back to 4, wild ones clamp to 1..30 | breakout/views.py |
| 2026-11-26 | An attached image is drawn full-page behind its cover line; any other file type gets the cover line and a note to print it from the experience page (no PDF merging library in the build) | breakout/kit.py |
| 2026-11-26 | The shopping list on the page and the kit form share one default (4 groups) and one number: typing in either updates the other | templates/breakout/experience.html |

## Known gaps

None yet.
