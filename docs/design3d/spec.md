# design3d: Spec

Status: **chapter 1 only, 2026-10-28, for Avi's review.** The data model is
in [data_model.md](data_model.md) and waits for his approval before the full
spec. The app is **design3d**, at `babook.co.il/design3d/` (Avi, 2026-10-28).

The technology is settled and measured in the `sketch-to-stl` skill
(`.claude/skills/sketch-to-stl/`): which model, what it costs, how much a
build takes, where it runs, and the safety rules.

## Chapter 1: What it is

**design3d is 3D design through a chat.** You tell it what you want to build:
in words, with a drawing or a hand sketch, with a written definition, or with
a photo of a real thing in the world. The chat asks about whatever it cannot
read or guess safely, then builds the part, shows it in 3D, and gives you a
printable STL. From there you keep changing it by talking ("make the walls
3 mm", "add a slot for the cable") or by moving its sizes on sliders.

**An example of the photo case.** You photograph your pencil and write "I
want a holder for this". A photo has no scale, so the chat asks for what it
cannot know (the pencil's diameter, how many pencils, how tall), and it
suggests putting a coin or a card next to the object next time. Only then
does it build.

### Who it is for

Avi, and the people he lets in. Every chat turn costs money (about half a
cent) and the tool is unusual enough to give only to chosen people.

- Anyone who reaches the site and is not in sees one thing: a form to ask
  for access, with a line about why they want it.
- Avi has an admin screen: who asked, approve or decline, who is in, and how
  much each person has spent.
- Signing in is the shared babook account (Google first, as in the other
  apps); being in is a separate approval, as in cohort.
- Each person has a daily spending limit, so one long evening cannot run up
  a bill: $2 a day by default (about 400 chat turns), changeable per person
  by Avi; Avi himself has none.
- A person Avi declined may ask again; the new request comes back to his
  screen.

### Designs are projects

A person has many designs. Each design stands on its own: its own chat, its
own memory of what was agreed, its own images, and its own versions of the
part.

- **The chat is the design's history.** What you asked, what the chat
  understood and assumed, and what it built, in order.
- **Every build is a version.** You can open any earlier version, see it in
  3D, download it, and continue from it; continuing from an old version does
  not delete the newer ones.
- **Sizes as sliders.** The chat names the part's key sizes (wall, height,
  diameter, clearance). Each becomes a slider; moving one rebuilds the part
  without asking the model, so it costs nothing, and makes it easy to tune a
  fit before printing.
- **Downloads.** The STL, for any version; and the OpenSCAD source, for
  whoever wants to keep editing it elsewhere.
- **Always there.** You come back to a design days later and carry on where
  you stopped; the chat remembers.

### Sharing, only when you choose

A design is private to its owner. Its owner can choose to share it; then the
other people in design3d see it in a shared gallery: the model only, meaning
its 3D view, its preview picture and its STL. Never the chat, and never the
pictures that went into it (Avi, 2026-10-28). Unsharing hides it again.

### Built for the phone

The natural way to use design3d is a phone in your hand: chatting, and taking a
photo straight from the camera of a sketch on paper or of the thing you want
to build around. It works on a computer too.

### What it accepts

Text; a photo or an upload of a drawing, a hand sketch or a written
definition; a photo of a real object. More than one image per message.

### What it is not

- Not for organic shapes (figurines, faces, characters). The method builds
  functional geometric parts: holders, boxes, mounts, brackets, enclosures,
  adapters, spacers.
- Not professional CAD: no STEP or assembly files for industry. Fusion 360
  opens the STL or the 3MF as a mesh (Insert Mesh, then Convert Mesh to a solid).
  A real STEP needs the CadQuery engine, which does not fit beside the site
  (engine evaluation, 2026-10-28); a later "precise mode" on its own server.
- Not a slicer or a printer controller: it gives you the STL; you print it.
- Not open to the public.

### Planned right after the first release

- **Make a copy** of a design someone shared, and continue it as your own;
  the original stays theirs. (Built 2026-10-29, REQ-D3.54.)
- **Print-ready checks** before download: the part lies flat on the bed,
  walls are not thinner than a nozzle can print, fits have clearance.
  (Built in D3.7, REQ-D3.45.)

### Decided by Avi, 2026-10-28

1. Name and address: design3d, `/design3d/`.
2. A shared design shows the model only (3D view, preview, STL); not the chat,
   not the pictures.
3. Daily limit: $2 per person by default.
4. A declined person may ask again.

---

Data model approved by Avi with "Start", 2026-10-28. Look: direction B,
"Print bed" (https://claude.ai/artifact/Eyxm3JuRN69LLd4hrdiTU6).
Requirements are `REQ-D3.n`.

## Chapter 2: The door

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-D3.1 | Signed out | `/design3d/` shows what design3d is, in two lines, and "Sign in" (Google first, email and password folded away). Nothing else. | DONE |
| REQ-D3.2 | Asking | Signed in but not in: one form, "why do you want in" (optional), and a button. Then "waiting for Avi" on every visit. Declined: "not approved" and a way to ask again, which puts the request back to pending. | DONE |
| REQ-D3.3 | Avi's screen | Requests waiting, people in, people declined; approve, decline, withdraw; each person's spend today and in total, and their daily limit (editable). Approving sends one email: you are in, with the link. | DONE |
| REQ-D3.4 | Its own frame | Own base template and menu (my designs, shared, and for Avi the people screen), the print-bed look, own error pages, no link to babook. Not in babook's portal until Avi asked for a card on the main page (2026-10-29, `app/portal.py`, EVERYONE: the app's own door asks to join). | DONE |

## Chapter 3: Designs and the chat

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-D3.10 | My designs | A list of my designs, newest first, each with its preview picture, title and when it was last changed; "New design" on top. | DONE |
| REQ-D3.11 | A design page | On a phone: the part on top, the chat below, the text box with the camera button at the bottom. On a computer: designs and chat on the left, the part in the middle, sizes and versions on the right. | DONE |
| REQ-D3.12 | A chat turn | I write, and may add pictures (camera or files, several). The turn runs in the background; the page shows what the turn is doing now ("Reading your message", "Building version 2", "Fixing a build error, try 1 of 3", "Checking the part against what you asked") with its running seconds from the server, a "taking longer than usual" line after two minutes, and the answer arrives without a reload; a ready part is on screen as soon as it is built. The answer shows the chat's message and its list of assumptions. | DONE |
| REQ-D3.13 | It asks before it guesses | When something important cannot be read or assumed safely (the scale of a photo), the chat asks instead of building. With a photo of an object it asks for a real measurement and suggests a coin or a card next to the object. | DONE |
| REQ-D3.14 | Pictures | Each picture is made at most 2000 px, its location data removed, checked by the site's image check, kept privately, and shown in the chat to its owner only. | DONE |
| REQ-D3.15 | The model and its cost | gpt-6.1-terra (a setting). Every turn records its tokens and cost. Over the person's daily limit, the turn is refused with the time it resets; Avi has none. Without a key the app runs in a stub mode that answers with a fixed part, so it can be developed and tested. | DONE |

## Chapter 4: Builds, versions and sizes

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-D3.20 | A build | The chat's OpenSCAD code is built on the server with a time limit (90 s) and refused if it reads files (`import`, `include`, `use`). The result is an STL, a preview picture and the part's size in millimetres. | DONE |
| REQ-D3.21 | It repairs and checks itself | A failed build goes back to the chat with the error, up to three times. After a design's first successful build the chat is shown a picture of what it built and corrects it if it does not match. | DONE |
| REQ-D3.22 | Versions | Every successful build is a version, numbered. Any version can be opened, seen in 3D, downloaded, and continued from; continuing from an old one keeps the newer ones. | DONE |
| REQ-D3.23 | Sizes as sliders | The chat names the key sizes with a sensible range. Each is a slider; "Apply" builds a new version from the sliders with no call to the model. | DONE |
| REQ-D3.24 | The 3D view | The part in 3D, turned by finger or mouse, on a print-bed floor, with its size written beside it. | DONE |
| REQ-D3.25 | Downloads | The STL and the OpenSCAD source of any version. | DONE |

## Chapter 5: Sharing

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-D3.30 | Share or not | A design is private. Its owner shares it with one switch and can unshare it. | DONE |
| REQ-D3.31 | The shared gallery | People in design3d see shared designs: preview, title, maker, a 3D view of the current version and its STL. Never the chat or the pictures. | DONE |

## Chapter 6: How it must behave

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-D3.40 | Phone first | Every screen works at 320 to 412 px and on a computer, with no sideways scroll. The camera opens straight from the text box. | DONE |
| REQ-D3.41 | Closed by default | Every page, file and API answer checks: signed in and approved, or Avi. A design's files only to its owner, or to people in when shared. | DONE |
| REQ-D3.42 | Full REST API | Rule 6: makers, designs, messages, pictures, versions (with a build action), parameters. | DONE |
| REQ-D3.43 | Runs on babook's server | OpenSCAD is downloaded by the build and runs beside the site; a build never runs inside a web request. If Render cannot hold it, the builds move to Google Cloud Run (sketch-to-stl skill). | DONE: verified on Render 2026-10-28, a build in 0.4 s at 99 MB peak |
| REQ-D3.44 | A fast engine, checked | The server runs a pinned OpenSCAD development snapshot (2026.10.27) for its Manifold engine, 20 to 180 times faster than 2021.01 on the engine evaluation of 2026-10-28; 2021.01 is the fallback if the snapshot cannot be downloaded. Every part is checked for an inside-out mesh (negative volume) and the error goes back to the model. The model's rules about rounding follow the engine installed. Every build is killed with its children at 90 s and capped at 200 MB (the site shares the 512 MB server; Manifold peaked at 70 MB). The admin's People screen names the engine and how the last builds went. | DONE in dev 2026-10-28 |
| REQ-D3.45 | Print-ready checks | Every built version is checked on the server (pure Python, under 1 s on the evaluation's parts): it sits on the bed with enough contact, no piece floats, no two pieces will fuse (under 0.2 mm apart), no wall is under 0.8 mm (a small thin spot is a note), it fits 220 x 220 x 250 mm, and overhangs that need supports are a note. The chat line says "ready to print" or "N print warnings" (tap opens the findings); each warning has Fix it, which sends the fix to the chat. The first part's self-check also tells the model the warnings. Older versions are checked when first shown. | DONE in dev 2026-10-28 |
| REQ-D3.46 | Email me this chat | On his own designs, Avi has "Email me this chat": the whole chat as text (every message, the model, tokens and cost, assumptions, how each turn went, what it built, the print findings) with every version's OpenSCAD code, the pictures, the previews and the current STL attached (up to 15 MB), to his own address. So a chat can be read and replayed off the site to compare models and prompts. Never another person's chat. | DONE in dev 2026-10-29 |
| REQ-D3.47 | Build first, ask alongside | The chat builds a first version at once from its best estimates (a card, coin or A4 sheet in a photo gives the scale), lists them as assumptions, and asks for every measurement that matters in one question, the length included. It asks with no part only when nothing gives any idea of size. Every part the chat builds is shown back to it (the self-check), not only the first. | DONE in dev 2026-10-29 |
| REQ-D3.48 | Mark a point | Point mode: tap the part to mark "here". The next message carries the point in the code's own coordinates, the face it is on and its direction, the version, and a picture of the view with the marker. | DONE in dev 2026-10-29 |
| REQ-D3.49 | Measure | Measure mode: tap two points on the part for the distance between them and its x, y, z parts. The bed grid is 10 mm. | DONE in dev 2026-10-29 |
| REQ-D3.50 | Done | "Done" under the chat input opens the finished part: the 3D view, the print check, download STL or OpenSCAD, email me the files, share, and "order a print" (coming soon). | DONE in dev 2026-10-29 |
| REQ-D3.51 | The part stays on top | On a phone the 3D view stays at the top while the chat scrolls; a Pinned button lets it scroll away, remembered on that phone. | DONE in dev 2026-10-29 |
| REQ-D3.52 | Avi hears about requests | Asking to join (and asking again after a decline) emails Avi: who, why, and a link to the People screen. | DONE in dev 2026-10-29 |
| REQ-D3.53 | Invite one person | On the People screen Avi enters an email (and a name). They get a link with a one-time key: the first person who opens it signed in is let in at once (with the welcome email) and the key is burned. That person may open it again; anyone else is refused, as is everyone after 14 days or once Avi withdraws it. The People screen lists every invitation and its state. | DONE in dev 2026-10-29 |
| REQ-D3.54 | Make a copy | On a shared design, "Make a copy" starts a new design of your own with that part as version 1 (made by "copy"): its code, sizes, parts and files; not the chat or the pictures, which stay their owner's. The first chat line says whose it was. | DONE in dev 2026-10-29 |
| REQ-D3.55 | A picture, full size | Tapping a picture in the chat opens it full size, with Save (a download) and, on a phone that can, Share (the phone's share sheet with the picture itself). | DONE in dev 2026-10-29 |


## Chapter 7: Designs with several parts (approved by Avi 2026-10-29)

Avi, 2026-10-29: parts that fit together (a box and its lid, a clip on a
rail, a case and its cover) and parts joined by hardware (screws, nuts,
magnets, a hinge pin) come first. Up to 8 parts. Each part as its own STL
and all of them in one 3MF. Multi-colour and print-in-place come later.

### How it works

- **The model names the parts.** Its JSON lists them (name, label, how many
  to print, printed or not, a print orientation); the code has one module per
  part, drawn where it sits **in the assembly**. Hardware the person buys (a
  screw, a magnet) is a part that is not printed: it is shown in the assembly
  and checked for fit, and never goes on the plate.
- **The server builds each part on its own**, then does the rest itself, in
  Python: it turns each printed part to its print orientation (the model's
  hint, checked by trying the six flat sides when the hint gives a poor
  bed contact), lays the parts out on one plate 10 mm apart, and writes the
  3MF. The model writes one file, as today.
- **The fit check** runs on the parts in their assembled places: two parts
  that overlap, or mating faces closer than the clearance asked for (0.2 to
  0.4 mm), or a screw that does not go through its hole, are findings like
  the print checks, with Fix it.

### What the person sees

- **Assembled**: every part in its own colour. Tap a part's name to hide or
  show it; an "explode" slider pulls the parts apart.
- **Print plate**: what goes on the bed.
- A list of parts, each with its size, its print check, how many to print
  and its own Download STL; and Download all as 3MF.
- The chat works per part ("make the lid tighter"), and a marked point
  knows which part it is on.
- A one-part design looks and works exactly as today.

| REQ | Name | Requirement | Status |
|---|---|---|---|
| REQ-D3.60 | Parts | The model may answer with up to 8 named parts in one file; each has a label, a count, printed or not, and a print orientation. | DONE in dev 2026-10-29 |
| REQ-D3.61 | Built one by one | The server builds each part alone, in its assembled place; each gets its own STL, size and print check. | DONE in dev 2026-10-29 |
| REQ-D3.62 | Plate and 3MF | The server turns each printed part flat (the hint, or the best of six sides), lays them out on one plate, and writes one 3MF with every part as its own object. The plate STL stays the version's main file, so downloads and sharing keep working. | DONE in dev 2026-10-29 |
| REQ-D3.63 | Fit check | In the assembly: no two parts overlap; mating faces have the clearance asked for; hardware passes through its holes. Findings carry Fix it. | DONE in dev 2026-10-29 |
| REQ-D3.64 | Assembled and plate views | The 3D view switches between assembled (a colour per part, hide and show, explode) and plate. | DONE in dev 2026-10-29 |
| REQ-D3.65 | Per-part downloads | Each part's STL, the plate STL, the 3MF, and the OpenSCAD file. | DONE in dev 2026-10-29 |
| REQ-D3.66 | Per-part chat | A marked point names its part; the model is told which part it is. | DONE in dev 2026-10-29 |
