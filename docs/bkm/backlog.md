# bkm: Backlog

Spec: [spec.md](spec.md). Data model: [data_model.md](data_model.md).

A small app, so a light process (building_an_app.md, "Process weight"):
one sprint, built and shipped the day Avi approved the data model.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-B.1 | The whole app: the wall and its message, the gate and sign-in (Google first), the phone notice, cards with likes and stars, a BKM's page with the four steps and the conversation, the API, the chat command, the first three BKMs with their pictures | REQ-B.1 to B.5, B.10 to B.16, B.20 to B.22, B.40 to B.42 | **DONE 2026-10-26** |

**Adding a BKM later** (Avi says "I have a new BKM"): write
`bkm/migrations/00NN_<slug>.py` (one `get_or_create`, the pattern of 0002),
put its picture at `bkm/seed_assets/<slug>.jpg` (960x720), run the bkm
tests, push. `seed_bkm` attaches the picture on the deploy.

**Tests.** `tests/test_bkm.py` (the wall, the gate, likes and stars,
the thread, the API, the command, the seed run twice, English with a date
on the page, no link to babook, every class defined) and
`tests/test_bkm_browser.py` (a visitor's road from a card to a reply on a
computer; the phone notice and its dismissal; no sideways scroll at five
phone widths and 1280).
