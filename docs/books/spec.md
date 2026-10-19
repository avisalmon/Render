# Books: Spec

Status: **Full spec approved by Avi, 2026-10-18** (design gate closed the
same day, BK1 §1.1c; backlog in [backlog.md](backlog.md)). Part A
(sections 1 to 13) is the introduction Avi reviewed. Part B is the full spec,
one chapter per epic (BK1 to BK13). The data model,
[data_model.md](data_model.md), was approved by Avi on 2026-10-18. Process:
[building_an_app.md](../building_an_app.md). The backlog comes after Avi
approves this.

# Part A: introduction

## 1. What Books is

Books is an app for sharing real, physical books between people. It is the
central app of the Render project, and the reason the project exists.

A person photographs a bookshelf. The system recognises the books on it, the
person confirms them one by one, and a personal catalog is built from photos
instead of typing. That catalog then feeds a shared library: other people can
see what you have, and you can see what they have, and books move between
real people by hand.

It is about physical goods. The books are real and so are the handovers.

## 2. Who it is for

The first users live in the Haifa and Tel Aviv areas and can meet in person.
That is the first experiment: local exchange, handed over by hand, no postage.
Later the same system can reach further (other regions, posting a book), but
that is not the starting point.

## 3. The three layers

1. **The catalog.** Your own books, built from shelf photos.
2. **The hub.** A browsable shared library: lend, exchange, sell, near you.
3. **The community.** Talking about books, taste-based recommendations,
   reading streaks and points, rare books.

The catalog is useful on its own, even with no neighbours yet. The hub needs
people nearby. The community grows on top of both. They are built in that
order.

## 4. The catalog, in one paragraph

The person photographs a shelf. The recognition (the `bookshelf-recognition`
skill) reads the spines, aiming for about 90 percent accuracy, Hebrew included.
The system then walks through the books one at a time and the person confirms
or corrects each one. The person can say where each book is, in free text
(a room, a shelf, a box, a table), so they can find it later.

## 5. What a person decides about each book

For every book the person chooses how it appears to others:

- **Private.** Nobody but the owner knows it exists.
- **Public, not shareable.** Others can see the owner has it. It stays theirs.
- **Lend.**
- **Exchange.** Given for a different book received.
- **Sell.**

The choice is made at the moment the person confirms each scanned book, and
can be changed later. One book may be offered more than one way at once (to
lend and to exchange, for example); "public, not shareable" is simply a public
book with no offer on it. (Settled in the data model, 2026-10-18.)

## 6. The hub, in one paragraph

Once people have catalogs, the app is one large sharing library you can browse.
You can offer an exchange, ask to borrow, or buy. A distance mode limits the
view to people within a radius (about 50 km was named), so two people can
meet and hand a book over. Other handover options, such as posting a book, are
to be defined later.

A book that is sold, given or exchanged between two people in the app moves
into the new owner's catalog as the same book, with its history. Over time a
copy carries the record of whose hands it passed through, which is what a
museum of rare items needs.

## 7. The community and play, in one paragraph

Forums and reading communities, book reports and blog posts where people give
opinions and analyse books, and recommendations based on each person's taste
(which needs books to carry genre and subject tags, and people to have a taste
profile). A place for
rare books, a museum of rare things. Gamification to encourage reading:
reading streaks that the person logs on trust, and points for sharing. Points
and streaks are visible to others, in the way Duolingo shows them.

## 8. Built to hold any collection

The foundation is built so that books are the first kind of collectible, not
the only one. Coins, banknotes and rare documents could use the same
infrastructure later. Only books are built and designed for now.

## 9. Quality bar

Hebrew and English. Phone, tablet and PC. Web only, nothing to install. It
must be built in the most professional way, with an excellent experience and
beautiful design.

## 10. Futuristic, captured and not planned

Recorded so they are not lost, and not part of any early build:

- Users writing their own books.
- Scanning physical books into digital form.
- People narrating books into audiobooks.

These touch copyright, so they will need their own thinking before anyone
builds them.

## 11. What exists already

Researched on 2026-10-18 (six parallel searches, mostly vendor pages, press and
forums, with almost no independent measurements). The full report is kept
outside the repo; this is the part that matters for the spec.

- **Mail-swap sites** (PaperBackSwap, BookMooch, Title Trader) are the older
  survivors. Posting a book costs about the same as buying it used, which is
  the case for in-person handover.
