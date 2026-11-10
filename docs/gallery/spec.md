# gallery: Spec

Status: **all nine sprints built in dev 2026-11-09**, not pushed. Full spec written 2026-11-09 from Avi's
interview the same day. Chapter 1 is the intro; the data model
([data_model.md](data_model.md)) was approved by Avi the same day. Next: the
backlog ([backlog.md](backlog.md)) and the build. Process:
[building_an_app.md](../building_an_app.md).

Requirements are `REQ-G.n`. Statuses: TODO, WIP, DONE. The app is open to the
whole internet, so it keeps REQ-IDs and a screen contract like the main site,
not the lighter process of a family app.

---

## Chapter 1: What it is

The public gallery of Avi's 10x engineer training. In the training, engineers
learn to build front end pages on GitHub, full stack web apps, BKMs and skills
for AI coding assistants. The gallery is where what they built is shown, liked,
discussed and shared. It lives at `/gallery/` and looks exactly like the
exhibition in the cohort app (cards with a picture, likes, one conversation per
card), copied into its own templates; it shares no code or data with cohort.

**Open to everyone.** Anybody on the internet sees everything without signing
in: every card, every person's page, every comment, and follows any link or
downloads any skill. Adding, liking and commenting need a babook account; a
signed-in person can do all of it at once, with no request and no approval.

**Three kinds of things are shown:**

- **Pages.** A link to anything a person built on the web: a GitHub Pages site,
  a full stack app, any page. Anybody signed in can add as many as they like.
- **Skills.** Skills for Claude Code and GitHub Copilot, in their own tab.
  Uploaded as a SKILL.md or a zip of the whole skill folder, and downloadable by
  anybody, for either platform, as often as they like. Uploading is guarded
  (below).
- **BKMs.** Avi's only. Nobody else adds one. In the gallery a BKM is a way into
  Avi's `/bkm/` app. This link out of the app is a deliberate exception to
  Rule 3, asked for by Avi.

**Uploading a skill is a conversation, not a form.** An AI assistant (Avi's
OpenAI account) talks with the uploader:

