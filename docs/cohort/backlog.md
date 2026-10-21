# cohort: Backlog

Spec: [spec.md](spec.md). Data model: [data_model.md](data_model.md).

Design chosen by Avi on 2026-10-21: **the teachers' room noticeboard**. All six
sprints built the same day, in dev, awaiting his review and his word to deploy.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-C.1 | The app, its frame and menu, the fixed disclaimer, the door: ask to join, Avi's requests screen, approval email | REQ-C.1 to C.6, C.42, C.45 | **DONE 2026-10-21** |
| SPR-C.2 | The exhibition: hang a site, cards, screenshots (method measured first), retake, upload fallback | REQ-C.10 to C.12, C.43 | **DONE 2026-10-21** |
| SPR-C.3 | Likes, stars, the comment thread with quoted replies, edit and delete | REQ-C.13 to C.16 | **DONE 2026-10-21** |
| SPR-C.4 | Tracks: the seven pages, owners, three links, the chat command | REQ-C.20 to C.23 | **DONE 2026-10-21** |
| SPR-C.5 | Course materials: video, file, course, Avi's editing | REQ-C.30 to C.34 | **DONE 2026-10-21** |
| SPR-C.6 | The REST API complete, phone walk-through of every task, screen contract, dashboard | REQ-C.40, C.41, C.44 | **DONE 2026-10-21** |

**Tests.** `tests/test_cohort_door.py`, `test_cohort_exhibition.py`, `test_cohort_tracks.py`, and `test_cohort_browser.py` (a teacher's whole job on a 390px phone; no sideways scroll and the disclaimer on screen after scrolling, at 390 and 1280; the board in the top half of a phone). No test makes a network call: screenshots come from a fake.