- **Neighbour lending apps** (Libro, BookNomads, BookMingle, ShelfLog) exist
  but are tiny, with no verified traction. Lendle died in 2011 when Amazon
  withdrew its API access.
- **Shelf-photo cataloguing apps** exist (Shelf Scan, ShelvesAI, TitleEntry,
  Check Yo Shelf) but only catalogue. No competitor found combines the photo
  with exchange.
- **AnyBook (אניבוק), Israel.** The closest precedent. A consumer app in
  2021 (barcode scan, nearby lending, return reminders), then by 2023 a B2B
  "book kiosk" for workplaces and Tel Aviv Municipality. Why it left
  consumers, and whether the consumer app is live, is unverified. Worth
  asking its founders.
- **Reading communities** (Goodreads, StoryGraph, Oku, BookWyrm) are social
  and tracking only, no exchange.
- **Collection platforms** (Discogs, LibraryThing, Numista) are the model for
  the generic foundation, see 12.6.

No source says a shelf-photo flow combined with local exchange exists, but that
is the absence of search results and not proof.

## 12. Raised by the research, for Avi's review

These are things Avi had not raised. Avi read 12.1 to 12.13 on 2026-10-18 and
liked them all; they are accepted as direction, with details left to the full
spec. 12.11 (money) was then settled by Avi.

**12.1 Start with one cluster, not two cities.** Every successful
neighbourhood sharing platform seeded one tiny group at a time (Nextdoor
needed 10 neighbours to open a neighbourhood; Olio began in a WhatsApp group;
Geev in one Facebook group). A 50 km radius over Haifa and Tel Aviv is thin.
The shelf photo helps, because it lets the first people fill the library fast.
Candidate first clusters: a book club, a school, a workplace, a neighbourhood.

