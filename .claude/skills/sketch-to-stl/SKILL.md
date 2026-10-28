---
name: sketch-to-stl
description: >
  Technology skill, tested 2026-10-28: turning a person's hand sketch (a photo) into a
  printable STL through a chat with an OpenAI model, and changing the part by chat after.
  The model writes OpenSCAD (or CadQuery) code, the server builds it, the model sees a
  render and corrects itself. Covers which model, what it costs, how much memory a build
  takes, where it can run (Render vs Google Cloud Run vs the browser), the safety rules,
  and working reference code. TRIGGER: an app or feature that makes 3D parts, STL files,
  3D printing, CAD from a sketch, "sketch to STL", OpenSCAD, CadQuery, or "the 3D app".
---

# Sketch to STL, through a chat

Tested by Claude for Avi on 2026-10-28, before any app existed, to know whether
the capability is real and what it costs. It is. This file is what was learned;
`reference/` holds the code that ran.

## How it works (the one idea to keep)

**No model writes an STL.** The model writes code for a CAD engine, the server
runs the code and exports the STL, and the model is shown a render of what it
built so it can check itself. Every change in the chat ("3 mm walls", "add a USB
slot") is an edit to that code. The conversation history *is* the design
history; the latest code is the part.

The loop, per person turn:

1. Send the history (and the sketch photo on the first turn) to the model.
2. The model answers JSON: `message` (to the person), `assumptions` (everything
   the sketch did not say), `code` (the whole part, or null to ask first).
3. Build the code with a time and memory limit. On an error, send the error
   back and ask for a fix (up to 3 times).
4. Render three views (iso, top, front) and, once after the first build, show
   them to the model: "compare with my sketch; fix or confirm".
5. Show the person the message, the assumptions and a 3D view; offer the STL.

The system prompt that worked is in `reference/trial_openscad.py` (`SYSTEM`):
millimetres, read every dimension, assume and say so rather than stop, one
parametric file with the key sizes as named variables at the top, no
`import()`/`include`/`use`, `$fn` at most 64.

## Which model (measured, the same 4-turn conversation)

Test: Avi's box sketch (100 x 80 x 27 mm, 2 mm walls, four 6 mm holes;
`reference/test_sketch.jpg`), then a self-check, then "3 mm walls, 5 mm
rounded corners, a lid with a 1 mm lip", then "a 12 x 6 mm USB slot 8 mm
above the floor".

| Model | Result | Per turn | 4 turns |
|---|---|---|---|
| gpt-6.1-sol ($2 / $10 per 1M in / out) | right every turn | 5-15 s | $0.038 |
| **gpt-6.1-terra ($1 / $5)** | **same quality as sol** | 6-15 s | **$0.020 (CadQuery), $0.017 (OpenSCAD)** |
| gpt-6-luna ($0.10 / $0.50) | holes in the wrong walls, not caught by its own self-check; lid floating 22 mm up | 17-25 s | $0.004 |

**Use gpt-6.1-terra.** About half a cent a turn; a 20-turn chat is about 15
cents because the earlier history is billed at the cached rate (a twentieth).
Prices from developers.openai.com/api/docs/pricing on 2026-10-28: re-read
them, they change. Every model ignored a fifth small hole in the sketch:
show the assumptions and let the person correct them.

The models on this account change; list them first
(`client.models.list()`), and note `gpt-image-1` was listed but refused while
`gpt-image-2` worked (image models, a different job, same lesson).

## Which engine

| | CadQuery 2.8 (Python) | OpenSCAD 2021.01 |
|---|---|---|
| Quality in the test | right | right, same reading, same assumptions |
| Memory per build | ~340 MB (328 MB just to import) | **45-85 MB** |
| Time per build | ~3 s | 1 s plain; 7-8 s once rounded corners come in |
| Disk | 1.3 GB of Python packages | ~100 MB |
| Safety | arbitrary Python: needs a real sandbox | **a closed language**: no files, no network (forbid `import()`, `include`, `use`) |
| Rounded edges, fillets | strong | weaker and slower (minkowski/hull); newer nightly builds are much faster |

**Default to OpenSCAD.** It is the one that can live on babook's own server
and the one models are safe to run. Move a part to CadQuery only when it needs
real fillets and chamfers that OpenSCAD cannot do well, and then run it in a
sandbox (below), never in the web process.

## Where it runs

babook's Render web service is the `starter` plan: **512 MB**, already running
the site. Measured locally, not yet on Render:

1. **OpenSCAD on the existing Render server: the first choice.** 85 MB fits
   beside the site. Install: Render's Python runtime has no apt, so `build.sh`
   downloads the standalone Linux AppImage and unpacks it with
   `--appimage-extract` into `vendor/openscad/` (gitignored), never fatal to a
   deploy (`reference/build_sh_openscad.diff`). Run `vendor/openscad/AppRun -o
   out.stl in.scad` with `QT_QPA_PLATFORM=offscreen`, a timeout, and a memory
   limit. **Not yet verified on Render itself**: the first sprint of the app
   verifies it with `reference/openscad_check.py` (a superuser-only page that
   builds `openscad_fixture.scad` and reports time, peak memory and the
   container's limit). Never build inside the request: queue the build, run
   it in a subprocess, and let the page poll ("building..."); one gunicorn
   worker blocked for 8 s blocks everyone.
2. **Google Cloud Run: the fallback**, if Render cannot install or hold it,
   or for CadQuery. A container that starts per build and costs nothing idle
   (Avi already has a Google Cloud account for Books). Cents per thousands of
   builds; 5-10 s cold start; Google's own sandbox per container.
3. **The person's browser: the bonus.** OpenSCAD has a WebAssembly build, so
   the build can run on the person's computer: no server cost, no sandbox to
   build. The server then only talks to OpenAI. Worth a spike in the app.

## Safety, whatever the engine

- The code comes from a model that read a person's photo: treat it as
  untrusted. OpenSCAD: reject `import(`, `include <`, `use <` before building.
  CadQuery: only in a container with no secrets, no network, no disk beyond a
  temp folder.
- A time limit (60-90 s) and a memory limit on every build; a size limit on
  the STL.
- The sketch photo goes through the site's image check (`app/safety.py`),
  like every upload.
- Cost cap per person per day in our own code, not only the vendor's settings
  (methodology 24).

## The view the person needs

A 3D viewer in the page (three.js loads STL; free), the message, the list of
assumptions to correct, and "Download STL". The three-view PNG in
`reference/trial_openscad.py` (`render`) is for the model's self-check, not
for people.

## Gotchas from the test

- Measuring memory on Windows: a venv's `python.exe` is a launcher that starts
  the real interpreter as a child; measure the children too (the first reading
  said 4 MB).
- A CadQuery `Workplane.val()` is only the first solid: a box and a lid side
  by side report the box's size. Count solids, or measure the STL.
- Ask the model to lay printable parts flat on z = 0 and check it (luna's lid
  started at z = 22).
- The reference scripts carry the scratch paths of the test PC (the OpenSCAD
  binary, the output folder); change them before running.

## Reference

- `reference/trial_openscad.py`, `reference/trial_cadquery.py`: the full
  conversation harness (prompt, build, repair, render, self-check, cost ledger).
- `reference/ledger_*.json`: tokens, seconds and dollars per turn, per model.
- `reference/openscad_check.py`, `reference/openscad_fixture.scad`,
  `reference/build_sh_openscad.diff`: the Render check, ready for sprint 1.
- `reference/test_sketch.jpg`: the sketch used.
- The results page sent to Avi: https://claude.ai/artifact/Qtij7tPRTrFYNwcdYLMRoM
