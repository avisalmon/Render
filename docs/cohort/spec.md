# cohort: Spec

Status: **built 2026-10-21** (SPR-C.1 to C.6), awaiting Avi's review in dev; the
high-level spec was written from Avi's interview the same day. Avi waived the approval gates for this spec and for the data model ("no
need for my approval, I think you understood"); the design direction is the one
gate left before the build. Data model: [data_model.md](data_model.md).
Process: [building_an_app.md](../building_an_app.md).

Requirements are `REQ-C.n`. Statuses: TODO, WIP, DONE.

---

## Chapter 1: What it is

The home of a teachers' professional-development course Avi runs, on **leading
innovation with advanced AI**. Everything the participants hand in during the
course lives here: the sites they built, the documents of each subject track,
and the materials Avi gives them along the way.

It is **not public**. It is open by invitation to the course's participants
only. Avi sends a link; a participant signs in with their babook account, asks
to join, and waits until Avi approves them.

What it is not: not a course platform (the courses themselves stay in babook),
not a social network (no profiles to browse, no messages between people), not an
official site of anybody.

## Chapter 2: The way in

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-C.1 | The disclaimer, always | Under the top menu, on every page including the ones before signing in, a fixed banner that does not scroll away and does not change: the site is a temporary site of Avi Salmon, meant only for communication during the course; it is not an official site of the Ministry of Education, Intel or anybody else; it is not shared with anyone except the course participants approved to enter. | DONE |
| REQ-C.2 | A visitor sees the door, not the house | Signed out: what this is (one paragraph), the disclaimer, and "sign in". Signed in without access: a single button, "ask to join". Nothing of the course is visible before approval. | DONE |
| REQ-C.3 | Asking to join | One press creates a request. The page then says the request was received and is waiting for Avi's approval, and keeps saying so on every visit until it is decided. Asking twice does nothing new. | DONE |
| REQ-C.4 | Avi's requests screen | Avi (the app's admin) sees, at all times, who asked: name, email, when. Approve or decline, one tap each. Approved and declined lists stay visible, and an approval can be withdrawn later. | DONE |
| REQ-C.5 | Approval is an email and an open door | On approval the participant gets an email saying they are in, with the link. From then on the site is open to them. A declined person sees a short, polite "your request was not approved". | DONE |
| REQ-C.6 | Babook's login, the app's look | Sign-in uses the shared babook account. The pages around it are in the app's own look (Rule 3). | DONE |

## Chapter 3: The exhibition (התערוכה)

The participants were asked to build a site. The exhibition shows them.

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-C.10 | Hang a site | Any participant adds a site by pasting its link, with a title (and a short line if they like). As many sites as they want. Only `http` and `https` links. | DONE |
| REQ-C.11 | A card with a picture | Each site is a card: a small screenshot of the site, its title, and the teacher's name. The system takes the screenshot itself. If it cannot (the site blocks it, or is down), the card says so and the owner can upload a picture instead. | DONE |
| REQ-C.12 | Retake on request | The screenshot is taken again only when the owner presses "retake" (Avi: "it doesn't really matter"). | DONE |
| REQ-C.13 | Likes, for everyone to see | Any participant likes a card; the count is public. | DONE |
| REQ-C.14 | Stars, for yourself | A star marks a favourite. Only you see your stars, and you can show only your starred cards. | DONE |
| REQ-C.15 | One conversation per card | Each card has one comment thread. Any participant writes in it. A comment can reply to an earlier one, shown as a quote the way WhatsApp does. | DONE |
| REQ-C.16 | Your own, and Avi's | The owner edits or deletes their cards and their comments. Avi can delete any card or comment. A deleted comment that others replied to shows as "deleted" so the replies still read. | DONE |

## Chapter 4: Tracks (מגמות)

Each high-school subject track has a page holding three documents its
coordinator prepares elsewhere. The pages are **containers of links**.

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-C.20 | The tracks | Opened at the start: Computer Science, Electronics, Physics, Mechatronics, Design, Data Science, and an example track, "Imaginary track: Electronics", owned by Avi to show what a good page looks like. More are added by Avi through the chat (a command), not through a screen. | DONE |
| REQ-C.21 | One owner per track | Each track has one owner, a participant Avi names (through the chat). Only the owner edits the track's links. | DONE |
| REQ-C.22 | Three links | The vision document, the graduate profile, and the project definition: what counts as a project high-school students submit in this track, its requirements and guidelines. Each is a link to anywhere (a cloud document, a GitHub Pages page, anything). | DONE |
| REQ-C.23 | Seen by all participants | Every approved participant sees every track. A link not given yet shows "in preparation". No likes or comments here. | DONE |

## Chapter 5: Course materials (חומרי ההשתלמות)

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-C.30 | Avi's shelf | Only Avi adds, edits and removes materials. Participants see them. | DONE |
| REQ-C.31 | Three kinds | A YouTube video (plays inside the page, with a link to open it on YouTube), a document Avi uploads (kept in the site), and a babook course (a link into babook). | DONE |
| REQ-C.32 | Title and a line | Every item has a title and one short line of explanation from Avi. | DONE |
| REQ-C.33 | In the order added | No sessions, no topics: the order Avi added them. No notifications; Avi tells the group himself. | DONE |
| REQ-C.34 | The one link out | Linking into babook's courses is a deliberate exception to Rule 3, asked for by Avi: the participants are babook users and do the courses there. | DONE |

## Chapter 6: How it must behave

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-C.40 | Phone and desktop | Built and checked at 390px and at desktop width. On a phone the content comes first (methodology 25). | DONE |
| REQ-C.41 | Hebrew, right to left | Hebrew interface. Anything with a direction or a sign checked by eye (methodology 30). | DONE |
| REQ-C.42 | Closed by default | Every page and every API answer checks: signed in and approved, or Avi. Anything else sees the door (Chapter 2). | DONE |
| REQ-C.43 | Links are safe to follow | Participant links open in a new tab, `rel="noopener noreferrer"`, and are never embedded in the page. | DONE |
| REQ-C.44 | Full REST API | Rule 6: DRF CRUD over every model, scoped like the pages. | DONE |
| REQ-C.45 | Its own frame | Own base template, own menu (Rule 3). The menu: the exhibition, tracks, materials, and for Avi the requests screen. | DONE |

## Chapter 7: Decisions taken on the way

- **Admin.** Avi's account (a superuser) is the admin, plus anybody Avi marks as
  admin through the chat. Stated so the superuser bypass is deliberate.
- **Edit and delete.** Owners edit and delete their own cards and comments; Avi
  deletes anything (the default Avi did not object to).
- **Track pages have no likes or comments** (default, not contradicted).
- **Screenshots.** Measured on 2026-10-21: WordPress mShots (with Microlink as a
  fallback) returns a real picture of a public site with no key and no browser
  on Render, so that is the method. Tries happen when a site is hung or retaken,
  and quietly on later visits to the exhibition while a picture is on its way,
  six tries at most; the owner can upload a picture instead.
- **Private files.** Screenshots and documents are kept outside the public
  media folder and served only to people inside (`/cohort/files/`).
- **Design.** The teachers' room noticeboard (chosen 2026-10-21 from five
  directions): cork, pins, Polaroids for sites, paper sheets for documents,
  sticky notes for comments.
- **Adding a track through the chat** means a line in `cohort/seed.py` and a
  deploy (`seed_cohort` runs on every deploy and never edits an existing track);
  owners and admins are set with `manage.py cohort_admin`.
- **Name.** The app is `cohort` at `/cohort/`; easy to rename before launch.