**12.2 Wishlists and "now available near you" alerts first.** The most
praised feature of the old swap sites. Mutual swaps (A wants B's book and B
wants A's) and three-way swaps only work with density, so they come later.

**12.3 Loans need rules.** An owner-set loan period (7, 14 or 30 days), approve
or decline, overdue reminders, and a written rule for what "lost" means, who
confirms it, and how to appeal. For cheap books a "replace it or pay the
approximate value" rule fits better than a deposit.

**12.4 Reputation: counts, not stars.** Peer star ratings inflate. Show
counts instead (books lent, share returned on time). Points for sharing are
credited only when the receiver confirms receipt, never on request.

**12.5 Gamification, refined.** Reward things that leave something behind (a
note, a review) and returned loans, cap daily points, and avoid ranking raw
logged reading, which is trust-based and so easy to inflate. Duolingo's
published results support a forgiving streak (streak freezes). Small friend or
cohort leaderboards, with opt-out, are fairer than one global one.
Visibility is a privacy matter, see 12.9.

**12.6 Edition versus copy.** The collection platforms all separate a shared
catalogue entry (the book, with its editions grouped) from each person's own
copy (condition, photos, notes), with the loan or swap on top. The generic
"any collection" foundation is exactly this, with the condition scale
different per item type. (A data model question, parked as Avi asked.)

**12.7 Hebrew data trap.** Many Israeli publishers use a danacode instead of
an ISBN, so recognition cannot rely on ISBN alone and must fall back to title,
author and publisher. The accuracy target must be measured on real Hebrew and
mixed shelves before it is promised: no source reports Hebrew spine accuracy.
The best case study found about 60 percent from text recognition alone, and
over 95 percent only with a vision model plus a catalogue lookup plus review.
The one-by-one confirmation is what makes 90 percent real. It works best as one
list, lowest confidence first, with a one-tap accept, never silent correction.

**12.8 Rare books, kept modest.** A spine photo cannot show a printing line or
a signature. The app can flag candidates (published before about 1966, "first
edition" wording, signed) and ask for a photo of the copyright page. It should
not value anything. Rare items need a display-only, not-lendable setting.

**12.9 Privacy.** Israel's Privacy Protection Law, Amendment 13, took effect
14 August 2025. A reading history can reveal religion, politics or
orientation, so private is the default, location is stored as a neighbourhood
or a rounded point and never an address, and anything public is opt-in. This
interacts with the Duolingo-style public profiles Avi wants: public is a
choice per person. The exact registration thresholds conflict between sources
and need an Israeli lawyer. Simplest age rule: 18 and over.

**12.10 Legal.** Lending and reselling a lawfully owned physical book is low
risk. Scanning books and user-narrated audiobooks are the real risk: hosting
copies of in-copyright books is high risk, public-domain or licensed content is
safe, and narration for print-disabled readers may be routed through the
Central Library for the Blind. Keep the platform out of the money flow (buyers
pay sellers directly in person), which avoids the payment-licensing question.
Provide a report button and a takedown contact. Tax on occasional sellers,
platform safe harbour and the status of the Books Law (חוק הספרים) could not
be confirmed. This is research, not legal advice.

**12.11 Money: three tiers (decided by Avi, 2026-10-18).** Prices are
Avi's first numbers, to be tested.

| Tier | Price | What it gives |
| --- | --- | --- |
| Free | 0 | Catalogue up to 1,000 books from shelf photos. See what other books exist. No contact with other people and no exchange. |
| Subscription | about 4.99 USD a month | Better recognition (Google search and match), full sharing (lend, exchange, sell, contact), forums, reading communities, blogs. |
| Advanced | about 20 USD a month | Writing your own books, scanning, narration and the other advanced capabilities. |

Things to check before this is built, not objections:

- **Free users cannot exchange.** An exchange needs two people, so the network
  only works where both sides subscribe. The free tier must give enough value
  alone (the catalogue) and enough of a taste of the hub (seeing that a book
  exists nearby) to make people subscribe. Settled 2026-10-18: a free user can
  answer a request a subscriber sends, but cannot start one.
- **Google Books terms.** Google's terms bar charging users for an
  application that uses its data without separate permission. The
  subscription's "Google search and match" needs those terms read, or another
  source (Open Library, the National Library of Israel) used for the paid
  tier. See 12.14 on not depending on one source.
- **The Advanced tier carries the copyright risk of 12.10.** It should not
  launch before the legal footing (public-domain or licensed content, or a
  partner such as the Central Library for the Blind) is settled.
- **Payments.** Subscription billing is the platform's own income, which is
  separate from buyers paying sellers. The sale of books between users still
  stays outside the money flow. The payment provider is not chosen.
- **Not in the first build.** The first experiment (Haifa and Tel Aviv, a
  small cluster) can run with no billing at all. Tiers are recorded so the
  data model leaves room for them.

**12.12 Partners and handover points.** Libraries, schools, cafes, book clubs,
bookshops (Yudan Books in Haifa is both a rival and a candidate), and Book Week
(9 to 18 June in 2026). Named partner places as meeting points would help
flaking, which is the main practical failure. None of this is tested.

**12.13 Accessibility.** Almost nothing was found. It should be a stated
requirement from the start: screen readers, right-to-left layout, readable
type, and the link to audiobooks. English, Russian and Arabic books should be
first-class, not an afterthought.

**12.14 Avoid platform dependency.** Lendle died when Amazon cut its API. Book
data should come from several sources (Open Library, the National Library of
Israel, Google Books) and be copied into our own database, never read live from
one.

**12.15 What to find out before design.** Why AnyBook left consumers. The real
accuracy on Hebrew spines, using the repo's `bookshelf-recognition` skill on
real shelves. What a lawyer says about reading-log privacy and payments.

## 13. Standing rules

Books follows the six core rules in
[building_an_app.md](../building_an_app.md): database models only, full
encapsulation (the shared login is the only thing shared), its own base template
and menu, its own `docs/books/` with a separate data model, migrations and
deploys scoped to the app, and a full DRF CRUD API for every model.

## 14. How the rest of this spec is organised

Sections 1 to 13 are the introduction (Part A). Part B below is the full spec:
one chapter per **epic**, each a self-contained scope of work that ends in
something a person can use or that the next epic stands on. The backlog will
break each epic into sprints. Epic IDs are `BK1` to `BK13`; sprints will be
`SPR-BK<epic>.<n>`.

**The first experiment** (the Haifa and Tel Aviv pilot, one cluster) needs
BK1 to BK6. BK7 to BK11 follow once people are exchanging. BK12 and BK13 are
recorded, not planned.

| Epic | Chapter | Layer | Needed for the pilot |
| --- | --- | --- | --- |
| BK1 | Design, graphics and infrastructure | Foundation | yes |
| BK2 | The book catalogue | Foundation | yes |
| BK3 | Shelf scan and confirmation | Catalog | yes |
| BK4 | My library | Catalog | yes |
| BK5 | The hub: finding and asking | Hub | yes |
| BK6 | Circles and the first launch | Hub | yes |
| BK7 | Community: threads, blogs, reviews | Community | no |
| BK8 | Play: streaks, points, badges | Community | no |
| BK9 | Discovery and recommendations | Community | no |
| BK10 | Rare books and the museum | Community | no |
| BK11 | Tiers and billing | Money | no (tiers set by hand) |
| BK12 | Advanced creation: writing, scanning, narration | Futuristic | no |
| BK13 | Collections beyond books | Futuristic | no |

Each chapter states its goal, what is in and out of scope, the rules that
govern it, what it depends on, and when it counts as done. Screens, field
lists and code are decided in the sprints, not here. The data behind each
chapter is in [data_model.md](data_model.md).

---

# Part B: the epics

## BK1. Design, graphics and infrastructure

**Goal.** Books has its own look, its own front door and a working skeleton
before any feature exists. Everything later is built on top of this, so it is
done properly once.

**1.1 Design language.** Books should feel like a good library and a warm
bookshop, not like a marketplace or a dashboard. Paper-toned backgrounds, ink
colours, generous white space, real book covers as the main imagery, and
calm motion. Proposed starting point, to be shown to Avi before any screen
is built:
- **Type.** One serif for headings and one sans for text, both with full
  Hebrew and Latin (for example Frank Ruhl Libre with Assistant or Heebo).
  Numbers in tabular figures where they line up.
- **Colour.** A small set of named tokens (`--bk-*`), defined once, with a
  light and a dark theme. Contrast meets WCAG AA in both.
- **Components.** One shared set: buttons, fields, cards, the book cover tile,
  the book spine strip, chips for the five choices, sheets and dialogs, empty
  states, toasts. Every class is namespaced (`bk-`) and every class used is
  defined (methodology entries 7 and 13).
- **Icons and illustration.** One icon family; a few simple illustrations for
  empty states (an empty shelf, a first scan).
- **Motion.** Short and purposeful: a book sliding into the catalogue on
  accept, nothing that delays a tap.

**The design gate.** Before BK1 code, a design board (colours, type, the cover
tile, one catalogue screen and one confirmation card, phone and desktop, Hebrew
and English, light and dark) is published for Avi. Building starts when he
approves it.

**1.1a Direction chosen (Avi, 2026-10-18): the lamp-lit shelf.** Of three
first styles (warm library, bright and playful, collector's den) Avi chose the
collector's den, then of three refinements chose **C3, the lamp-lit shelf**:
- A dark wood-and-brass room: near-black ground (`#120F0C`), brass accent
  (`#D8B46A`), ivory text (`#EFE6D2`), muted warm grey for secondary text.
- **David Libre** (serif) for titles and spines, **Heebo** for text, both
  Hebrew and Latin.
- The home screen is **your shelf**: one long shelf of real spines, titles on
  the spines, books leaning and slightly uneven, lit from above by a small
  brass lamp. You **swipe along the shelf** to walk through it, as you would
  scan a real one.
- Tapping a spine lifts and lights it, and a museum-style label (title,
  author, its status) appears below. Rare candidates carry a gold line.
- In the product the spines come from the person's own scanned shelf (colour,
  title, proportions), so the screen looks like their real shelf.
- This replaces the "paper-toned" proposal above.
- The design canvas: https://claude.ai/artifact/8qwMqztDQvDVYihGsGywVW

**1.1b Appearance is a setting (Avi, 2026-10-18).** Every design explored on
the canvas stays available; the ones Avi liked are the defaults. In the
person's settings, under Appearance:
- **Theme** (colours and type): **Lamp-lit light** (the default), Lamp-lit
  dark, Warm library, Bright and playful, Collector's den. A theme is a set of
  colour and type tokens over the same screens, so adding one is cheap.
- **Shelf view** (how the home shelf behaves): **Lamp-lit shelf, swipe along**
  (the default), Bookcase with two shelves and tap to pull out, Living shelf
  with drag to rearrange. These are real layout variants, so they cost more
  than a theme and are built after the default works.
- **Desktop** uses the drawn desktop layout by default: side menu with rooms,
  two full-width shelves per room under the lamp, the selected book's label
  and "near you" in a side panel.
- **Every screen is light (bright) by default,** phone, tablet and desktop
  alike (Avi, 2026-10-18). **Dark mode** is a switch in settings that turns
  every screen to the lamp-lit dark palette; **follow the device** (light or
  dark by the phone's setting) is a third option. The drawn dark boards are the
  reference for dark mode, the light boards for the default.
- The default theme and shelf view are what BK1 builds first and what the
  design gate approves. The other themes and views are their own sprints
  later in BK1, so the first screens are not delayed by them.

**1.1c The design gate: closed (Avi, "approved", 2026-10-18).** The approved
board is the canvas row "Defaults: everything bright" plus the bright Hebrew
home (`C3-Home-Light`): home on phone in Hebrew and English, the confirm-a-shelf
screen, and the desktop home, all in the lamp-lit light palette. The dark C3
boards are the approved reference for dark mode. The tokens that come out of
it are the starting `--bk-*` set:

| Token | Light (default) | Dark mode |
| --- | --- | --- |
| ground | `#EFE6D6` | `#120F0C` |
| surface | `#F8F2E7` | `#18140F` |
| ink (text) | `#241C13` | `#EFE6D2` |
| muted text | `#6A5D4A` | `#A89C86` |
| brass (accent, primary button) | `#7A5518` | `#D8B46A` |
| on brass | `#FFF8EA` | `#15120F` |
| line | `#D3C4A8` | `#3A3128` |
| shelf wood / edge | `#B08A5A` / `#C9A473` | `#4E3B28` / `#7A6040` |
| lamp light | warm `rgba(255,214,140,.5)` pool | warm `rgba(216,180,106,.2)` pool |

Type: David Libre (titles, spines, labels), Heebo (everything else). Spine
colours come from the book, not the theme. BK1 code may start once the backlog
is approved.

**1.2 Two languages, two directions.** Hebrew (right to left) and English
(left to right) from the first screen. Every string comes from one catalogue
with both languages; the layout mirrors correctly, including icons that point.
The person's language is on their Profile; a visitor's comes from the browser.
Book titles show in their own language and direction whatever the interface is.

**1.3 Every screen size.** Phone first, then tablet and desktop, from one web
app. No sideways scrolling at 390 px, tap targets of at least 44 px, and
layouts that use the width of a desktop rather than stretching a phone column.
Installable to the home screen (a web manifest and icons), nothing to download
from a store.

**1.4 Accessibility.** A stated requirement (spec 12.13): screen-reader labels
on every control, keyboard use on desktop, visible focus, readable type sizes,
alt text on covers, no meaning carried by colour alone.

**1.5 The app skeleton.**
- A Django app `books`, mounted at `/books/`, with its own base template,
  header, menu and footer (Rule 3). No link to babook unless Avi asks.
- Own 403, 404 and 500 pages, composed into the project's handlers by prefix.
- Sign in, sign up and sign out in Books' own look, on the shared `User`, with
  Google sign-in as the first option.
- **Onboarding** creates the `Profile`: name, language, a confirmation of age
  18 or over, acceptance of the terms, and an area (a neighbourhood or city,
  stored rounded, never an address).
- The DRF API scaffold under `/books/api/`, documented and browsable, with
  owner-scoped permissions from the start (Rule 6).

**1.6 Storage and jobs.**
- **Images** (shelf photos, spine crops, covers, copy photos) go to **Books'
  own Google Cloud Storage bucket** (Avi, 2026-10-18), never to the web
  server's 1 GB disk. The site's existing shared storage is Google Drive
  (`app/drive.py`, made for ustrip's photos); it is not built to serve many
  images to many phones, and using it would make Books depend on `app/`
  (Rule 2). The bucket is private: covers may be served publicly, everything
  personal (shelf photos, copy photos) only through short-lived signed links
  to its owner and to the people the owner shares a deal with. Covers are
  always our own copies.
- **Photo location, a bonus if present** (Avi, 2026-10-18). When a shelf
  photo carries GPS data, Books reads it once on upload and uses it only
  rounded to a neighbourhood: to suggest the person's area during onboarding
  or when they have none, and to tell which home a shelf belongs to. The
  precise point is then removed from the stored image and never saved, in
  line with spec 12.9.
- **Recognition runs outside the page request,** so a scan never times out a
  phone. The mechanism is chosen in the sprint (the site already runs
  in-process jobs triggered by tokens).
- **Every model call is costed** and recorded, so cost per scan and per person
  is visible from day one.

**1.7 Privacy plumbing.** Built in, not added later (spec 12.9): private by
default, rounded location, a person can download everything Books holds about
them and can delete their account's Books data. A privacy page and terms page
in both languages, marked as drafts until a lawyer reads them.

**1.8 Quality gates.** The site's existing practice applied to Books: a smoke
test for every front-door page, the seal in both directions (no babook chrome
inside, no Books link outside), a screen contract per screen and state at phone
width, a screenshot looked at for every new screen (methodology entry 6), and
every class defined.

**Out of scope.** Any book feature. Payments.

**Done when.** A person can open `/books/` on a phone and a desktop, in Hebrew
and English, light and dark, sign in, complete onboarding, and land on an
empty library that looks finished. The design board is approved and the
screens match it.

## BK2. The book catalogue

**Goal.** A shared catalogue of books, in our own database, good enough that
recognition has something to match against and people find their books in it,
Hebrew included.

**In scope.**
- `CatalogEntry`, `Creator` (with aliases across Hebrew and English), `Tag`,
  `EntryIdentifier` (ISBN and danacode and provider ids), `BookDetail`,
  editions grouped under a parent.
- **Sources.** Look-ups from Open Library, the National Library of Israel and
  Google Books (subject to its terms, spec 12.11), each result **copied into
  our own records** with its source, never read live (spec 12.14). Provider
  limits respected and calls cached.
- **Matching.** By identifier first, then by title, creator and publisher,
  because many Hebrew books have no ISBN (spec 12.7). Duplicates detected and
  merged by a curator, never silently.
- **Covers** copied into our storage.
- **Search** over titles and creators in both languages, tolerant of spelling
  and of missing vowel marks.
- **A tag list** (genres, subjects, audiences) in both languages, seeded once
  and edited by curators.
- **Curation.** Staff can verify, merge and correct entries. People can
  suggest a correction; a curator accepts it.

**Rules.** The catalogue is shared and public; it says nothing about who owns
what. Seeding from any file is one-time and never overwrites a curated record
(methodology, "Data").

**Built (2026-10-18).** Sources: Open Library and Google Books live without
keys; the National Library of Israel adapter is written and waits for a key
(ACT-BK.7), which matters most for Hebrew books and danacodes. Anyone
onboarded may add a record by hand; it stays unverified until a curator at
`/books/curate/` verifies it. See backlog BK2 and data_model.md section 11.

**Depends on.** BK1.

**Done when.** A Hebrew and an English book can each be found by title, by
author, and by ISBN or danacode, and a book not in any source can be added by
hand and later verified.

## BK3. Shelf scan and confirmation

**Goal.** The heart of the product: photograph a shelf, and minutes later the
books are in the person's library, each one confirmed by them.

**In scope.**
- **Capture.** The phone camera straight from the browser, or an upload on a
  desktop. Guidance on the screen (light, distance, two overlapping photos for
  a tall shelf). A shelf label ("living room, top shelf") asked once per scan.
- **Recognition.** The `bookshelf-recognition` skill's pipeline, run as a job:
  find the spines, read each, look up candidates in BK2, rank them with a
  confidence. Two or three candidates per spine.
- **The confirmation flow** (spec 12.7). One list, lowest confidence first,
  each card showing the spine crop beside the best candidate's cover. One tap
  accepts. Swipe or tap to pick another candidate, search, type it by hand,
  or skip. High-confidence books can be accepted together. Nothing is ever
  added or corrected silently.
- **The choices, in the same flow** (spec 5). For each accepted book: private
  or public, and if public, any of lend, exchange, sell. Defaults are set once
  per scan ("everything private", "everything public, not shared") and
  changed per book.
- **Location** prefilled from the shelf label, editable per book.
- **A spine the system missed** can be added by tapping the photo or by search.
- **The free tier's 1,000-book cap** is checked here, with a clear message.

**The accuracy gate.** Before this epic is promised to anyone, the pipeline is
measured on real shelves: Hebrew, English and mixed, at least ten shelves,
against a hand-labelled truth, using the skill's evaluator. The number is
written into this chapter. 90 percent is the target for books confirmed
without retyping.

**The gate, measured (2026-10-19).** 63 of 70 labelled books found (90%),
3 extra, about $0.024 a shelf, on the skill's four labelled shelves, at up to
4000 px. Hebrew matches against the catalogue wait for the National Library
key (ACT-BK.7); until then a Hebrew book is kept as read. See backlog BK3.

**Rules.** A scan never creates a book by itself; the person's accept does.
Shelf photos are kept for the owner only and deleted on request. Every scan
records its model and its cost.

**Depends on.** BK1, BK2.

**Done when.** A person photographs a real mixed Hebrew and English shelf on a
phone and has its books in their library, with their choices, in a few minutes,
and the measured accuracy is recorded.

## BK4. My library

**Goal.** The catalogue is worth having on its own, before anyone else joins.

**In scope.**
- **Browse** by shelf label, by location, by author, by tag, by choice
  (private, public, offered), with covers. Search inside my books.
- **A book's page:** cover, details, my condition and notes, location, photos
  (cover, copyright page, signature), its offers, its history (who it came
  from, when).
- **Edit** everything I own: change location, condition, visibility, offers;
  move many books at once ("these 30 went to a box"); delete.
- **Add by hand** or by barcode when there is no shelf to photograph.
- **Wishlist:** books I want, from the catalogue or as free text.
- **Mark a rare candidate** and add the photos that support it (BK10 builds on
  this).
- **Export** my library (a spreadsheet) at any time.
- **The scan history:** my past scans, their photos, re-open one to confirm
  books I skipped.

**Rules.** Only the owner ever sees a private book. Counts against the cap are
books still held or out on loan.

**Depends on.** BK3.

**Done when.** A person with a few hundred books can find any one of them,
knows where it is physically, and can change any of it, without help.

## BK5. The hub: finding and asking

**Goal.** People see what others near them offer, ask for it, meet, and hand
the book over, with the app keeping track.

**In scope.**
- **Browse the shared library:** public books near me (by my area and radius)
  and in my circles, filtered by tag, language and choice (lend, exchange,
  sell). A free person sees that a book exists nearby, without the owner.
- **Asking.** A request on an offer, with a message. The owner approves or
  declines. A free person can answer a request but not start one.
- **Messages** inside the request, in the app. Contact details are never shown
  unless a person shares them.
- **Meeting.** A meeting note, or a named meeting place (cafes, libraries,
  bookshops; partners marked).
- **Handover.** Both sides confirm the book changed hands. Loans get a due
  date from the offer's loan period; reminders before and after it; both sides
  confirm the return.
- **Exchange.** The requester names the book they give back; both books move
  on completion.
- **Sale.** The price is information; money changes hands in person, outside
  the app (spec 12.10).
- **Transfer.** On a completed sale, gift or exchange the copy moves to the new
  owner's library with its history.
- **When it goes wrong:** cancel, no-show, late, lost, disputed, each with a
  written rule (spec 12.3) and an appeal to a person, not an algorithm.
- **Reputation as counts:** books lent, returned on time, deals completed. No
  stars (spec 12.4).
- **Wishlist alerts:** "a book you want is now offered near you".
- **Block and report** a person or a listing.
- **Notifications** in the app, and by email for what cannot wait (a request,
  a due date). Quiet by default.

**Rules.** Nothing is credited, transferred or counted until both sides
confirm. A blocked person sees nothing of the blocker. Location shown to
others is a neighbourhood and a rough distance, never a point.

**Depends on.** BK4. Circles (BK6) are built in the same phase.

**Done when.** Two pilot users who do not know each other find a book, agree,
meet and complete a loan and its return through the app, and an exchange.

## BK6. Circles and the first launch

**Goal.** The first experiment works: one real group of people in Haifa or Tel
Aviv with enough books between them that asking is worth it (spec 12.1).

**In scope.**
- **Circles:** a book club, school, workplace or neighbourhood. Create, invite
  by link or code, join, leave, moderators. A circle's books are browsable by
  its members even beyond the radius.
- **Seeding.** Getting the first members' shelves in fast: a scanning evening,
  help on the spot, the first few hundred books in before the hub opens.
- **Partner meeting places** for the circle, if any agree.
- **Admin and pilot tools for Avi:** who joined, how many books, how many
  requests, how many completed, where people drop out. A pilot dashboard in
  Books' own docs, like the other apps'.
- **Feedback** from inside the app straight to Avi.
- **Questions to answer before launch** (spec 12.15): why AnyBook left
  consumers, the measured Hebrew accuracy, a lawyer's read on privacy and
  terms.

**Depends on.** BK1 to BK5.

**Done when.** One circle is live with real books and real exchanges, and the
pilot numbers are visible to Avi weekly.

## BK7. Community: threads, blogs, reviews

**Goal.** People talk about books, not only trade them.

**In scope.** Discussion threads (open or inside a circle, about a book or
general), blogs and book reports (a long piece with comments), short reviews
with a rating and a spoiler flag, a reading log (want, reading, read, did not
finish), and public profiles that are opt-in: a person decides what of their
reading and library others see. Moderation: report, hide, lock, a moderator
role per circle, and a site-wide one for Avi. Email digests are opt-in.

**Rules.** Private is the default for reading history (spec 12.9). No contact
details in posts. Hidden is reversible; deleted is the author's choice.

**Depends on.** BK5, BK6.

**Done when.** A circle runs a book discussion and members publish reports,
moderated, without Avi's help.

## BK8. Play: streaks, points, badges

**Goal.** Encourage reading and sharing, the Duolingo way, without rewarding
cheating (spec 12.5).

**In scope.** A daily reading check-in and a streak computed from it, with
streak freezes; points from a ledger for confirmed handovers, on-time returns,
reviews and reports, and confirming catalogue books (capped daily); badges for
milestones; leaderboards per circle and among friends, with opt-out; a
personal year in books.

**Rules.** Points only when both sides confirm; one deal pays once; no ranking
by self-logged reading counts; daily caps; any award can be reversed.
Visibility of points follows the person's profile choice.

**Depends on.** BK5, BK7.

**Done when.** A circle has a weekly leaderboard people check, and an
attempt to farm points by passing one book back and forth earns nothing.

## BK9. Discovery and recommendations

**Goal.** "What should I read next, and who near me has it."

**In scope.** A short taste survey at onboarding (genres, moods), a taste
profile per person built from it and from their library and log, tag-based
recommendations with a reason shown ("because you liked..."), more by this
author, readers of this also read, and matching recommendations against books
offered nearby. Recommendations stay explainable; no hidden scoring.

**Depends on.** BK2 tags, BK4, BK7.

**Done when.** A person gets suggestions they recognise as theirs, and some of
them are on offer within their circle or radius.

## BK10. Rare books and the museum

**Goal.** Rare and special copies are noticed, documented and shown, carefully
(spec 12.8).

**In scope.** Flagging candidates (old, first edition wording, signed, an
inscription), asking for the copyright page and signature photos, a curator
review, a display-only setting so a rare book is shown but never offered,
provenance from the copy's transfer history, and curated exhibitions (the
museum) with text, items and rights statements.

**Rules.** Books never values anything. A rare copy's owner decides whether it
is shown at all.

**Depends on.** BK4, BK5 (provenance), BK7.

**Done when.** A curated exhibition of real rare copies from members is
published.

## BK11. Tiers and billing

**Goal.** The three tiers (spec 12.11) are enforced, and later paid for.

**In scope.** Tier checks on every feature (one function, used everywhere), the
1,000-book cap, the free-tier reply rule, an upgrade screen, then a payment
provider for subscriptions, receipts in both languages, cancellation, and what
happens to a lapsed subscriber's offers and deals. The Google Books terms
question is settled before the paid tier depends on it.

**Rules.** Subscription money is the platform's only income; money between
users never passes through Books. In the pilot, tiers are set by hand.

**Depends on.** BK5, BK7. Billing after the pilot.

**Done when.** A person can subscribe, use the paid features, cancel, and keep
their library.

## BK12. Advanced creation: writing, scanning, narration

**Recorded, not planned** (spec 10). Writing your own books, scanning books
into digital form, and narrating audiobooks, for the top tier. Nothing here
starts before the legal footing is settled (spec 12.10): public-domain or
licensed material, or a partner such as the Central Library for the Blind.
Its own data model and its own chapter will be written then.

## BK13. Collections beyond books

**Recorded, not planned** (spec 8). Coins, banknotes, rare documents. The
foundation is ready for them (`CollectionType`, a detail model per type, a
condition scale per type). Adding one is a second `CollectionType`, its detail
model, its own recognition, and its own grading. Nothing is designed for them
now.
