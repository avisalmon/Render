# Breakout room app: spec

> **Status: data model approved 2026-11-26; spec in chapters 1 to 13;
> B.1 (skeleton, library, experience page, API, flagship seed) and B.2
> (the printed kit) built in dev 2026-11-26, not yet shipped.** Working name for the
> app, the URL and this folder: `breakout`. Avi may rename it.
> Data model: [data_model.md](data_model.md). Process:
> [building_an_app.md](../building_an_app.md).

## Chapter 0: the interview so far

What Avi said on 2026-11-26, in his words:

> just a tool to create desk paper and craft breakup experience.
> I will explain later on

Decisions already given:

- Audience: a teacher and teenagers (school / מט״צים setting).
- Access: signed-in babook users only; the shared login is the gate.
- Language: Hebrew only (RTL).

Avi's explanation (2026-11-26, from Hebrew, in short): he has to host a
large group of middle-school students on technology leadership, computers
and programming, with no computers for them. The answer is an escape-room
experience without a room: a rolling riddle built only from cheap office
and craft materials (paper, bristol board, scissors, a printer, safety
pins, staplers, insulating tape; no 3D printing, nothing expensive). From
that came the app: a site that holds such "breakout" experiences, where any
signed-in user can add one and others can download it, run it, comment and
like. A few flagship experiences by Avi seed it. The boundary of the genre
is the materials: anything you can buy cheaply in an office-supply shop.

Refinement (same day): the site is for teachers. A teacher prepares the
breakout and brings it to the class as raw material for groups. Beyond the
fun and playfulness, a stated goal is to take the kids away from screens,
the internet and AI for a while: physical things in the real world, written
riddles, reading comprehension, not through a computer.

Headline for the site's purpose (approved by Avi, 2026-11-26):

**Breakout: escape-room experiences made of paper, scissors and office
supplies. Pick one, print it, run it with your group; or publish your own.**

In Hebrew: חדרי בריחה מנייר: חוויות חדר בריחה שבנויות מדפים, מספריים וציוד
משרדי. בוחרים, מדפיסים ומריצים עם הקבוצה, או מפרסמים חוויה משלכם.

## Where the open questions landed

1. Who uses the app: **teachers only.** The teenagers never open it; the
   whole point is that their part happens on paper.
2. What it produces: **a printable kit** (player pages, cut-outs, a teacher's
   guide with the answers and the order of play) plus a shopping list of
   materials. Assumed A4 PDF; confirm.
3. AI: **none in the first version** (assumption). The site's stated goal is
   to take the kids away from AI; a writing helper for the teacher may come
   later as its own decision.
4. מט״צים: **standalone.** Nothing of מט״צים is touched or linked.
5. Sharing: **yes, a library.** Every signed-in user can publish; everyone
   can browse, download, like and comment. Avi's flagship experiences seed
   it. A curator (Avi) can hide a published experience.
6. Shape of one experience: **a story, an ordered chain of stations, each a
   puzzle with its materials, answer and hints, and a final lock** that the
   stations' answers open. "המחשב שנכבה" (below) is the model example.

## The style example (Avi: "this is the style, use it for the build")

**"המחשב שנכבה"**: the school's robot crashed; the group is the engineering
team that brings it back. Each part is "repaired" by solving a paper puzzle,
and each solution yields a digit or a word of the final code.

1. Memory: cards of 0/1 sequences decoded to letters with a printed table.
2. Processor: logic gates drawn on bristol board, inputs marked with sticky
   notes, "run" by hand.
3. The bug: a short printed program in plain Hebrew with one wrong line;
   the right line hides a number.
4. Network: a message cut to strips and shuffled, numbered like packets;
   ordered by number it reads an instruction.
5. Algorithm: a pile of weighted cards sorted by written rules; the order
   is the code.
6. Power-up: an envelope closed with a stapler and four paper "locks"; the
   collected code opens it and inside is the message that the robot lives.

---

## 1. What breakout is (the thin intro spec)

### 1.1 In one paragraph

breakout is a library of **escape-room experiences without a room**, built
only from paper, scissors and office supplies, for teachers to run with a
group of teenagers. A teacher picks an experience, prints its kit, buys a few
cheap materials, and runs it in class; or writes their own experience and
publishes it for other teachers to download, run, like and comment on. The
teenagers never touch the app: their whole experience is on paper, at the
desk, in the real world.

Headline: **חדרי בריחה מנייר: חוויות חדר בריחה שבנויות מדפים, מספריים וציוד
משרדי. בוחרים, מדפיסים ומריצים עם הקבוצה, או מפרסמים חוויה משלכם.**

### 1.2 Why it exists

