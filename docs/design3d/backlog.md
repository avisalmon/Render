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
