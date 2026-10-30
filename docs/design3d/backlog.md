# design3d: Backlog

Spec: [spec.md](spec.md). Data model: [data_model.md](data_model.md).
Technology: the sketch-to-stl skill.

Avi said "Start" on 2026-10-28 (data model approved, look B). Built in dev;
nothing ships without his word.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-D3.1 | The app and its frame in the print-bed look; the door: sign in, ask, wait, declined and ask again; Avi's people screen with spend and limits; the welcome email | REQ-D3.1 to D3.4 | **DONE 2026-10-28** |
| SPR-D3.2 | Designs and the chat: my designs, a design page on phone and computer, chat turns in the background with pictures, the model call with cost and the daily limit, stub mode | REQ-D3.10 to D3.15 | **DONE 2026-10-28** |
| SPR-D3.3 | Builds: OpenSCAD runner with limits and the file guard, STL and preview, repair up to three times, the self-check, versions | REQ-D3.20 to D3.22 | **DONE 2026-10-28** |
| SPR-D3.4 | The 3D view, sliders, continuing from a version, downloads | REQ-D3.23 to D3.25 | **DONE 2026-10-28** |
| SPR-D3.5 | Sharing and the gallery; the full API; phone and computer walk-throughs; OpenSCAD in build.sh and the check that it runs on Render | REQ-D3.30, D3.31, D3.40 to D3.43 | **DONE 2026-10-28**, live the same day |

