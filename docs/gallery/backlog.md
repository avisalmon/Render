# gallery: Backlog

Spec: [spec.md](spec.md). Data model: [data_model.md](data_model.md).

Kickoff done 2026-11-09: interview, intro spec, data model (approved), full
spec. Built in dev; pushed only on Avi's word, through the release train.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-G.1 | The app and its frame: `gallery` Django app mounted at `/gallery/`, cohort's noticeboard look copied in, menu, Hebrew/English switch remembered, sign-in pages in the gallery's look, Person row, DRF skeleton, portal registry entry | REQ-G.1 to G.3, G.6, G.100 to G.103 | **DONE 2026-11-09** (dev) |
| SPR-G.2 | Pages: Training and Topic (seeded once), the first-post training question, hang a page, screenshots with upload fallback, edit and delete | REQ-G.4, G.5, G.10 to G.13, G.31 | **DONE 2026-11-09** (dev) |
| SPR-G.3 | Likes, stars, the comment thread with quoted replies | REQ-G.20 to G.23 | **DONE 2026-11-09** (dev) |
| SPR-G.4 | People and search: a page for every person, search box and filters, no AI | REQ-G.30, G.32, G.33 | **DONE 2026-11-09** (dev) |
| SPR-G.5 | Skills without AI: the skills tab, safe upload of SKILL.md or zip, SkillVersion and SkillFile, Claude Code and Copilot packages, downloads, the plain safety checks | REQ-G.40 to G.42, G.50, G.55 (layout part), G.105 | **DONE 2026-11-09** (dev) |
| SPR-G.6 | The skill chat: duplicate check, AI safety reading (model chosen by measuring against planted good and bad skills), refuse-explain-propose, publish as agreed with tags, 40-cent ceiling, AICall rows, fail is a no | REQ-G.51 to G.56, G.60, G.63, G.64, G.104 | **DONE 2026-11-09** (dev) |
| SPR-G.7 | Strikes and limits: block on the second strike, the email to Avi, four updates with the full check, unlimited grant | REQ-G.61, G.62, G.70 to G.73 | **DONE 2026-11-09** (dev) |
| SPR-G.8 | Avi's screens and BKMs: delete anything, trainings, topics, people, numbers, BKM cards | REQ-G.80, G.81, G.90 to G.94 | **DONE 2026-11-09** (dev) |
| SPR-G.9 | Whole walk-through on the narrowest phones and desktop, both languages by eye, security sweep (methodology 51), screen contract, dashboard | REQ-G.100, G.101, G.105 | **DONE 2026-11-09** (dev) |

**MVP (SPR-G.1 to G.4), 2026-11-09.** Built in dev, not pushed. A visitor sees everything; a signed-in person hangs pages (after the training question), likes, stars and comments; search without AI; Hebrew and English. Avi can make BKM cards and delete anything. Trainings, topics and people are edited in Django admin until SPR-G.8. Tests: `tests/test_gallery_mvp.py` (31). Checked on screenshots at 320, 360, 390 and 1280, both languages; a newcomer walked from the link to a hung page on a 360px phone.

**SPR-G.5, 2026-11-09.** Skills tab, skill page with every file readable (escaped, never rendered), downloads for Claude Code and Copilot (counted, open to all), safe upload (zip read in memory; size and count checked before decompressing; no paths out, no links, no inner archives, text only), plain checks for ten kinds of danger, limits (2 skills, 4 updates, blocked). An upload opens a chat and stops there: nothing is published until the AI reads it (SPR-G.6). Tests: `tests/test_gallery_skills.py` (46).

**SPR-G.6 and G.7, 2026-11-09.** The skill chat with the real model (gpt-6-luna, measured): similar-skill check, safety reading that also writes the card's description, topics and platform note, refuse-explain-fix with a fixed file checked again, publish as shown, replies that can change the proposal, retry when the model fails, a 40-cent ceiling priced before each call, every call in AICall (failed ones too), strikes, the block and one email to Avi. Walked live in dev on a 390px phone: a clean skill published, a risky one refused with the first-strike warning. The unlimited grant, unblocking and update reset are in Django admin until SPR-G.8. Tests: `tests/test_gallery_chat.py` (19).

**SPR-G.8, 2026-11-09.** Avi's screens at `/gallery/manage/` (404 for anybody else): numbers (totals, people, pages, skills and AI cost per training including "other" and "not answered", cost per person, chats that hit the ceiling, what "other" people wrote), people (search, blocked only, per person: unlimited skills, lift a block, reset a skill's updates, strikes and chats), trainings (add, rename, close, reorder), topics (add, rename, reorder). Counts are subqueries, never a Count beside another join. Tests: `tests/test_gallery_manage.py` (8).

**SPR-G.9, 2026-11-09.** Security sweep (methodology 51): two findings fixed with tests first, daily AI caps per person and site-wide, and cost records that blocked deleting an account; an open redirect on the people screen caught by its own test before it ran. The REST API gained skills, skill chats (start and act, same rules as the page), AI calls and strikes (Avi only). Screen contract `tests/test_gallery_screens.py`: 23 screens as their role at 320, 360, 390 and 1280 plus English at 360; it found the cork contrast, 30px targets, a small upload field and two unlabelled fields, all fixed.

**Tests.** Each sprint brings its own `tests/test_gallery_*.py`. No test makes a
network call: screenshots, OpenAI and mail come from fakes. The skill chat is
tested with a set of planted dangerous skills that must all be refused.