Avi had to host a large group of middle-school students on technology
leadership, computers and programming, without computers. The answer was a
rolling riddle in the spirit of an escape room, made of what an office has.
The site makes that reusable: one place that holds such experiences, shows
how to build and run each, and grows as teachers add their own.

Two goals, in this order: a genuinely fun and playful experience for the
kids, and a deliberate hour away from screens, the internet and AI, with
written riddles, reading comprehension and physical things to handle.

### 1.3 The boundary of the genre

An experience is in scope only if everything it needs can be bought cheaply
in an office-supply shop or found in a school: paper, bristol board, a
printer, scissors, envelopes, staplers, safety pins, insulating tape, sticky
notes, string, markers. No 3D printing, no electronics, no screens, nothing
expensive. The app enforces this gently: materials are chosen from a shared
catalogue, and a new material is a request, not a free text.

### 1.4 Who is in it

- **A teacher** (any signed-in babook user): browses, downloads kits, runs
  experiences, reports back, likes, comments, and writes and publishes their
  own experiences.
- **A curator** (Avi, and whoever he names): the same, plus hiding an
  experience or a comment that does not belong, and marking flagship
  experiences.
- **The teenagers**: not users. They appear only as the audience an
  experience is written for.

### 1.5 What it is not

Not a digital escape room, not a game the kids play on phones, not a timer
or scoreboard for the session, not part of מט״צים. Hebrew only. No AI in
the first version.

### 1.6 Standing rules that apply

Everything in [building_an_app.md](../building_an_app.md): own base
template and menu, database rows for all real data, a full DRF CRUD API,
one-time seeding of Avi's flagship experiences, every piece of content
editable in the app by its owner, an edit screen for every field a deploy
would otherwise change.

## Next steps (the kickoff sequence)

1. ~~Interview~~ done.
2. ~~Thin intro spec~~ this chapter.
3. ~~[data_model.md](data_model.md)~~ approved 2026-11-26.
4. ~~Full spec in chapters~~ below. Sprints: [backlog.md](backlog.md).

---

## 2. The library

The front page of the app is the library: every published experience as a
card. On a phone the first card starts in the top half of the first screen
(mistake 25); the one main action in the page head is "write an experience",
search and filters fold behind one slim line.

A card shows: title, tagline, ages, duration, difficulty, subjects, how many
teachers ran it, likes, and a flagship mark when it is one of Avi's.

Filters: subject, age range, duration, difficulty, "has runs". Sort: newest,
most run, most liked. Search is a client-side match over the rendered cards
(no AI, costs nothing, leaks nothing; building_an_app.md mistake 51).

## 3. One experience, as a teacher reads it

The experience page is written for a teacher deciding whether to run it and
then preparing it. It opens with what the thing is and one main action:
**"הדפיסו את הערכה"** (chapter 4). Below, folded sections with their value
showing (mistake 28):

1. **The story** the teacher reads to the group.
2. **The chain**: the stations in order, each with its name, mechanic,
   minutes, and what it contributes to the final code. Opening a station
   shows the kids' text, the puzzle, the solution and its explanation, the
   hints in order, the materials with quantities, and the setup notes.
3. **The final lock**: how the code is built, the code, the message inside.
4. **Materials**: the whole shopping list, grouped, with a "for N groups"
   control that scales it.
5. **Preparation**: prep time, teacher notes, attached printables.
6. **Runs** other teachers reported (chapter 6), **comments**, likes.

Everything typed by a person renders with `dir="auto"` (mistake 30) and any
text that may carry markup goes through the sanitizer before `|safe`
(mistake 50).

## 4. The kit

"Print the kit" asks one question, how many groups, and produces one A4 PDF
with three parts, built from the rows every time (data model, principle 2):

1. **Teacher's guide**: story, the chain with solutions, explanations,
   hints, the final lock and code, setup notes per station, prep checklist,
   and the shopping list scaled to the groups.
2. **Player pages**: for each station, a page the kids get: station name,
   story text, the puzzle. One copy per group. No solutions anywhere on
   these pages; a test proves no solution string appears in the player part.
3. **Attached printables**, appended in order, with a cover line saying
   which station each belongs to and how many copies to make.

Hebrew PDF is made the way exo makes its download (ReportLab, the Heebo font
from `static/fonts/`, python-bidi for shaping), in the app's own module
(`breakout/kit.py`); exo's code is the reference, not an import (Rule 2).
Each print is recorded as a Download row with the group count.

## 5. Writing an experience

