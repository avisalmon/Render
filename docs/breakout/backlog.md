# breakout: Backlog

> Sprints for the app in [spec.md](spec.md), on the data model in
> [data_model.md](data_model.md). Status words: **planned**, **building**,
> **built in dev**, **shipped**. Each sprint ends with its tests green,
> screenshots read against the seed, and a post-mortem entry if anything was
> learned. Process: [building_an_app.md](../building_an_app.md). Nothing
> ships without Avi's word; shipping is the release train.

| Sprint | What it delivers | Spec | Status |
| --- | --- | --- | --- |
| **B.1** Skeleton and the first flagship | The `breakout` Django app with every model from the data model and its migrations; Profile on first visit; own base template, header, footer, sign-in in the app's look; DRF CRUD API for every model with the permissions of chapter 10; the library (cards, filters, client-side search) and the read-only experience page; the seed command with "המחשב שנכבה" written in full; the portal registry sweep; `docs/breakout/dashboard.html` | 2, 3, 10, 11 | **built in dev 2026-11-26** (53 tests: `tests/test_breakout_b1.py`, `tests/test_breakout_screens.py`; PM-101) |
| **B.2** The kit | "Print the kit" for N groups: one A4 PDF with the teacher's guide, the player pages and attached printables, scaled shopping list; Download rows; the test that no solution string reaches the player part | 4 | **built in dev 2026-11-26** (`breakout/kit.py`; `tests/test_breakout_b2.py`; the phone flow in `tests/test_breakout_screens.py` downloads it) |
| **B.3** Writing an experience | The editor: about, story, stations (add, edit, delete, reorder), hints, materials from the catalogue, material requests, printable upload through the checking view, final lock, review-and-publish with its checklist, draft and unpublish, version bump; sanitizer on every person-typed text | 5, 9 | **built in dev 2026-11-26** (`breakout/edit_views.py`, `edit_forms.py`, `text.py`; `tests/test_breakout_b3.py`; the editor's eight screens in the screen contract and a phone authoring flow) |
| **B.4** Community | Like, comment (edit, delete), run report (public or private), report; counts on the cards annotated before filtering, tests with two of everything | 6 | planned |
| **B.5** Curation | The curator's desk: reports queue, material requests, hide / unhide with reason, flagship on / off, make a curator; the author's view of a hidden experience | 7 | planned |
| **B.6** Phone, screens, sweep | Every phone width on every page, the class-defined test, no-link-out, Hebrew-only, screenshots at phone, tablet and computer widths read against the seed, the full security sweep list, a second flagship experience | 8, 9, 11 | planned |

## Decisions taken along the way

| Date | Decision | Where |
| --- | --- | --- |
| 2026-11-26 | Headline approved; app for teachers; kids never in the app; signed-in only; Hebrew only; no AI in v1 | spec 0, 1 |
| 2026-11-26 | Data model approved with the section 7 defaults | data_model.md |
| 2026-11-26 (evening, after B.1 to B.3 shipped) | **Not in the "more on babook" menu** until it looks good (Avi). **Only Avi puts up challenges for now**: writing is gated to curators (`access.may_write`), teachers read, print and (B.4) react; the open-to-all editor of spec 5 waits for his word, one line to flip. One example experience is enough for the moment | access.py, edit_views.new, api.py |
| 2026-11-27 | **The word is "אתגר"** (m.), not "חוויה" (f.), in every person-facing string: screens, messages, the kit, the dashboard (Avi: "אתגר."). Code, URLs, model names and the docs' English "experience" stay as they are | templates/breakout/, breakout/*.py |
| 2026-11-26 | The kit is composed into text blocks first and drawn second, so the "no secret on a player page" promise is tested on the blocks, not by parsing a PDF | breakout/kit.py |
| 2026-11-26 | Player pages come one stack per group (group 1: stations 1 to N, then group 2 ...), each stamped "קבוצה g מתוך N", so the teacher tears the printout into piles | spec 4 |
| 2026-11-26 | The kit is a GET with `?groups=`; the Download row is written on that GET (signed-in only, so no crawler inflates it); junk counts fall back to 4, wild ones clamp to 1..30 | breakout/views.py |
| 2026-11-26 | An attached image is drawn full-page behind its cover line; any other file type gets the cover line and a note to print it from the experience page (no PDF merging library in the build) | breakout/kit.py |
| 2026-11-26 | The shopping list on the page and the kit form share one default (4 groups) and one number: typing in either updates the other | templates/breakout/experience.html |
| 2026-11-26 | The editor is plain POST forms with a redirect back, not fetch: it works the same on a flaky phone connection, and every write is a URL a test can hit. The DRF API stays the programmatic door | breakout/edit_views.py |
| 2026-11-26 | Slugs are ASCII, transliterated from the Hebrew title (`text.slug_for`), because Django's `<slug:>` converter is ASCII; same title twice gets -2, -3 | breakout/text.py |
| 2026-11-26 | Publishing is blocked only by what makes an experience unplayable (no station, a station without a puzzle or a solution); everything else on the checklist is advice | edit_views.checklist |
| 2026-11-26 | Any write to a published experience, including a hint or a material, bumps the version; a draft's writes do not. "Publish the updated version" bumps too | edit_views.touch |
| 2026-11-26 | Uploads: PNG, JPG, PDF only, 8MB, 25 megapixels; an image is decoded, turned upright and re-saved, a PDF is read for its header and page count; a draft may be deleted, a published experience is unpublished first; curators do not edit (they hide, B.5) | breakout/edit_forms.py |

## Known gaps

None yet.