1. It tells them if a skill like theirs is already in the gallery ("there is
   already an Excel skill, here it is") and asks whether to go on.
2. It reads every file of the skill for safety: instructions to erase or harm
   the person's computer, sending data out, hidden or obfuscated content,
   anything nasty. If it finds something it refuses, says what and why, and
   proposes a fix. A skill is published only as agreed at the end of the
   conversation.
3. A second risky attempt blocks the person from uploading skills, and Avi gets
   an email describing the incident. Avi can lift the block.
4. A skill that passes is published for both platforms. Claude Code and
   Copilot read the same SKILL.md format, so usually only the folder layout
   differs; where something is specific to one platform, it is adapted and the
   uploader is told what changed.
5. The assistant tags the skill (category, topic) for search as it publishes.

**Limits, so the AI cost stays small:** each person may have at most 2
published skills (a refused or deleted skill does not count); Avi can give
chosen people unlimited uploads. Each skill can be updated at most 4 times, and
every update goes through the whole check again. One skill's conversation may
cost at most 40 cents; every AI call is recorded per person, so Avi can see
later who costs what.

**Every person is tied to the training they came from.** Avi delivers many
trainings and wants each person identified with the right one, for his
statistics. The first time a person adds a page or uploads a skill, a question
pops up: which training did you join? A list, with "other" at the end, and
"other" lets them write where they came from if they want to. Browsing never
asks anything. One training per person, which they can change later. It is
private: only the person and Avi see it; it is not on their public page or
their cards. Avi adds and edits the trainings on his own screen. The list it
starts with:

- Technion semester course
- Intel monthly guest session, October 2026
- Intel monthly guest session, November 2026
- Intel monthly guest session, December 2026
- Technion hands-on session, 3 hours, Thursday 12 November 2026

**Everything else uses no AI.** Each person has a public page with everything
they posted. A page gets a screenshot taken automatically, as in cohort, with an
uploaded picture when that fails. Search is plain database search, free text
over titles, descriptions, people's names and topics, with filters by kind and
topic. Topics come from a list Avi controls (and can add to); the AI picks from
the same list when it tags a skill, so search stays clean. When a skill
conversation reaches its 40 cents, it ends politely, nothing is published, and
it does not count as a risky attempt.

**Avi is the only admin.** He can delete any card, skill or comment (bad
content, a thing posted three times by mistake), and manage who has unlimited
skill uploads and who is blocked. There are no automatic content checks on
pages and comments.

**Hebrew by default, English on a switch** that is remembered: on the person's
gallery profile when signed in, in the browser otherwise.

**What it is not:** not a course platform (the courses stay in babook), not a
social network (no messages between people, no followers), not a place for
anybody but Avi to post BKMs.

## Chapter 2: The way in

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.1 | Everything is open to look at | Signed out, a visitor sees every card, every person's page, every comment and every skill, follows any link and downloads any skill. No page asks them to sign in just to look. | DONE |
| REQ-G.2 | Doing needs a sign-in | Adding, liking, starring and commenting need a babook account. A signed-out visitor who presses one of these goes to sign in and comes back to the same place. A signed-in person can do all of it at once: no request, no approval. | DONE |
| REQ-G.3 | Babook's login, the gallery's look | Sign-in and sign-up use the shared babook account, on pages in the gallery's own look (Rule 3). | DONE |
| REQ-G.4 | Which training? | The first time a person adds a page or uploads a skill, a question pops up before anything else: which training did you join. Avi's list, then "other" with an optional line "where did you come from". Answered once; changed later in their own settings. Browsing, liking and commenting never ask it. | DONE |
| REQ-G.5 | The training is private | Never printed about a person: not on a public page, a card, a search result or a public API answer. Changed 2026-11-10 (Avi): a course gallery (REQ-G.110) shows its members' cards to the other members, so course mates can tell who is in their course; "nothing secret about it". | DONE |
| REQ-G.6 | Hebrew or English | Hebrew by default, right to left. A switch in the menu turns everything to English, left to right. The choice is remembered: on the person's row when signed in (it follows them to any device), in a cookie otherwise. | DONE |

## Chapter 3: Pages

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.10 | Hang a page | A signed-in person adds a page by pasting its link (`http`/`https` only), with a title, a short line if they like, and topics from Avi's list. As many as they want. | DONE |
| REQ-G.11 | A card with a picture | The system takes a screenshot of the page itself, the way cohort does. If it cannot, the card says so and the owner uploads a picture instead. Retake on the owner's request only. | DONE |
| REQ-G.12 | Your own | The owner edits and deletes their own cards. | DONE |
| REQ-G.13 | Links are safe to follow | Links open in a new tab with `rel="noopener noreferrer"` and are never embedded in the page. | DONE |

## Chapter 4: Likes, stars, comments

The same as cohort's exhibition, for every kind of card (page, skill, BKM).

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.20 | Likes, for everyone to see | A signed-in person likes a card; the count is public. | DONE |
| REQ-G.21 | Stars, for yourself | A star marks a favourite. Only you see your stars, and you can show only your starred cards. | DONE |
| REQ-G.22 | One conversation per card | Each card has one thread. A signed-in person writes in it; a reply quotes the comment it answers, WhatsApp style. Everyone can read it. | DONE |
| REQ-G.23 | Your own comments | The author edits or deletes their comment. A deleted comment that others replied to shows as "deleted" so the replies still read. | DONE |

## Chapter 5: People and search

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.30 | A page for every person | `/gallery/u/<name>/`: their display name and everything they posted, newest first. Public. Their name on any card leads there. | DONE |
| REQ-G.31 | Settings | A signed-in person sets their display name, language and training. | DONE |
| REQ-G.32 | Search without AI | One box: free text over titles, short lines, skill descriptions, people's names and topic names, in both languages. Filters by kind (page, skill, BKM) and by topic. Plain database search, no AI and no cost. | DONE |
| REQ-G.33 | Topics are Avi's list | People pick topics from the list; the skill assistant picks from the same list. Nobody but Avi adds a topic. | DONE |

## Chapter 6: Skills

### 6.1 Looking and downloading

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.40 | The skills tab | Skill cards: name, description, owner, topics, likes, downloads, and the platform it came from. Opening one shows its files and its SKILL.md, readable before downloading. | DONE |
| REQ-G.41 | Download for either platform | Two buttons: Claude Code (`.claude/skills/<name>/`) and GitHub Copilot (`.github/skills/<name>/`), each a zip ready to unpack in a repo. Anybody, signed in or not, as often as they like. Downloads are counted. | DONE |
| REQ-G.42 | Read before you use | Every skill page carries one line: it passed an automatic check, read it before you use it. | DONE |

### 6.2 Uploading is a conversation

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.50 | What can be sent | A SKILL.md, or a zip of the whole skill folder, up to about 1MB. A zip is opened safely: no paths out of the folder, no links, no nested archives, nothing run. A SKILL.md without a name and description in its header is refused before any AI is called. | DONE |
| REQ-G.51 | Already have one like it | The assistant compares the new skill with the published ones and, if one is close ("there is already an Excel skill"), shows it and asks whether to go on. The person decides. | DONE |
| REQ-G.52 | Safety, read by the AI | The assistant reads every file for danger: instructions to erase or damage the computer, to send files, keys or data out, to download and run something, to hide what it does; obfuscated or encoded content; instructions aimed at the AI that contradict what the skill says it does. Plain checks without AI run first (hidden characters, encoded blobs, known dangerous commands) and their findings go to the assistant too. | DONE |
| REQ-G.53 | Refuse, explain, propose | When something risky is found, nothing is published. The assistant says what it found and where, in plain words, and proposes a fix. The person can send a fixed file in the same chat; it is checked again from the start. | DONE |
| REQ-G.54 | Published as agreed | The skill is published only when the last file sent is clean and the person confirms. The assistant writes the card's description and picks topics from Avi's list as it publishes. | DONE |
| REQ-G.55 | Both platforms | The upload is recognised as Claude Code or Copilot, and both downloads are built. Both read the same SKILL.md format, so usually only the folder differs; where something belongs to one platform only (a Claude-only header field, a Copilot `.prompt.md` or `.instructions.md`), it is adapted, and the person is told what changed before they confirm. | DONE |
| REQ-G.56 | A fail is a no | If the AI cannot be reached or answers nonsense, the chat says so and nothing is published. A skill is never published unchecked. | DONE |

### 6.3 Limits

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.60 | Two skills each | A person may have 2 published skills. Refused, abandoned and deleted skills do not count. At the limit, the upload button says so and does not open a chat. | DONE |
| REQ-G.61 | Unlimited, by Avi | Avi grants chosen people unlimited skills on his people screen. | DONE |
| REQ-G.62 | Four updates | The owner uploads a new version of their skill at most 4 times. Each update goes through the whole conversation again. The old version stays downloadable until the new one is published. Avi can reset the count for a skill. | DONE |
| REQ-G.63 | 40 cents a chat | Each chat stops at 0.40 USD of AI cost. Before the call that would go past it, the chat ends politely: nothing published, and it is not a strike. | DONE |
| REQ-G.64 | Every cent recorded | Every AI call is recorded with the person, the chat, the purpose, the model, tokens and cost. | DONE |

### 6.4 Strikes

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.70 | First strike, a warning | The first risky file a person sends is a strike: the chat explains and proposes a fix (REQ-G.53). | DONE |
| REQ-G.71 | Second strike, blocked | A second risky file (in the same chat or a later one), or insisting on publishing the risky one, blocks the person from uploading skills. They can still look, like, comment and add pages. The chat tells them plainly. | DONE |
| REQ-G.72 | Avi hears about it | On a block, Avi gets one email to his Gmail: who, when, the findings of both strikes, and a link to the chat. | DONE |
| REQ-G.73 | Avi lifts it | Avi unblocks a person on his people screen. | DONE |

## Chapter 7: BKMs

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.80 | BKM is a link | Changed 2026-11-10 (Avi): BKMs are not cards. Nobody adds one here, Avi included; the menu has "BKM", a link to the bkm app. | DONE |
| REQ-G.81 | The one link out | The menu's link to `/bkm/` is a deliberate exception to Rule 3, asked for by Avi. The gallery never reads the bkm app's data. | DONE |

## Chapter 8: Avi's screens

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.90 | Delete anything | Avi deletes any card, skill or comment from where he sees it, one tap and a confirm. | DONE |
| REQ-G.91 | Trainings | Add, edit, reorder and close trainings. A closed training leaves the question's list and keeps its people. | DONE |
| REQ-G.92 | Topics | Add, edit and reorder topics. | DONE |
| REQ-G.93 | People | Everyone who ever acted: name, training, pages, skills, strikes, AI cost. Grant or take back unlimited skills, unblock, reset a skill's updates. | DONE |
| REQ-G.94 | Numbers | People per training, posts per training, AI cost per person and per training, and the chats that hit the ceiling. Real numbers from the rows, nothing estimated. | DONE |

## Chapter 8b: Round 2, from Avi's first look at the live site (2026-11-10)

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.110 | The course's own gallery | A signed-in person with a training lands on their course's gallery: only the cards of people from the same course, the course's name under the title. "The whole gallery" is one tap away and "my course" brings it back. Visitors and people who chose "other" see the whole gallery. Avi sees the whole gallery and opens any course from his numbers screen (`?course=`); nobody else can open a course that is not theirs. Applies to the skills tab too. | DONE |
| REQ-G.111 | The search behind a magnifier | The search fields do not show until the magnifier is pressed (pages and skills alike). The kind (pages or skills), the topic, and "my favourites / mine" are inside it. A search in progress keeps it open. | DONE |
| REQ-G.112 | Newest on top | With no search, the newest four cards sit on top under "new in the gallery". | DONE |
| REQ-G.113 | Then by likes, or by date | The rest is ordered by likes; a switch orders everything by date instead (then the newest strip is not needed). | DONE |
| REQ-G.114 | The skills banner | The skills tab says what to upload (a SKILL.md, or a zip of the folder) and links to the guide. | DONE |
| REQ-G.115 | The skill guide | `/gallery/skills/guide/`, in both languages: what a skill is, SKILL.md with an example, where it lives for Claude Code and Copilot, skill-creator, what makes a good skill, how uploading works. | DONE |
| REQ-G.116 | One line, not a paragraph | The gallery's intro is one short line; on a phone the cards come first. | DONE |

## Chapter 9: How it must behave

| REQ | Title | Expectation | Status |
|---|---|---|---|
| REQ-G.100 | Phone and desktop | Built and checked at the narrowest phones and at desktop width; on a phone the content comes first. | DONE |
| REQ-G.101 | Both directions | Checked by eye in Hebrew (right to left) and English (left to right). | DONE |
| REQ-G.102 | Its own frame | Own base template and menu (Rule 3): the gallery, pages, skills, BKMs, search, the language switch, sign in or the person's name, and for Avi his screens. The look is cohort's noticeboard, copied into gallery's own files. | DONE |
| REQ-G.103 | Full REST API | Rule 6: DRF CRUD over every model, scoped as in the data model (section 4). The training never appears in a public answer. | DONE |
| REQ-G.104 | AI only in the skill chat | No other screen calls a model. | DONE |
| REQ-G.105 | Uploads are data | Skill files are stored and served as downloads, never run, never shown as HTML. A SKILL.md is shown as escaped text or cleaned markdown. | DONE |

## Chapter 10: Decisions taken on the way

- **Admin.** Avi's account (a superuser) is the admin; stated so the bypass is
  deliberate. Nobody else is admin.
- **BKM, stars, update reset.** Avi approved the data model with its three open
  points unanswered, so the defaults were built: stars stay and Avi can reset a
  skill's updates. The BKM default (Avi's own cards) was wrong: on 2026-11-10 he
  said BKM is only a link to the bkm app (REQ-G.80, PM-92).
