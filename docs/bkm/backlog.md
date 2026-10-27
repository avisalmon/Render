# bkm: Backlog

Spec: [spec.md](spec.md). Data model: [data_model.md](data_model.md).

A small app, so a light process (building_an_app.md, "Process weight"):
one sprint, built and shipped the day Avi approved the data model.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.1 | The whole app: the wall and its message, the gate and sign-in (Google first), the phone notice, cards with likes and stars, a BKM's page with the four steps and the conversation, the API, the chat command, the first three BKMs with their pictures | REQ-B.1 to B.5, B.10 to B.16, B.20 to B.22, B.40 to B.42 | **DONE 2026-10-26** |
| SPR-B.2 | The menu always on top; the public exhibition of projects (video, site, photo), signed in to open, likes, threads, search and filters, the BKM page's "made with it" | REQ-B.30 to B.36, B.43 | **DONE 2026-10-27** |
| SPR-B.3 | Avi's form for a BKM: edit every field and the picture, add, hide, remove; no deploy for content | REQ-B.23 | **DONE 2026-10-27** |

**Adding or changing a BKM** (since SPR-B.3): Avi does it on the wall,
signed in: "+ Add a BKM", or "Edit this BKM" on a card. No migration, no
deploy. The migration and seed assets were day one only.

**Tests.** `tests/test_bkm.py` (the wall, the gate, likes and stars,
the thread, the API, the command, the seed run twice, English with a date
on the page, no link to babook, every class defined) and
`tests/test_bkm_browser.py` (a visitor's road from a card to a reply on a
computer; the phone notice and its dismissal; no sideways scroll at five
phone widths and 1280).