Any signed-in teacher writes. The editor is a sequence of screens, each a
real object a person can add, edit, delete and reorder (methodology: "every
item is a real object"):

1. **About**: title, tagline, ages, group size, duration, prep time,
   difficulty, subjects, cover.
2. **Story**: the opening text and the teacher notes.
3. **Stations**: a list to add to and reorder by arrows; each station is
   its own form with the kids' text, puzzle, solution, explanation,
   contribution, mechanic, minutes, setup notes, hints (a list), materials
   (pick from the catalogue, quantity, note), printables (upload with a big
   labelled button, never a raw file input; mistake 28).
4. **Final lock**: description, code rule, code, message, setup.
5. **Review and publish**: a read-through of the whole thing as the
   teacher page will show it, a checklist of what is still empty (no
   stations, a station without a solution, no final lock, no materials),
   and the publish button. Publishing is immediate; `version` bumps on every
   later published edit, and the kit's footer prints the version.

A draft is visible to its author only. A published experience is edited in
place; the author may unpublish back to draft. A material not in the
catalogue is a request (data model 3), and until a curator approves it the
station names it in its note.

## 6. Community

- **Like**: one tap, one per person, undone by a second tap.
- **Comment**: flat, under the experience; the author of the comment edits
  and deletes their own; a curator hides.
- **Run**: "I ran this": date, groups, kids, actual minutes, a 1 to 5
  rating, what worked, what to change, public or private to me. Public runs
  show on the experience page and their count on the card. This is the
  signal the library is ranked by, more than likes.
- **Report**: a small "report" link on an experience and on a comment,
  with a reason; lands in the curator's queue (chapter 7).

Counts are annotated before filtering (mistake 20) and the tests build two
of everything so a wrong count can appear.

## 7. Curation

A curator (Profile.is_curator; superusers included, written down here) has
one extra screen, the curator's desk: open reports, open material requests,
and the list of experiences with hide / unhide and flagship on / off.
Hiding keeps the row and records who and why; the author sees "hidden by a
curator, because ..." on their own page and can edit and ask again by
republishing. A curator never edits another person's text.

Making a teacher a curator is a tick on their Profile in the curator's desk
(not in /admin/), recorded with who did it.

## 8. Look, language, device

Hebrew only, RTL, the app's own base template, header and footer (Rule 3).
Every class is named after its component with a `br-` prefix (mistake 7); a
test checks every class in the markup is defined in the stylesheet (mistake
13). Teachers browse on phones and print from computers, so: phone-first
list and detail screens, checked at 320, 360, 375, 390 and 412 (mistakes 34,
52); the editor is comfortable on a computer and usable on a phone.

breakout is not an official app yet, so it shows no "more on babook" menu;
when Avi makes it official: one line in `mysite/more_on_babook.py`, the menu
in its base template, and its page in the shared test.

## 9. Access and safety

Every page except sign-in requires a signed-in babook user; the sign-in and
sign-up pages are rendered in the app's own look against the shared `User`
table. No kid data anywhere (data model 6). Uploaded files live under the
app's own media folder, served through a checking view, not `MEDIA_URL`.
The security sweep (mistake 51) runs in the sprint that creates each
subject: `|safe` and uploads in B.3, the reporting and hiding paths in B.4
and B.5. No paid calls exist in this version, and the app's very first test
file blanks `OPENAI_API_KEY` anyway (mistake 26).

## 10. The API

Django REST Framework, under `/breakout/api/`, full CRUD for every model in
the data model (Rule 6), browsable, with these permissions: read for any
signed-in user on published experiences and their children; write on an
experience and its children for its author; Like, Comment, Run, Download,
Report create for any signed-in user, edit and delete for their author;
hide, flagship, material-request decisions and report resolution for
curators. Read-only owner fields are also enforced in `perform_create`, and
the test breaks both (mistake 4).

## 11. Seeding and content

Avi's flagship experiences are seeded by a management command from a file
in `breakout/seed_assets/`, once: the command checks each experience by
slug and leaves existing rows alone; a test runs it twice and proves the
second run changes nothing (methodology, "seeding is one-time only"). After
day one, flagship content is edited in the app like any other (Avi is its
author), never by a migration or a deploy.

The first flagship experience is **"המחשב שנכבה"**, written in full: six
stations with real puzzles, real solutions, hints, materials and a final
lock, so that the kit printed from it can be run in a class as is. Avi
reviews its text in the app before it is published.

## 12. Process weight

A medium app: spec.md and backlog.md as the two sources of truth, a
dashboard.html, one test file per sprint plus the app-wide guards (class
defined, phone widths, no link out, Hebrew only, CSRF cookie on pages that
post). No REQ-IDs. Each sprint ends with the screenshots read against the
seeded world (mistake 21), a post-mortem entry if anything was learned, and
the train ships it when Avi says so.

## 13. Later, by Avi's decision only

A writing helper for teachers (AI) with its own cap; share links for kits
without an account; a versions table; an English UI.