- **Strikes.** A first risky file is a warning; a second, or insisting on the
  risky one, blocks. Leaving a chat after the first does not block.
- **The model: gpt-6-luna** (measured 2026-11-09 on Avi's key). Against 4 good
  skills (one that warns about `rm -rf ~`) and 9 planted bad ones (3 that the
  plain patterns do not catch: a Python script uploading the home folder, an
  instruction to mail the repository out, a script deleting Documents), luna
  and terra were both right on all; luna costs a tenth, about $0.0002 a
  reading. `GALLERY_MODEL` changes it without a deploy of code.
- **Both platforms get the same files.** Claude Code and Copilot read the same
  SKILL.md, so the packages differ only in their folder (as FullStackBKM's own
  `sync_skills.py` does). The safety reading also notes anything that works on
  one platform only (a named tool, a slash command, hooks), shown on the card.
  Uploads that are not a SKILL.md (a Copilot `.prompt.md`) are refused for now.
- **One reading does four jobs.** Safety, the card's description, topics from
  Avi's list and the platform note come from one call; the similar-skill check
  is a second small call, skipped for updates and when the gallery is empty.
- **Strikes are the person's, not the chat's.** A risky reading is a strike; a
  second one anywhere, or pressing publish on a risky reading, blocks and mails
  Avi once (to `GALLERY_ADMIN_EMAIL`). Until Avi's screens (SPR-G.8) he lifts a
  block in Django admin by clearing "skills blocked at".
- **Only the uploader speaks in a chat.** Avi can read any chat but not act in
  it, so nothing is ever published in somebody's name by somebody else.
- **Daily caps on the AI, not only per chat** (security sweep, SPR-G.9).
  Signing up is instant, so 40 cents a chat is not a ceiling on the bill: $1 a
  person and $5 for the whole gallery per 24 hours (`GALLERY_PERSON_DAILY_USD`,
  `GALLERY_SITE_DAILY_USD`). Reaching one ends the chat politely, publishes
  nothing and is not a strike.
- **Cost records never block deleting an account** (`AICall.person` set null).
- **Unblocking clears strikes, keeps them on record.** The person starts again
  from a first warning; Avi still sees what happened on their screen.
- **Text on the cork is dark ink.** Cohort's light text on the cork measured
  2.55:1 (needs 4.5:1); the gallery prints it in dark ink (5.9:1). The board,
  pins and paper are unchanged. Cohort itself still has the light text.
- **Known limits, on purpose.** The download counter and comments have no
  per-address throttle (inflating a count harms nobody; comments come from
  signed-in accounts Avi can delete). A message that starts with an English word
  inside a Hebrew sentence reads left to right (the browser's first-letter rule).