**Tests.** `tests/test_design3d.py` (25: the door and asking again, the
people screen and limits, a chat turn in stub mode, asking before
guessing, repair and self-check, the file guard, stuck turns, one turn at a
time, the daily limit, pictures made small and private, sliders without
the model, continuing from a version, downloads, sharing the model only,
the STL renderer, the real OpenSCAD when present, the API, English and no
link to babook, every class defined) and `tests/test_design3d_browser.py`
(a maker's job on a phone from a new design to a slider change; the
computer's three columns; no sideways scroll at five phone widths).

**One real turn** (2026-10-28, gpt-6.1-terra, Avi's box sketch, through the
app's own code): $0.0066 including the self-check, a 1.2 s build, the box
100 x 80 x 27 mm with six sliders.

**Live 2026-10-28** (train T1028-163113). A one-off Render job built the sample part with the server's OpenSCAD: 0.4 s, 99 MB peak, vendor/openscad/AppRun present.

## D3.6 · The fast engine (2026-10-28)

Avi's "10x bigger and fillet the edges" ran for minutes and lost turns. An
engine evaluation (12 maker requests, three engines, $0.73 of model calls,
scratchpad eval3d) found OpenSCAD the language strong enough (21 of 24, as
CadQuery) and the 2021.01 engine the weak part; the Manifold snapshot built
the same code 20 to 180 times faster. CadQuery: best shapes, but 330 MB just
to load, so not beside the site.

- [x] build.sh pins OpenSCAD-2026.10.27 (sha256 checked), 2021.01 as fallback, `vendor/openscad/ENGINE` replaces a cached build
- [x] builder: `engine()`, `manifold()`, `--backend=Manifold`, inside-out check (`signed_volume`), whole-group kill, 200 MB cap
- [x] prompt follows the engine (`llm.system()`); the polyhedron winding line
- [x] People screen: the engine and the last 50 builds
- [x] Turn trail ("How this turn went"); downloads follow a live-built part
- [ ] Verify on Render after the ship: People screen says "2026.10.27 (Manifold)"

**One real turn** (2026-10-28, local, Manifold): "a 100 mm cube with a 20 mm
hole, all edges filleted 5 mm": model 16 s, build 0.57 s, the hole's rims
rounded too.

## D3.7 · Print-ready checks (2026-10-28)

- [x] `design3d/printcheck.py`: bed and contact, floating pieces, pieces that fuse, thin walls (axis rays over a 2D grid), size, overhangs
- [x] Run over all 60 parts of the engine evaluation before wiring: 0.01 to 2.2 s each; false alarms found and fixed (slivers under 0.15 mm, rounded bottom edges counted as overhang, a thread's feather edge now a note)
- [x] `Version.checks`, the chat line ("ready to print" / "N print warnings", tap opens the findings), the Files panel with Fix it, the self-check told the warnings
- [x] Older versions checked when first shown; the rename box follows the title the chat gives
- [x] Tests: 6 unit, 1 phone browser test (warning, tap, Fix it)
- [x] Memory measured: about 1.1 KB per triangle (30k triangles, 32 MB peak); bodies and walls checked up to 60k triangles, nothing above 150k (a note says to look in the slicer)

## D3.8 · Email me this chat (2026-10-29)

Avi: the chat "did not understand what I want"; would a better model do
better? Claude cannot see production data, and should not sign in as him.

- [x] `mail.chat_text` and `mail.email_chat`: the transcript plus code, pictures, previews and the current STL (15 MB cap, the rest listed)
- [x] `POST /design3d/d/<pk>/email/`: the admin, on his own designs only, to his own address; the button in the Design panel
- [x] Tests: the whole chat arrives; nobody else, and not Avi on someone else's design
- [ ] Replay Avi's chat through gpt-6.1-terra and gpt-6.1-sol and compare the parts and the cost

## D3.9 · Build first, mark a point, measure, Done, the part on top (2026-10-29)

From Avi's remote-holder chat (#4): three rounds of questions before any
part, the remote's length never asked, the changes never looked at, and
"creative" taken as a few holes.

- [x] Prompt: build first from estimates (card, coin, A4 for scale), ask everything at once with the length; ambiguous answers read, not re-asked; how a held object stays put; "creative" is a design idea
- [x] Self-check on every chat-built part, not only the first
- [x] Chat email: every version's code in the body and a signed link for a day to a page with the pictures (Claude's Gmail connection cannot open attachments)
- [x] Point mode (`Message.pin`, `llm.pin_text`, a picture of the view with the marker), Measure mode, grid 10 mm
- [x] Done page: view, print check, downloads, email me the files, share, order a print (coming soon)
- [x] The part stays on top on a phone, Pinned / Pin to top, remembered
- [x] babook main page: design3d and BKM cards
- [ ] Replay chat #4 with its photos on gpt-6.1-terra and gpt-6.1-sol (needs a new chat email after the ship)

**Two real turns** (2026-10-29, "a wall holder for my TV remote, creative,
50 x 30 mm"): both models built at once and asked for the length. terra
$0.012, 29 s; sol $0.019, 37 s. Both made a rocket-shaped back plate with a
pocket; sol's words were richer, the shape no better.

## D3.10 · Requests mail Avi; invitations (2026-10-29)

- [x] `mail.request_notice`: asking, and asking again after a decline, emails every admin
- [x] `Invite` model, `access.let_in` (the one way in, which also mails the welcome), `views.invited`, the People screen form and list, withdraw
- [x] The token is burned by a conditional update, so two people opening it at once cannot both get in
- [x] API: /design3d/api/invites/ (admin only; creating one sends the email)
- [x] Tests: the notice once per request; signed out burns nothing; first person in with one welcome email; the same person again; a second person refused; withdrawn and expired refused; only Avi invites

## D3.11 and D3.12 · Several parts (2026-10-29, Chapter 7)

- [x] `design3d/parts.py`: the part list cleaned (8 at most), orientation (the hint unless a flat side is clearly better), plate rows on a 220 mm bed, a 3MF writer, the fit check (ray parity for overlap, point to triangle for tight fits)
- [x] `Part` model, `Version.file_3mf` and `Version.fit`; files under stl/ so the private file view serves them after its check
- [x] Builder `part=`; jobs build each part alone; a part's error names the part; slider builds keep the parts; the self-check sees the assembly and the fit warnings
- [x] Prompt: the parts contract (`part = "all";`, one module per part, the closing if-lines, hardware as `printed: false`)
- [x] Page: Assembled and Print plate, a chip per part to hide it, Pull apart, the parts list with each part's STL, All parts (3MF); a marked point names its part; Done page lists the parts
- [x] API: /design3d/api/parts/ (read only)
- [x] Tests: box and lid (two parts, the lid turned upside down, a 3MF with two objects, downloads, the file check, sliders, history), too tight and overlap, an undrawn part, the part list cleaned, a phone test of the whole flow

**Real turns** (2026-10-29, gpt-6.1-terra): "a box with a sliding lid" gave
two parts, the lid turned for printing; one sample overlapped (found by the
fit check), another had 0.25 mm clearance. "A two-piece pipe clamp with M3
screws and nuts" gave six parts, four of them hardware, and no fit findings.
About $0.011 to $0.015 a turn.

## D3.13 · Make a copy; a picture full size (2026-10-29)

- [x] `jobs.copy_design`: the shared part as version 1 of a new design (`Version.COPY`, `Design.copied_from`), with its own copies of every file, its sizes and its parts; one chat line saying whose it was
- [x] `POST /design3d/shared/<pk>/copy/`, "Make a copy" on the shared page
- [x] A picture in the chat is a button: full size in a dialog, Save (`?download=1`), Share (Web Share with the file, where the phone has it)
- [x] Fusion 360: answered in the spec (mesh import now; STEP needs the CadQuery engine, later)
- [x] Tests: the copy without the chat or pictures, the original untouched, only shared designs; Save is a download, still owner only; a phone test of the picture

- [x] 2026-10-29: Home button in the 3D view (REQ-D3.56), on the design, Done and shared pages; a phone test turns the view and comes back

## D3.14 · One-tap links for Avi, a link for everyone, who brought whom (2026-10-30)

- [x] Avi's "Invite a friend": one tap, a one-time link with WhatsApp, Email, Share and Copy and a ready message; no email typed, nothing mailed; signing up through the link lets the new person in at once
- [x] The invitation page explains design3d with three examples, Google first
- [x] Everyone's own link on My designs (`Maker.ref_code`, `/design3d/r/<code>/`), the door says who invited you, the request remembers it (`Maker.referred_by`); Avi sees "invited by" and "brought N"; each person sees how many joined through them; Avi's one-time links credit Avi
- [x] `_sharebox.html`: one share box for both
- [x] Home stops the glide left from a drag before it jumps back (the test taps it mid-glide)
- [x] Tests: the coupon by signup and by an existing member, the friend link through ask and approve with the counts, never yourself, an unknown code
- [ ] Next: the gamification plan (Avi, 2026-10-30), with these counts as one input
- [ ] Flaky under load (PM-78 rule, written down): in the full design3d run of 2026-10-30, `test_on_a_phone_mark_a_point_measure_keep_the_part_on_top_and_finish` timed out once (30 s) waiting for #d3-stick after `page.reload()`; it passed twice alone. Watch the nightly run; if it repeats, wait for the page's load event after the reload.
