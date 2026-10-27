# bkm: Spec

Status: **built 2026-10-26.** Data model ([data_model.md](data_model.md))
approved by Avi the same day. Backlog: [backlog.md](backlog.md).
Requirements are `REQ-B.n`.

## Chapter 1: What it is

**bkm** is the gateway to Avi Salmon's BKMs, at `babook.co.il/bkm/`. One wall,
in the noticeboard look of the cohort app, with one card for each BKM.

**A BKM** ("best known method") is a public GitHub repository that holds a
whole method: how to build a full-stack site, how to build and program the
Single Button kit, how to learn FPGA on the DE10-Lite, and whatever comes
next. Each BKM has its own GitHub Pages page that explains everything about
it. The detail lives there, not on the wall.

**How a person uses a BKM.** They need Git, an IDE and an AI engine. The
school's choice is VS Code with Claude Code or GitHub Copilot; Cursor or
others can work too. A GitHub account helps but is not required. They clone
the repo, open VS Code in its folder, and say in the chat "Hi, what do I do
now?". From there the BKM itself explains, installs, teaches and guides.

**The top of the wall** says exactly that, in a few lines: what a BKM is, and
the four steps (clone, open in VS Code, start the AI, ask "what do I do
now?"). Then the cards.

**The cards.** Each card shows a picture of what the BKM makes (the
DE10-Lite board, the Single Button kit, a creative illustration for full
stack; mostly hardware, robotic dogs and the like), its name and one line.
Only finished BKMs are on the wall; Avi says when one is ready. A
signed-in person can open it (it leads to the BKM's GitHub Pages page), like
it (the count is public), star it (only they see their stars) and talk about
it in a comment thread.

**Who sees what.**

- Anybody with the link sees the wall and its cards, without signing in.
  Nothing on it opens for them: not the BKM's page, not likes, stars or
  comments.
- When they try any of those, a sign-in window opens and invites them in.
  Google comes first and is the one encouraged; email and password is there
  but tucked away, as in the other apps.
- Signing in uses the one babook account: signed in here is signed in to
  every babook app.

**Who adds BKMs.** Only Avi, and through the chat, not a form: he says "I
have a new BKM" with its repo, and Claude puts it on the wall. Nobody else
adds BKMs.

**Desktop first.** People use a BKM in front of a computer, so the wall is
built for a computer. On a phone, a big notice says the site is meant for a
desktop and strongly suggests switching; it can be dismissed, and the wall
then works on the phone, but nothing is done to make the phone experience
good.

**English only.** The app and the BKMs are in English, for an international
audience.

**What it is not.** Not a place to read the BKMs (their pages do that), not
a place for other people's BKMs, and not linked from babook's portal or
pages, nor linking back to them (Rule 3).

## Chapter 2: The wall

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.1 | The message on top | A pinned sheet: "Best Known Methods", one paragraph on what a BKM is, and the four steps (get Git, VS Code and an AI; clone; open in VS Code and start the chat; ask "Hi, what do I do now?"). A sticky note beside it on a computer. | DONE |
| REQ-B.2 | Public, but nothing opens | Anybody with the link sees the wall and the cards (picture, name, line, counts). Signed out, the BKM's addresses are not in the page at all, and every link and button opens the sign-in window. The API gives a visitor the cards without their links. | DONE |
| REQ-B.3 | The sign-in window | A window over the wall: why to sign in, one big "Continue with Google", and "Use an email and password instead" folded under it, with "create one". It brings the person back to the card they clicked. The account is babook's one shared User. | DONE |
| REQ-B.4 | Made for a computer | On a phone (narrow screen, or a touch-only device) a big notice says the site is made for a computer and asks to come back from one. It can be dismissed; the device remembers. Nothing else is done for phones beyond not sliding sideways. | DONE |
| REQ-B.5 | English | Every screen in English, dates included, although babook's default language is Hebrew. | DONE |

## Chapter 3: The cards and a BKM's page

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.10 | A card is a Polaroid | A picture of what the BKM makes, its name and one line, pinned to the cork. | DONE |
| REQ-B.11 | Opening a BKM | Signed in, the picture and the name open the BKM's GitHub Pages page in a new tab. "How to start" opens the BKM's page here: the card large, the four steps with this BKM's own `git clone` and `code` commands and copy buttons, the repository link, and the conversation. | DONE |
| REQ-B.12 | Order | Avi decides the order of the cards (`position`). | DONE |
| REQ-B.13 | Likes, public | A heart with the count everybody sees. One per person, toggled. | DONE |
| REQ-B.14 | Stars, private | A star only its owner sees; "My stars" shows only the starred cards. | DONE |
| REQ-B.15 | One conversation per BKM | Questions and comments as sticky notes; a reply quotes the comment it answers. Text only, never HTML. | DONE |
| REQ-B.16 | Your own, and Avi's | The author edits or deletes their comments; Avi deletes any. A deleted comment shows as deleted so replies still read. | DONE |

## Chapter 4: Avi's BKMs

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.20 | Only Avi, through the chat | No screen adds BKMs. Avi tells Claude; `manage.py bkm add <repo>` fills name, line and Pages address from GitHub once; `bkm set`, `picture`, `hide`, `show`, `remove` change it. Through the API, only an admin writes. A hidden BKM is seen by Avi only, with a "hidden" tag. | DONE |
| REQ-B.21 | Finished BKMs only | A BKM goes on the wall when Avi says it is complete. In production it arrives as a data migration plus its picture in `bkm/seed_assets/<slug>.jpg`, attached once by `seed_bkm` (never over a picture Avi changed). On 2026-10-26: FullStackBKM, SingleButtonKitBKM, De10LiteBKM. | DONE |
| REQ-B.22 | The picture is the result | A photo of the thing the BKM makes, or a creative illustration when it is not a thing. Kit: the photo from its own repo. DE10-Lite: Terasic's product photo. Full stack: a papercraft illustration made for the card. | DONE |

## Chapter 4b: The exhibition of projects (Avi, 2026-10-27)

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.30 | A public exhibition | A second tab, "Projects": things people made, as taped photos on the cork (so they never look like a BKM). Anybody with the link sees the cards and their pictures. | DONE |
| REQ-B.31 | Pin your project | Anybody signed in pins their own: a YouTube video, a website, or a photo. Title, a sentence or two, and the facts below. A photo is checked, made at most 1600px, stripped of where it was taken, and passed through the site's shared image safety check; it lives in the public media folder. The owner edits or removes it; Avi any. | DONE |
| REQ-B.32 | Signed in to open | A visitor sees the card and the picture (the video's thumbnail, the photo, a screenshot of the site from WordPress's free mShots); pressing anything opens the sign-in window and brings them back to that card. Signed in: a video plays inside its card and has a full screen button, a site opens in a new tab, a photo opens large. The links are not in a visitor's page or API. | DONE |
| REQ-B.33 | Likes | Public count, one per person, toggled. | DONE |
| REQ-B.34 | A conversation per project | The same thread as a BKM's: quoted replies, edit and delete your own, Avi deletes any. | DONE |
| REQ-B.35 | Find a project | No AI, no search engine: words searched in the title, description, tags, maker and BKM name, every word must match; filters by BKM ("made with"), topic, kind and reason; order by newest, most liked, most talked about. Every chip on a card (BKM, topic, tag) is a filter link. A BKM's page shows how many projects were made with it and invites pinning one. | DONE |
| REQ-B.36 | The API | `projects` (public read without links, signed-in create, owner or Avi change, `like` toggle, the same filters as the page), `project-likes`, `project-comments`. | DONE |

## Chapter 5: How it must behave

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-B.40 | Full REST API | Rule 6: DRF over every model under `/bkm/api/`: `bkms` (public read without links, admin write, `like` and `star` toggles), `readers` (your own), `likes`, `stars` (your own only), `comments`. | DONE |
| REQ-B.41 | Its own frame | Own base template and menu (the wall, my stars), own error pages, no link to babook and not in babook's portal (Rule 3). | DONE |
| REQ-B.42 | No sideways scroll | No page slides sideways at 320, 360, 375, 390, 412 and 1280. | DONE |
| REQ-B.43 | The menu is always there | Avi, 2026-10-27: the top menu stays on screen while scrolling. Fixed to the top, the page pushed down by its measured height; tested in Chromium and WebKit (the iPad's engine) at 1280 and 1024. | DONE |

## Chapter 6: Decisions taken on the way

- **Sign-in is not approval.** Unlike cohort, anybody with a babook account
  may like, star and comment; the wall is a public gateway.
- **The card leads to the Pages page, not the repo.** The repo link is on the
  BKM's page here, next to the clone command.
- **Rows by migration, pictures by seed.** A migration runs once, so a card
  Avi removes never comes back; a picture file cannot live in a migration,
  so `seed_bkm` attaches committed files to BKMs that have none.
- **DE10-Lite picture.** No freely licensed photo exists on Wikimedia; the
  card uses Terasic's own product photo. Avi can replace it with his own
  board (`bkm picture de10-lite <file>`).
