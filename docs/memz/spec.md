# memz — Spec

> **Status: full spec, ready for development, 2026-09-14.** Built on the
> approved [data_model.md](data_model.md); chapter 1 is the intro that was
> approved earlier, kept as is. Sprints and their status live in
> [backlog.md](backlog.md) (next step); this document and the data model are
> the two sources of truth for *what* memz is. When they disagree with the
> code, the code is wrong until someone changes the document on purpose.
>
> **Process weight** ([building_an_app.md](../building_an_app.md), "Process
> weight scales to the app's size"): memz is public-facing, guests are
> strangers, and there is a paid tier planned, so this is closer to the main
> site's weight than to ustrip's. Decided: numbered chapters and rules here
> (referenced from the backlog as "spec §5.3"), a `data_model.md`, a
> `backlog.md`, a `dashboard.html`, and tests for everything that can break
> silently (state machine, scoring, retention, tier caps, moderation gate).
> No separate REQ-ID catalogue and no separate test plan document; the
> numbered rules in this file are the requirement IDs.

## 1. What memz is

A meme app built as **one meme engine with two front doors**:

1. **A solo meme creator.** Pick a template (or one of your own images), add
   a caption, get a meme out. Quick, personal, usable outside of any live
   session.
2. **A live multiplayer party game.** A host opens a session and gets a code.
   Friends enter the code on their own phones and are in. Each round everyone
   gets a meme, writes the funniest caption they can before the timer runs
   out, then the group votes on the results and a leaderboard crowns the
   winner.

Both front doors share the same content system: a bank of meme images
organized into packs, part of it public, part of it belonging to individual
users who uploaded their own pictures. That shared bank is the point. It is
what lets a family play with photos from their own trip instead of stock
templates, and it is the one thing the research across the existing apps
(Make It Meme, MemeMaster.io, reMemed, We Meme, Meme It!, Let's Meme, The
Meme Game, NoCap, yalabo, What Do You Meme?) found almost nobody does: most
are either a solo creator or a party game, not both on one engine.

memz is played on phones, in a group, usually in the same room, in Hebrew
first. It is not a social network: there is no feed, no followers, no
public gallery. A meme goes where a person sends it.

## 2. Tiers and limits

memz works with no login at all, works better with a free account, and has a
modestly priced paid tier planned for later. **The tier that matters for a
session is the host's tier**: it sets the session's limits and which images
are available. Every other player joins as a guest, and a player who happens
to be logged in keeps their own personal privileges (saving, their own bank)
regardless of who is hosting.

### 2.1 Guest: no login

Anyone who lands on the app can open a session, get a code, send it to
friends, and play the whole game. Nothing to sign up for.

- Up to 5 participants per session (host included).
- The game draws only from the public bank; the caption deck is a public
  one.
- Who wrote what is tracked per player for the life of the session by the
  guest token (§3.1). Nothing accumulates for a guest afterwards.
- Guests can use the solo creator with the public bank, and can share or
  download what they make. They cannot save.

### 2.2 Free user: the host is logged in

- Up to 10 participants per session.
- The host can play with images that are not public: their own uploads and
  their own packs, alongside the public bank, and chooses what plays (§6.5).
- Sessions and their memes are remembered on the host's account, within the
  free cap.
- Uploads to their own bank within the free cap; own packs; saving memes.
- Any logged-in player, host or not, gets save and their own bank for
  themselves.

### 2.3 Paid user: planned, modest price

Only the host needs to be paid; players are still guests or free users.
Direction, not a timing commitment. Up to 50 participants, unlimited
remembered sessions, a large upload quota. Payments are not in v1 (§13);
the tier exists in the data so an admin can grant it by hand from day one.

### 2.4 The numbers, as settings

Every cap is a Django setting with a `MEMZ_` prefix, read at runtime, so it
can be tuned without a migration. These are the v1 defaults.

| Setting | Guest | Free | Paid |
| --- | --- | --- | --- |
| `MEMZ_MAX_PLAYERS` | 5 | 10 | 50 |
| `MEMZ_REMEMBERED_SESSIONS` | 0 | 30 | unlimited |
| `MEMZ_UPLOAD_LIMIT` (images in own bank) | 0 | 100 | 2000 |
| `MEMZ_PACK_LIMIT` (own packs) | 0 | 10 | unlimited |
| `MEMZ_GUEST_SESSION_TTL_HOURS` | 48 | n/a | n/a |
| `MEMZ_GUEST_MEME_TTL_HOURS` | 48 | n/a | n/a |

Rule 2.4.1: a session's `max_players` is snapshotted at creation from the
host's tier at that moment (data model, `Session.max_players`). Changing a
tier never changes a running game.

Rule 2.4.2: when a free host opens a session beyond the remembered cap, the
oldest remembered session is offered for release (it gets an `expires_at`
like a guest session); the host confirms in the create screen. Nothing is
silently deleted.

Rule 2.4.3: an upload past the cap is refused with a message that names the
cap and the tier, never a generic error.

## 3. Identity: guests, accounts, and memz's own front door

### 3.1 The guest token

Every player in a session, logged in or not, gets a `Player` row with a
random `guest_token` (data model). The browser stores it (a cookie scoped to
`/memz/`, plus a copy in `localStorage` for recovery). Every request to the
game API carries it. It is the single identity mechanism for game logic;
the account, when present, is extra information on top.

Rule 3.1.1: a token is only ever valid for the one session it was issued
for. Rejoining a session after a reload, a crash, or a closed tab works by
presenting the token again; the player lands on the current phase.

Rule 3.1.2: knowing the session code lets you *join* as a new player; it
never lets you act as an existing one. The token is never in a URL.

Rule 3.1.3: a browser holds at most one active token per session. Opening
the same session in a second tab is the same player, not a new seat.

### 3.2 Nicknames

Rule 3.2.1: 1 to 16 characters, any script, trimmed. Unique within the
session; a duplicate gets a number appended ("דני 2") and the player is told.

Rule 3.2.2: a logged-in player's nickname defaults to `MemzProfile.display_name`
and can be changed per session without changing the profile.

### 3.3 Login and sign-up: shared accounts, memz's own pages

Rule 3.3.1: accounts are the site's shared `User` rows. Someone who already
has a babook account signs in with it.

Rule 3.3.2: the sign-in, sign-up, password-reset and sign-out pages are
memz's own templates under `templates/memz/auth/`, in memz's look, mounted
under `/memz/`. They authenticate against the shared `User` with
`django.contrib.auth`. A person who arrives by link and taps "sign in" never
sees another part of the site, and nothing in memz links out — except the
one deliberate door Rule 3.3.3 opens: `/accounts/`, the site's shared
allauth flow. That is proving who you are, not browsing the rest of the
site; it carries no babook chrome of its own and returns straight to
`next`, same as the password form beside it.

Rule 3.3.3: sign-up is email plus password, and the account works
immediately, no verification email (building_an_app.md, "Auth: a lighter
front door is fine"). Email is still required and unique, because it is how
a person recovers the account. Both `/memz/login/` and `/memz/signup/` also
offer "המשך עם גוגל", the site's existing allauth Google provider (§14.1) —
no new view, no new credentials: a link to the same shared
`/accounts/google/login/` flow babook's own login page, ustrip and matazim
already offer, carrying `next` the same way the password form does.

Rule 3.3.4: a `MemzProfile` is created the first time a logged-in person
does anything in memz, never for every babook user.

Rule 3.3.5: logging in mid-session (a guest player taps "sign in" from the
lobby to be able to save memes) attaches the account to the existing
`Player` row. The seat, nickname and score are untouched.

## 4. The party game, screen by screen

Every screen below is a phone screen first (§11). The state each screen
shows comes from one endpoint, the session state (§12.4), polled by every
client; a screen never holds truth the server does not have.

### 4.1 Home

Two big buttons and two small links. **Start a game.** **Join with a code**
(a code field with a large keyboard-friendly input; a code in the URL
`/memz/join/<code>/` skips the field). Small: *Create a meme* (§7), *Sign
in* (or the person's name, when signed in). A one-line explanation of what
this is, and nothing else. No onboarding, no carousel.

### 4.2 Create a session

The host chooses, with sensible defaults preselected so "Start" works on the
first tap:

| Setting | Options | Default | Notes |
| --- | --- | --- | --- |
| Game mode | Normal / Topics / Same Meme / Relaxed | Normal | §5.1 |
| Captions | Typed / Cards | Typed | §5.2 |
| Scoring | Vote / Judge | Vote | §5.3; hidden in Relaxed |
| Rounds | 3 to 10 | 5 | |
| Caption timer | 30 to 90 s | 60 | |
| Vote timer | 15 to 45 s | 20 | |
| Images | Public random / Packs / My images / Mix | Public random | §6.5; only Public random for a guest host |
| Deck | a public deck, or one of mine | public Hebrew deck | Cards mode only |

Rule 4.2.1: the create screen shows the host's tier and the player cap
that comes with it, and a "sign in to get 10 players and your own photos"
line for a guest host. That line is the only upsell in the game flow.

Rule 4.2.2: starting creates the `Session` in `lobby` and the host's
`Player` (`is_host`), issues the token, and lands the host in the lobby.

### 4.3 Lobby

The code, huge, in the unambiguous alphabet (§12.6). A QR code of the join
URL (Rule 4.3.5). A "share the link" button (built as a WhatsApp-specific
invite, Rule 4.3.4, not the originally-specced generic share sheet). The
list of players as they arrive, with their nicknames, and a presence dot
(§4.9). The host sees a **Start** button, enabled once the minimum is
reached (§5.4); everyone else sees "waiting for the host" and the settings
summary.

Rule 4.3.1: joining asks for a nickname only. No other field.

Rule 4.3.2: a join past `max_players` is refused with "this room is full
(5 of 5)", and, for a guest-hosted room, the line about signing in for a
bigger room, shown to the *host*, not to the person who was refused.

Rule 4.3.3: the host can remove a player from the lobby. The removed
player's token is invalidated for this session.

Rule 4.3.4 (ACT-Z.6, added 2026-09-16): every seat in the lobby (host and
guest alike, not the shared big-screen view) gets a "שיתוף בוואטסאפ"
button, opening `https://wa.me/?text=...` with the room code and the
`/memz/join/<code>/` link pre-filled — Avi's own ask, "share like in
whatsapp," not the generic Web Share API sheet F-Z.3.5 originally
specced.

**Amended 2026-09-19 (ACT-Z.15), Avi: "the share game on whatsapp is not
working well."** The button was a `window.open()` on that URL, which an
installed PWA and more than one phone browser block or bounce to wa.me's
"continue to chat" web page rather than the app. It is now a real
`<a href>` to the same wa.me URL (a universal link WhatsApp itself claims,
so it opens the app directly, no popup involved) — and, where the phone
has a share sheet (`navigator.share`), a tap opens that instead, with the
join link. This partly reverses the "not the generic sheet" choice above,
on purpose: the sheet is the one path that works inside a PWA on both
platforms, WhatsApp is the first thing on it, and the direct link is what
Avi reported broken. The button keeps its WhatsApp name and its WhatsApp
link; the sheet is an upgrade on tap, not a replacement. If the direct
link turns out to be enough on Avi's own phone, dropping the sheet is a
one-line change.

Rule 4.3.5 (ACT-Z.6, added 2026-09-16): a QR code of the join URL,
`GET /memz/s/<code>/qr.png` (the `qrcode` library, already a project
dependency via matazim's own invite/join QR endpoints — same shape, a
generated PNG response, nothing stored), shown in **both** the regular
lobby and the shared big-screen view (spec §4.10) — unlike the WhatsApp
button, a QR code on a TV is exactly the point: other players scan it
with their own phones. No extra authorization on the endpoint: the code
it encodes is already shown in plain text on the very same page.
F-Z.3.5's original gap is now fully closed.

### 4.4 A round: captioning

The round starts for everyone at once (`Round.status = captioning`,
`caption_deadline` set). Each phone shows:

- The image dealt to this player (their `Submission.image`), large.
- In Topics mode, the topic above it.
- A caption input: a text field in Typed mode (§5.2), or the player's hand
  of cards in Cards mode.
- A live preview of the meme as they type (rendered in the browser with the
  same layout rules the server uses, §8.1, so what they see is what they
  get).
- The countdown, and a "Submit" button.

Rule 4.4.1: submitting renders the meme on the server (§8.1), creates the
`Meme`, fills `Submission.meme` and `submitted_at`, and locks the input. A
submitted caption cannot be changed. The screen then shows "sent" plus how
many others are still writing, with the countdown.

Rule 4.4.2: the phase ends when every active player has submitted or the
deadline passes, whichever is first. Nobody waits for a full timer when
everyone is done.

Rule 4.4.3: an empty caption cannot be submitted. A player who runs out the
clock without submitting keeps their `Submission` row with `meme` null; they
see "didn't make it this round" and continue to voting normally.

Rule 4.4.4: the last 5 seconds are unmistakable: the countdown grows,
changes colour, ticks (sound, if on), and the phone vibrates once at 5 s
where the browser allows it.

Rule 4.4.5 (SPR-Z.10, 2026-09-18): a player may **throw the dealt image
back and get another**, up to `IMAGE_SWAPS_PER_ROUND` (3) times per round,
any time before they submit. The button says how many are left and
disappears at zero. A swap deals a fresh image under the same rules the
round's own deal follows (unseen first, never one another player is
holding this round, the same personal-stock cap), never re-deals anyone
else, and never touches what the player has already typed. Refused
outright in Same Meme mode, where everyone captioning the same picture is
the entire point (§5.1).

### 4.5 Reveal — and, from SPR-Z.10, the vote itself

Everyone sees the memes one at a time, like a slideshow, on every phone in
sync (`Round.status = revealed`; the client shows the reveal from the
state, the server budgets `REVEAL_SECONDS_PER_MEME` (10 s) per meme into
`reveal_deadline`, host can tap to end it early). Memes are anonymous,
here and everywhere else (Rule 4.7.1).

**Rewritten 2026-09-18 (SPR-Z.10), on Avi's own design after playing the
real game:** the reveal is no longer a passive prelude to a separate
voting screen. Each meme's slot on screen *is* its vote — under it, three
buttons: **אוהב** (2 points), **ככה ככה** (1), **פחות** (0). Everyone in
the room is looking at the same meme at the same moment and rates it
before it moves on. The separate grid where everyone picked one favourite
at the end is gone (§4.6 now describes Judge mode only). Rationale, in
Avi's words: it keeps everyone watching together instead of scrolling a
grid alone, and one verdict per meme separates the scores far better than
one pick per player ever did.

**Built 2026-09-16** (ACT-Z.7 QA pass; this was F-Z.3.9's own tracked gap,
open since SPR-Z.3 — until then every meme showed at once, in a grid with
just a staggered fade-in, never a real slideshow). The index itself isn't
a value the server advances and pushes — there's no socket to push it
over — it's computed identically on every client (a phone, or the shared
big screen) from `reveal_deadline` and `reveal_seconds_per_meme`, both
already in the state payload: `index = floor((now - (deadline -
seconds_per_meme × count)) / seconds_per_meme)`. Every screen reaches the
same number because they're all doing the same arithmetic against the
same two numbers, not because anyone told them to.

Rule 4.5.1: in Same Meme mode the image is shown once, then only the
captions cycle. In every other mode each meme is shown whole.

Rule 4.5.2: submissions with no meme are not in the reveal. They are listed
at the round result as "didn't make it".

Rule 4.5.3: Relaxed mode ends the round after the reveal (§5.1). There is
no rating and no result screen, just "next round" for the host.

Rule 4.5.4 (SPR-Z.10): a verdict is only accepted for the meme that is on
screen **at that moment**, checked on the server against the same
`reveal_deadline` arithmetic every client runs. Without it a client could
rate the whole round the instant the reveal opened, before anyone had read
a single joke.

Rule 4.5.5 (SPR-Z.10): the player whose meme is on screen cannot rate it,
and gets the line **"תעשה פרצוף תמים..."** where the buttons would be.

### 4.6 Voting — Judge mode only, from SPR-Z.10

`Round.status = voting` is now reached **only in Judge mode**, after the
reveal: the judge alone picks one winner out of the whole round, which
can only happen once they have seen all of them. `vote_deadline` set. A
grid of the round's memes, still anonymous; everyone else sees "the judge
is deciding" and the judge's nickname.

In every other game this phase does not happen at all: the reveal already
collected everyone's verdicts (§4.5), so the round goes straight from
`revealed` to `done`.

Rule 4.6.1 (rewritten SPR-Z.10): outside Judge mode, every player gives
**every meme except their own** one verdict — אוהב / ככה ככה / פחות —
cast during that meme's own slot in the reveal. Final on tap, no confirm
dialog (§11), no changing your mind. A player with no submission of their
own still rates everyone else's.

Rule 4.6.2: in Judge mode only the judge sees the grid as tappable; everyone
else sees the grid with "the judge is deciding" and the judge's nickname.
The judge's timer is twice the vote timer.

Rule 4.6.3: the Judge-mode phase ends when the judge has picked or the
deadline passes.

Rule 4.6.4: with fewer than two memes in a round (everyone but one timed
out) there is no contest; the one meme wins the round outright, the screen
says so, and any verdict that landed on it during the reveal is ignored.

### 4.7 Round result

**The running leaderboard, and nothing else** (ACT-Z.14, 2026-09-19):
names and scores, with position changes marked (up, down, new leader).
The host taps **Next round** (or, after the last round, **Results**); a
20 s auto-advance keeps a distracted host from stalling the room.

Relaxed mode is the exception: it has no scores at all, so its result
screen still shows the round's memes (no numbers, no names) — seeing them
together is the whole point of that mode (§5.1).

Rule 4.7.1 (SPR-Z.10, replacing "names come off"): **no screen ever says
who made which meme.** Not the round result, not the podium, not the
end-of-game gallery — and not the state payload behind them, which no
longer carries the author at all, so it cannot leak through a client
someone wrote themselves. The only mark is **"שלכם"** on your own meme,
visible only to you. Names live on the leaderboard and the podium, scores
beside them; the link between a person and a particular joke is never
drawn. Avi's reason, in his words: "זה ישמור על מבוכה" — a joke that lands
badly should cost nobody anything at the table.

Rule 4.7.2 (ACT-Z.14, 2026-09-19): **per-meme scores are never shown
either.** Avi, seeing SPR-Z.10 live: "בסוף הראת גם את רשימת המובילים אבל
גם כמה כל מים קיבל. וזה עושה קשר. אנחנו רוצים רק את טבלת המנצחים" — and he
is right: a meme worth 4 points, displayed beside a leaderboard where
exactly one player's score just rose by 4, names its author as precisely
as a caption would. Rule 4.7.1 without this one is not anonymity, just
indirection. So the points live only in `Player.score`, aggregated, and
the round result is the table alone. The numbers are removed from the
state payload, not merely hidden in the client, for the same reason the
author is: what the server never sends cannot be read out of it by a
client somebody wrote themselves.

### 4.8 Podium and end of game

The top three, biggest first, with confetti for first place; then everyone
else in order; then **the titles** (§9.2), one per player, so nobody leaves
with nothing. Under it: a gallery of every meme from the game, each with a
share button and, for logged-in players, a save button (§8.3, §8.4). The
gallery is **anonymous** (Rule 4.7.1) — only your own memes are marked, and
only to you; it used to name every author, which would have handed back at
the podium exactly what the round result stopped revealing.

Two actions at the bottom: **Play again** and **Leave**.

Rule 4.8.1: *Play again* creates a new `Session` with the same settings and
the same host, and every player still on the podium screen is moved into its
lobby automatically, same nickname, new token, no code to retype. The old
session is `finished` and keeps its data (or expires, per §8.5).

Rule 4.8.2: the podium and the gallery stay reachable at the session's URL
for as long as the session exists (§8.5): a guest can come back the next
morning to share a meme they forgot.

### 4.9 Presence, leaving, dropping, and the host disappearing

Presence is derived from `Player.last_seen_at`, which every state poll
touches (data model).

Rule 4.9.1: not seen for 15 s: shown as away (dim dot). Not seen for 90 s:
marked `is_active = false` and skipped by "everyone has submitted / voted"
checks. Coming back reactivates the player; they rejoin the current phase.

Rule 4.9.2: **Leave** is explicit and immediate: `is_active = false`, the
token is invalidated, and the room is told. Their memes stay in the game.

Rule 4.9.3: if the host is inactive for 90 s during a game, host passes to
the active player with the lowest `seat_order`. The room is told ("דני is
the host now"). A returning ex-host is a normal player. A session where
every player is inactive for 10 minutes is marked `abandoned` by cleanup.

Rule 4.9.4: a room that drops below the minimum (§5.4) mid-game finishes
the current round and then ends the game with whatever scores exist.

### 4.10 Big screen (host's laptop or TV)

`/memz/s/<code>/screen/`: a read-only view of the same state, designed for a
TV or laptop in the room: the code and QR in the lobby, the countdown and
"who has submitted" during captioning, the reveal slideshow, the vote
grid, results, podium. No controls on it; the host's phone stays the
remote. It uses the session code only (it is read-only and shows nothing a
player in the room cannot already see), no token.

### 4.11 AI players

Added post-epic, 2026-09-16 (Avi): "add option for AI players to join the
game... up to three... fun and also easy for testing or a small team
situation." An organizer can add bot seats when opening a game, so a
host testing alone — or a real group of two or three — can still reach
Vote/Judge mode's minimum of three without recruiting anyone.

Rule 4.11.1: at create time only, a **signed-in** organizer picks 0 to
`MEMZ_AI_PLAYERS_MAX` (3) AI seats, always leaving at least one seat for
the host — a bot never displaces the one person who has to be able to
tap "start". A guest host's request is silently forced back to zero
server-side (Avi, 2026-09-16), the same downgrade `image_source` already
gets for a guest — the create screen simply doesn't offer the field to a
signed-out visitor, and the server never trusts the client's own claim
about who is asking either way. **Noted for later, not built now:** Avi
expects this to become a paid-tier-only feature once the site has paid
users to gate it against; free-tier accounts get it for now. Bots are
created immediately, alongside the host, and count toward `max_players`
like any other seat. Their captions and vote choices
come from the site's own OpenAI integration (`app.ai_chat.call_openai`,
through the one named adapter `memz/ai_players.py`, Rule 12.1.1) — the
same model every other AI feature on the site uses, in stub mode when
`OPENAI_API_KEY` is unset, and never the reason a round hangs: a stub
marker, an API error, or an unusable reply all fall back to a small
built-in caption or a plain random vote instead.

Rule 4.11.2: an AI player has no browser and nothing ever polls on its
behalf, so its turn is resolved synchronously from inside `game.sync()` —
the same function that already runs on every action and every state
read. In Cards mode it plays a card from its own dealt hand, same as a
human; in Typed mode it asks the model for one short, playful caption
(the round's topic, if any, is given as context). Voting picks the
funniest of the anonymous options the same way, except it never votes
for its own submission, and in Judge mode it only ever votes when the
rotation actually makes it the round's judge — the same rotation, the
same rule, no special case.

Rule 4.11.3: an AI player is exempt from presence tracking (Rule 4.9)
entirely — always shown as active, never marked away or inactive by
staleness, since staleness measures a human going quiet. It is never
eligible for host handoff. Otherwise it is an ordinary `Player` row: it
can win rounds, receive votes, earn a podium title (§9.2), and appear in
the gallery, same as anyone else — the point is a full extra player, not
a placeholder.

## 5. The rules

### 5.1 Game modes

| Mode | Each round | Voting | Points |
| --- | --- | --- | --- |
| Normal | every player gets a different random image | yes | yes |
| Topics | as Normal, plus a `Topic` shown to everyone; the caption should fit the topic (the crowd judges whether it did) | yes | yes |
| Same Meme | every player gets the same image | yes | yes |
| Relaxed | as Normal | no | no; the reveal is the whole point |

Rule 5.1.1: Topics are drawn without repeats within a session from the
public topics plus, for a logged-in host, their own.

### 5.2 Captioning: typed and cards

**Typed**: free text, 1 to 140 characters, up to 3 lines after wrapping;
the preview shows the wrap and refuses a fourth line (the input stops
accepting). Any script. Emoji allowed; the rendering font must have them or
fall back (§8.1).

**Cards**: each player holds a hand of 7 `CaptionCard`s (`HandCard` rows).
Playing a card submits it as the caption (the meme's `caption_text` is the
card's text, `caption_card` points at it). After the round each hand is
topped up to 7 from the deck.

Rule 5.2.1: a deck is dealt without repeats across the session until it
runs out; then played cards are reshuffled back in. A deck needs at least
`7 × max_players + rounds` cards to be selectable for a session, otherwise
the create screen says why.

Rule 5.2.2: in Cards mode a player may **swap one card per game**: discard
it and draw another, once. A small mercy for a dead hand, and one decision
that makes holding cards interesting.

### 5.3 Scoring

**Vote mode** (rewritten SPR-Z.10, 2026-09-18): a meme scores the **sum of
the verdicts it collected** during the reveal — אוהב 2, ככה ככה 1, פחות 0
— and the round winner is simply the highest total. Nothing else: the old
+1 round-winner and +1 unanimous bonuses are gone, because they existed to
spread out scores that a single pick per player made very flat, and rating
every meme separates them on its own. The gain is that a player can work
out their own score from the buttons they watched people press, which is
worth more than a livelier number nobody can explain. "Unanimous" survives
as a **podium title** (§9.2) — every single rater said אוהב — just not as
points.

**Judge mode**: the judge's pick gets 3 points. Nothing else scores. If the
judge times out, nobody scores that round and the round result says "the
judge fell asleep". The judge rotates by `seat_order` among active players,
starting with the player after the host; a player does not judge twice
before everyone has judged once.

Rule 5.3.1: `Player.score` is a cache written when a round reaches `done`.
The `Vote` rows are the truth; a test recomputes every player's score from
votes and asserts equality, in both modes, with ties and time-outs.

Rule 5.3.2: final ranking: score, then total votes received (from SPR-Z.10,
that tiebreak counts **אוהב** verdicts — the deliberate "this one is
funny", which is what a vote used to mean — not raw rows, since everyone
now rates everything), then earliest `joined_at`. Equal on all three is a
shared position and the podium says "tie".

### 5.4 Minimums, maximums, timers

Rule 5.4.1: minimum to start: 3 players in Vote and Judge modes, 2 in
Relaxed. Maximum: `Session.max_players`.

Rule 5.4.2: all deadlines are absolute server times in the state. Clients
count down to them and never keep their own clock as truth; a phone that
went to sleep and wakes up shows the right phase and the right remaining
time from the next poll.

Rule 5.4.3: phase transitions happen on the server, on the first request
that arrives after a deadline (or the last submit/vote), never in a client.
Two phones reporting the deadline at once cannot double-advance a round;
the transition is guarded by a `select_for_update` on the session.

## 6. The bank

### 6.1 Public bank

`MemeImage` rows with `owner` null, `visibility = public`,
`moderation_status = approved`, organized into public `Pack`s ("family",
"animals", "work", "school"...). Seeded once from `memz/seed_assets/`
by `manage.py seed_memz`, keyed by `seed_key` (check-before-create, never
delete or overwrite; a test runs the seed twice and asserts the second run
changes nothing, building_an_app.md "Data").

Rule 6.1.1: **the public bank contains only images memz has the right to
use in a product**: Avi's own photos, generated illustrations, or images
under a licence that allows it (CC0 or equivalent, recorded per image in
`moderation_note` for now, a `licence` field if it ever matters more).
Famous meme templates are copyrighted photographs; they are not in the
public bank. A user can upload whatever they like into their *own* bank;
that is their call, in their private room.

### 6.2 Uploads: a user's own bank

Rule 6.2.1: logged-in users only, within `MEMZ_UPLOAD_LIMIT` (30 for a
free account from SPR-Z.11, raised from 5 now that a player's own photos
are up to half of what a game deals; 50 paid; a guest cannot upload at
all). JPEG, PNG, WebP; up to 8 MB per file; multiple files per upload
action, from camera or gallery. HEIC from iPhones is accepted if Pillow
can open it on the server, else refused with a message that says "choose
JPEG in the share sheet". **From ACT-Z.15 (2026-09-19) it can:**
`pillow-heif` is a project dependency and registers the format at import,
so an iPhone's camera roll uploads like anything else (stored as a clean
JPEG, Rule 6.2.2). Before that, every HEIC upload was refused with the
"choose JPEG" message — which nobody picking a photo at a party will act
on — and that, with the raw file control below, is what Avi meant by "it
needs to allow images from phone, real camera and files."

Rule 6.2.6 (SPR-Z.11, 2026-09-19): uploading is offered **on the home
screen and in the lobby**, not only in the profile's bank tab — Avi's
ask was for "a clear interface of upload your own image", and a control
nobody finds is the same as a control that doesn't exist. The home and
lobby controls are one implementation (`window.memz.mountUploader`) so
they cannot drift apart; the profile keeps its own fuller bank manager on
top of the same endpoint (thumbnails, moderation badges, delete), since
that screen is for tending the bank, not for adding to it in a hurry.
**Amended 2026-09-19 (ACT-Z.15):** the control is two buttons, "מצלמים"
and "מהגלריה", each driving a hidden file input — never the browser's own
"Choose Files" widget, which is unstyled, in English, and on some phones
opens a document browser with no camera in sight. The camera input
carries `capture="environment"` (what makes a phone open the camera) and
is deliberately not `multiple`, since with `multiple` set iOS drops the
camera option from its sheet; the gallery input is `multiple`. Picking
is the whole gesture: the upload starts on `change`, with no second tap.
The profile uses the same control, mounting it with a callback for the
thumbnail row and the count that only that page has.
The lobby's copy deliberately lives *outside*
the poll-rebuilt game root: everything inside it is re-rendered from the
state every couple of seconds, which would throw away a half-made file
selection or an upload in flight. It is shown in the lobby and hidden
once play starts — mid-round is the wrong moment to be picking photos,
and a round's images are chosen when the round begins.

Rule 6.2.2: on upload the server applies EXIF orientation, strips metadata
(location, device), resizes so the longest side is at most 1600 px, and
stores the result. The original is not kept.

Rule 6.2.3: an uploaded image starts `pending` and is moderated (§6.4)
before it can be dealt or used in the creator. Moderation is fast enough
that the user sees the result in the same visit; a `pending` image shows a
spinner in the bank, a `rejected` one shows why and a delete button.

Rule 6.2.4: a user can delete their own image. Memes already made from it
keep their rendered file (`Meme.image` goes null, data model).

Rule 6.2.5 (decided 2026-09-16, SPR-Z.9, spec §14 item 9): the upload form
carries a plain-text notice — don't upload photos of other people,
celebrities, or existing memes, only what you'd be fine with other players
seeing — rather than a second, unreliable automated detection pass on top
of Rule 6.4.2's existing safety check. The existing report link (Rule
6.4.3) is the mechanism for anything that slips through; there is no
in-app moderation queue for this, same as for the public bank.

### 6.3 Packs

Rule 6.3.1: a logged-in user creates packs (within `MEMZ_PACK_LIMIT`), names
them, adds their own images and public images, reorders, removes, deletes
the pack. Every verb, in-app, no admin (building_an_app.md "Every item is a
real object").

Rule 6.3.2: a public pack is a category. The public packs are curated by an
admin in the Django admin for v1; there is no in-app editor for public
content.

### 6.4 Moderation

Rule 6.4.1: only `approved` images are ever dealt into a game, listed in
the creator, or shown in a bank. This gate is memz's own code and has its
own tests.

Rule 6.4.2: the check itself: memz calls the site's existing image
moderation function as it would an external service (a function call with
an image in and a verdict out; no imports of another app's models, no
shared tables). If that function is unavailable or fails, the image stays
`pending` and the user is told it is being checked, never silently
approved (fail closed for uploads, the opposite of the site's chat gate,
because a bad image in a room is worse than a delayed one).

Rule 6.4.3: a `Meme.share_slug` page carries a small "report" link that
emails the site admin with the slug. No in-app moderation queue in v1.

### 6.5 What plays in a game: image source

| `image_source` | Draws from |
| --- | --- |
| `mix` (**the default**, SPR-Z.11) | the public bank **plus** every approved image any seated signed-in player owns, plus the selected packs if any |
| `public_random` | every approved public image |
| `packs` | the session's selected `packs` (public and the host's own) |
| `own_only` | every approved image any seated signed-in player owns |

**Changed 2026-09-19 (SPR-Z.11), on Avi's ask** ("the images are boring,
I want every signed-in user to upload his own, and whenever he's playing
a random picture will be chosen from his pictures, as well as all the
other banks"):

- `mix` is the **default** for every new session, not `public_random`.
  The engine had been able to deal seated players' uploads since SPR-Z.9,
  but only if the host went and chose it, so in practice nobody's photos
  ever reached a table.
- `mix` now actually includes the public bank. It never did: with no
  packs selected the query fell through to own-uploads-only, so the
  screen's own label ("my photos + the public bank") was not what ran,
  and a room where nobody had uploaded had an *empty* pool.
- A guest host's session is `mix` too, not `public_random`. A guest still
  owns nothing and uploads nothing; what changes is that a signed-in
  *player's* photos now play wherever that player plays, rather than only
  in rooms a signed-in friend happened to open.

Rule 6.5.1: dealing never repeats an image within a session while unseen
ones remain; in Normal and Topics modes no two players get the same image
in the same round while the pool allows. Pool too small for the rounds and
players is caught at create time ("this selection has 12 images; 5 players
× 5 rounds needs 25"), not mid-game.

Rule 6.5.2: for a logged-in host, dealing prefers images the host has
played least in remembered sessions, so a family that plays every Friday
sees new photos first. A cheap count over remembered submissions; no new
model.

Rule 6.5.3 (decided and built 2026-09-16, SPR-Z.9): when
`image_source` allows outside images, *every* signed-in player currently
seated contributes their own approved uploads to the pool, not only the
host's (today's `own_only`/`mix` are host-only). A guest player
contributes nothing — uploading requires an account (Rule 6.2.1), so a
guest simply has none. At least one dealt image per round comes from a
seated player's own stock when any exists, in every mode including Same
Meme (the one shared image for that round can itself be someone's upload);
across the whole session, no more than **50%** of dealt images may come
from players' own stock (raised from 30% in SPR-Z.11, Avi's call: at 30%
the players' own photos were seasoning, and the ask was for them to be
half the game). The ceiling still earns its place — it keeps the public
bank present, so a room where exactly one person uploaded doesn't become
an evening of that one person's camera roll. A player is never dealt their own upload — the pool
for their draw excludes images they themselves own, even though those
same images are still eligible for everyone else. This is why Rule
6.1.1's "their own private room" framing for a user's own bank stops being
literally true the moment this ships: another seated player, a stranger in
a public game, can now be shown it. See §14 item 9 for the still-open
question this raises about upload-time moderation.

## 7. Solo creator

`/memz/create/`: pick an image (public packs; own bank and own packs when
logged in; or upload directly into the creator when logged in), type the
caption with the same live preview and the same 140-character, 3-line
rules as the game, tap **Make it**. The result is a `Meme` with
`source = solo`, rendered exactly as a game meme would be, on a result
screen with share, download and (logged in) save.

Rule 7.1: a guest's solo meme gets `expires_at` per §8.5. A logged-in
user's solo memes are listed under "my memes" (§10) and do not expire.

Rule 7.2: the creator is also reachable from the podium gallery ("make
another with this image"), which is how a good image from a game becomes a
personal meme.

### 7.3 Classic templates, via Imgflip (ACT-Z.5, added 2026-09-16)

Rule 7.3.1: a second creator mode, alongside the bank-image one: pick one
of Imgflip's own templates and type top/bottom text. memz calls Imgflip's
own captioning API (`memz/imgflip_templates.py`) rather than storing their
template library itself — they do the actual compositing, memz downloads
and stores only the result, same as any other `Meme` (`source = solo`,
`rendered` set), with `source_credit` recording which template it came
from (e.g. "Imgflip: Distracted Boyfriend"). `image` is null for these —
there is no bank `MemeImage` behind an Imgflip meme.

Rule 7.3.2: browsing templates needs no Imgflip account (a cached, public
list); making one does, via `IMGFLIP_USERNAME`/`IMGFLIP_PASSWORD`. Without
both configured, the picker still shows templates but captioning refuses
with a plain message — fail closed, there is no meaningful placeholder
image to fall back to.

Rule 7.3.3: v1 only fills a template's first two text boxes (top/bottom).
A template with more than two stays blank past the second — Imgflip's
multi-box form isn't wired in yet.

## 8. Memes: rendering, sharing, saving, expiry

### 8.1 The rendering engine

One function, `memz/render.py`, used by the game and the creator, with a
JavaScript twin for the live preview that follows the same layout rules.

**The JavaScript twin fixed twice on 2026-09-16, in one QA pass (ACT-Z.8):**
first, `CreatorForm`'s caption widget never carried the `data-creator-
caption` attribute `static/memz/creator.js` looks for, so the script's own
first line touching the (null) caption field threw before the canvas ever
drew a single frame — the whole live preview was silently blank the entire
time, on every device, since it was first built. Fixed by adding the
attribute. Once that let the preview actually run, a second, real bug
became visible for the first time: its own hand-rolled bidi reshaper
pre-reversed each Hebrew run's letters the way `python-bidi` does for
PIL — correct for PIL, which has no bidi awareness of its own, but Canvas
`fillText` already applies real Unicode bidi on its own in every modern
browser, so the pre-reversed text got reversed *again*, scrambling every
Hebrew word's own letters. Fixed by deleting the reshaper outright and
drawing the caption exactly as typed, with `ctx.direction` pinned to
`"rtl"` — the same fix in spirit as `render.py`'s own `base_dir="R"` pin
below, and for the same reason.

- Output: JPEG, quality 85, width 1080 px (height follows the image), the
  `Meme.rendered` file.
- Layout: **caption bar above the image**: a white band, black bold text,
  centred, auto-wrapped to the width, auto-shrunk from 64 px to a floor of
  36 px to fit 3 lines. Chosen over the classic Impact top/bottom-with-
  outline for three reasons: it is readable on any image at phone size,
  Hebrew has no Impact tradition to honour, and it needs no stroke
  rendering. The classic style is a backlog item, as a per-session option.
- Text: Hebrew and mixed text laid out with `python-bidi` (already a
  dependency) before drawing, so a Hebrew caption with an English word or a
  number renders in the right order. Tested with the same cases the site's
  other RTL rendering uses. **Fixed 2026-09-16** (ACT-Z.7 QA pass, found by
  Avi live-testing the real game): `get_display`'s base direction was left
  to auto-detect from the caption's first *strong* character, so anything
  starting with an English word, a digit, an emoji or a quote mark — all
  ordinary things to type — got silently treated as an LTR paragraph and
  came out backwards. `base_dir="R"` is now pinned explicitly
  (`render.shape_for_draw`): memz captions are always Hebrew-first RTL,
  never a paragraph direction actually in question. **A second, real
  instance found 2026-09-16** (ACT-Z.10, a real screenshot from the live
  game — "רגע... מה קורה פה?!" rendered with "רגע" spelled backwards): first
  (wrongly) diagnosed as `requirements.txt` pinning only a range
  (`>=0.6,<1`) for `python-bidi`, letting dev and production resolve
  different builds. That fix (`python-bidi==0.6.10`) was deployed,
  confirmed live, and the exact same meme still rendered reversed —
  disproving the theory. **The real cause, found and fixed 2026-09-16**
  (ACT-Z.11): most Linux/macOS Pillow wheels, what Render actually
  installs, bundle `libraqm` and gain real bidi awareness in
  `ImageDraw.text` from it — Windows dev wheels don't. Production was
  reordering `shape_for_draw`'s already-correctly-reordered string a
  *second* time, the same double-reversal bug class ACT-Z.8.2 fixed in
  the browser canvas, just server-side and invisible locally (nothing
  there to double anything with). Fixed by checking
  `PIL.features.check_feature("raqm")` once at import
  (`render.PIL_HAS_RAQM`): when true, `shape_for_draw` hands PIL the line
  *unreordered* and `_draw_caption_bar` passes `direction="rtl"`, letting
  PIL's own raqm layout do the reordering, same as the browser fix; when
  false, behaviour is unchanged (`get_display(line, base_dir="R")`, as
  ACT-Z.7.3/10 left it). Confirmed by hand-comparing rendered glyph shapes
  against known-correct and known-reversed reference renders of the same
  word (not by reading the image directly, which had already produced a
  wrong answer twice earlier the same day) — see backlog.md's ACT-Z.10 and
  ACT-Z.11 sprint notes for the full story, including why the first fix
  didn't hold.
- Font: one OFL font with heavy Hebrew and Latin weights (Heebo Black or
  Rubik Black), vendored under `static/memz/fonts/` and used by both the
  server and the browser preview so they match. Emoji are dropped from the
  render rather than shown broken — decided during the rendering sprint,
  recorded here then, but **not actually implemented until ACT-Z.12
  (2026-09-16)**, found from a real game screenshot with a visible
  broken-glyph box baked into the caption: Heebo Black has no emoji glyphs
  at all, and nothing dropped them first. `render.strip_unsupported_chars`
  now reads the font's own cmap table and drops any character it has no
  glyph for before layout (a dropped character becomes a space, not
  nothing, so an emoji typed with no space around it doesn't fuse its two
  neighbouring words together). A live preview warning when an emoji gets
  dropped (the other half of the original decision) is not yet built.
- A small watermark "memz" in the corner at 40% opacity for guest-made
  memes; none for logged-in users. The one place the free tier is visible
  in the output.

Rule 8.1.1: rendering happens at submit time, synchronously, and takes
under 300 ms on Render's instance for a 1600 px source. The reveal never
waits for a render.

### 8.2 Share

Every meme, everywhere it appears (reveal excluded), has a share button.
On a phone with the Web Share API it shares **the image file itself** plus
the share URL, so WhatsApp gets a picture, not a link. Where files cannot be
shared, it shares the URL; where nothing can be shared, it copies the URL
and says so. Mail is the phone's own mail app via the same sheet.

Rule 8.2.1: the share URL is `/memz/m/<share_slug>/`: a page with the meme
large, Open Graph tags (image, title "a meme from memz") so WhatsApp, mail
and Slack show a preview, a download button, "make your own" (to the
creator), and "play memz" (to Home). Nothing else. It needs no token and no
login.

Rule 8.2.2: an expired or deleted meme's page says so plainly ("this meme
has expired") with the two buttons, not a 404.

### 8.3 Download

Everywhere share is, download is: the rendered JPEG, named
`memz-<slug>.jpg`.

### 8.4 Save (logged in)

`SavedMeme` per (user, meme). Saving clears the meme's `expires_at`. Saved
memes are listed under "my memes" (§10) with unsave and download. Any
logged-in player can save any meme from a game they were in, not only their
own.

### 8.5 Expiry and cleanup

- A guest-hosted session gets `expires_at = ended_at + MEMZ_GUEST_SESSION_TTL_HOURS`
  when it ends, or `created_at + TTL` if it never started; `abandoned`
  sessions likewise from the abandonment time.
- Every meme made in a guest-hosted session, and every guest solo meme,
  gets `expires_at = created_at + MEMZ_GUEST_MEME_TTL_HOURS`.
- Saving a meme sets its `expires_at` to null (§8.4).
- A logged-in host's session is `remembered` with no `expires_at`, until
  Rule 2.4.2 releases it.
- `manage.py memz_cleanup` deletes sessions past `expires_at` (cascading
  players, rounds, submissions, votes, hand cards) and memes past
  `expires_at` that are not saved, and marks stale sessions `abandoned`
  (Rule 4.9.3). It is idempotent and safe to run any time; it runs from the
  site's existing scheduled-job mechanism (the weekly-backup style token
  endpoint triggered by GitHub Actions), daily.

Rule 8.5.1: a test creates a guest session, a remembered session, a saved
guest meme and an unsaved one, moves the clock, runs cleanup, and asserts
exactly the right rows are gone.

## 9. Gamification and delight

The research (spec history, and the party-game literature) is clear on
one thing: **status and shared moments beat points and badges.** memz's
gamification is therefore almost entirely *inside a session*, where the
people are, and is derived from data the game already has. No badge model,
no XP, no streak counters in the database.

### 9.1 In the moment

- The reveal is a show: one meme at a time, full screen, drumroll (sound,
  if on), the caption appearing a beat after the image.
- Votes count up on the result screen, the winner's tile gets a crown and a
  little shake, position changes on the leaderboard animate.
- The last 5 seconds of any timer are a moment (Rule 4.4.4).
- Sound and haptics are on by default, with a mute toggle in the header
  that persists per browser. All audio is small, bundled, and only plays
  after the first tap (browsers require it; the join tap counts).
- Copy is playful and short, in Hebrew, and never mean. "Didn't make it"
  is "לא הספקת, קורה", not "FAILED".

### 9.2 Titles: everyone leaves with one

Computed at the end of a game from votes, submissions and timestamps,
shown on the podium, one per player, best first, no two players the same
title where the numbers allow. The pool:

| Title | Who |
| --- | --- |
| מלך/מלכת הערב (crowd favourite) | most total votes |
| פה אחד (unanimous) | won a round with every vote |
| הרצף (the streak) | won two or more rounds in a row |
| ברגע האחרון (clutch) | won a round with a submission in its last 5 s |
| הזריז/ה (speed) | first to submit in the most rounds |
| הסוס השחור (dark horse) | biggest climb in the last two rounds |
| הפילוסוף/ית (the philosopher) | longest average caption |
| המינימליסט/ית (the minimalist) | shortest average caption that scored |
| הקהל (the crowd) | voted for the round winner most often |
| הסטרייק (the judge's favourite) | judge mode: picked most often |

Rule 9.2.1: titles are not stored. A remembered session shows the same
titles when reopened because they are recomputed from the same rows.

### 9.3 For logged-in players, over time

A profile page (§10) with lifetime numbers computed from remembered
sessions: games, wins, votes received, best meme (most voted, with the
image), titles earned (counted). Nothing cosmetic to buy or unlock in v1;
if identity cosmetics (frames, avatars) come later they get their own
models then.

## 10. Profile and history (logged in)

`/memz/me/`, with tabs:

- **My memes**: saved memes and solo creations, newest first, each with
  share, download, unsave/delete.
- **My bank**: uploads with status, upload button, delete; packs with
  create/rename/add/remove/reorder/delete.
- **My games**: remembered sessions, newest first, each opening its podium
  and gallery again (Rule 4.8.2), with "release" to free a slot toward the
  cap (Rule 2.4.2).
- **Stats**: §9.3.
- **Account**: display name, tier (and "paid until" when paid), sign out,
  and the site's password change.

Rule 10.1: every list here is a real object with add, edit, delete and,
where order matters, reorder, in-app (building_an_app.md).

## 11. Platform, UX and accessibility rules

Rule 11.1: **phone-first**, with the same acceptance criteria ustrip
adopted (its spec §0a.1): 44×44 px minimum tap targets, enforced by a
guard test; destructive controls never adjacent to routine ones; no
browser-native `alert`/`confirm`/`prompt`; no `location.reload()` after an
action, the page patches itself from the response; every control that hits
the network disables itself until the response returns.

Rule 11.2: portrait phone is the design target (360 to 430 px). Desktop
gets a centred column of at most 560 px for the player screens; the big
screen view (§4.10) is the one desktop-first page.

Rule 11.3: **Hebrew, RTL** is the UI language of v1; every UI string goes
through Django's i18n from day one so English is a translation file, not
a rewrite. Images are language-neutral; captions are any script; decks and
topics carry a `language`.

Rule 11.4: colour is never the only signal (a vote, a winner, presence all
have a shape or a word too). Text contrast meets WCAG AA. The countdown is
readable at arm's length.

Rule 11.5: memz is installable as a PWA (manifest and icons under
`static/memz/`, like ustrip), so "add to home screen" gives it an icon and
full screen. No offline mode; a lost connection shows a banner and keeps
polling.

Rule 11.6: a state poll is small (under 8 KB for a 10-player room), cached
with an ETag so an unchanged state is a 304, and the polling interval
adapts: 1 s in captioning and voting, 2 s in lobby and results, 5 s on a
finished session.

## 12. Technical architecture

### 12.1 The Django app

`memz/`: `models.py`, `views.py` (pages), `api/` (DRF), `render.py`,
`game.py` (the state machine: start round, deal, advance, score; the only
place that changes a `Round.status`), `dealing.py`, `titles.py`,
`auth_views.py`, `urls.py`, `admin.py`, `migrations/` from `0001`,
`management/commands/seed_memz.py` and `memz_cleanup.py`, `seed_assets/`.
Templates under `templates/memz/`, static under `static/memz/`. Mounted at
`/memz/` in `mysite/urls.py` before the catch-all, namespace `memz`; its
403/404/500 composed into `mysite/errors.py` by path prefix like matazim
and ustrip.

Rule 12.1.1: `memz` imports nothing from `app`, `matazim` or `ustrip`
except two named adapters, each in exactly one file, so either import can
be swapped for memz's own version without touching anything else: the
moderation function (Rule 6.4.2), through `memz/moderation.py`, and the
site's OpenAI wrapper (Rule 4.11.1, AI players), through
`memz/ai_players.py`.

### 12.2 URLs (pages)

| URL | Page |
| --- | --- |
| `/memz/` | Home (§4.1) |
| `/memz/new/` | Create a session (§4.2) |
| `/memz/join/<code>/` | Join (nickname) |
| `/memz/s/<code>/` | The game: lobby, rounds, results, podium (one page, driven by state) |
| `/memz/s/<code>/screen/` | Big screen (§4.10) |
| `/memz/create/` | Solo creator (§7) |
| `/memz/m/<slug>/` | Meme share page (§8.2) |
| `/memz/me/` (+ tabs) | Profile (§10) |
| `/memz/login/`, `/memz/signup/`, `/memz/logout/`, `/memz/password/...` | Auth (§3.3) |

### 12.3 The REST API (Rule 6 of building_an_app.md)

DRF, under `/memz/api/`, browsable, with a schema at `/memz/api/schema/`.
(SPR-Z.1: the schema is a JSON listing generated from the router itself,
every resource with its verbs, extra actions and fields, so it cannot go
stale. DRF's OpenAPI generator needs `uritemplate`, which the project does
not carry; swapping in drf-spectacular later is a one-line change in
`memz/api/schema.py`.) Full CRUD on every model where a verb makes sense,
with permissions that scope everything to the caller:

| Resource | Verbs | Who |
| --- | --- | --- |
| `images/` | list, create (upload), retrieve, update (title), delete | owner; public images listable by anyone, writable by admin only |
| `packs/`, `packs/<id>/images/` | full CRUD, reorder | owner; public packs read-only |
| `decks/`, `decks/<id>/cards/` | full CRUD | owner; public read-only |
| `topics/` | full CRUD | owner; public read-only |
| `sessions/` | create, retrieve (by code), update settings (lobby only), delete/release | host |
| `sessions/<code>/players/` | list, create (join), update (nickname), delete (leave, or host removes) | token |
| `sessions/<code>/state/` | retrieve | token, or code-only for the big screen |
| `sessions/<code>/start/`, `.../advance/`, `.../again/` | actions | host |
| `sessions/<code>/rounds/<n>/submit/` | action | token |
| `sessions/<code>/rounds/<n>/vote/` | action (Judge mode's single pick, §4.6) | token |
| `sessions/<code>/rounds/<n>/rate/` | action (one verdict for the meme on screen, Rule 4.6.1) | token |
| `sessions/<code>/rounds/<n>/swap-image/` | action (throw the dealt image back, Rule 4.4.5) | token |
| `sessions/<code>/rounds/<n>/swap-card/` | action | token |
| `memes/` | create (solo), retrieve, delete (own) | user or token |
| `saved/` | list, create, delete | user |
| `profile/` | retrieve, update | user |

Rule 12.3.1: game actions authenticate with the guest token (a header,
`X-Memz-Player`), never with the session cookie alone; the DRF
authentication class for it lives in `memz/api/auth.py`. Profile, bank and
saved resources authenticate with the logged-in user.

Rule 12.3.2: the pages are consumers of this API (they fetch state and
post actions with a tiny shared JS helper), not a second implementation.

### 12.3.3 API security: closed by default, opened one resource at a time

The site's DRF defaults are already `SessionAuthentication` +
`IsAuthenticated` (`mysite/settings.py`). memz keeps them. Nothing in
memz's API is reachable without an identity unless a view explicitly says
so, and the only views that say so are the ones a guest player needs, each
with its own narrower rule. The principle from the site's own BKM
("giving an agent a key, without giving it the house") applies to every
endpoint: **the worst case is bounded by what the endpoint can express,
not by who holds the credential.**

Rule 12.3.3.1: **no anonymous CRUD, anywhere.** Every write requires
either a logged-in user or a valid player token for the specific session
being written to. There is no endpoint that accepts an unauthenticated
POST, PUT, PATCH or DELETE.

Rule 12.3.3.2: **object-level ownership on every user resource.** Images,
packs, decks, topics, saved memes and the profile are filtered by
`owner = request.user` in the queryset itself (not only checked on the
object), so a foreign id returns 404, never 403 and never the object. An
admin's public content is writable only by `is_staff`; everyone else gets
it read-only, and `visibility = private` images of other users are not
listable, retrievable or dealable by anyone but their owner, ever.

Rule 12.3.3.3: **the player token is scoped to one session and one seat.**
The `X-Memz-Player` authentication class resolves a token to exactly one
`Player` row; the session in the URL must be that player's session or the
request is 403. A player can submit and vote only as themselves, only in
the current round, only in the phase that accepts it; the state machine
in `game.py` refuses everything else, and the API never takes a `player`
id from the request body. Host-only actions (start, advance, again,
remove player, change settings) check `is_host` on the resolved player,
not a flag in the request.

Rule 12.3.3.4: **the state endpoint leaks nothing it should not.** It
never includes any token, never includes other players' account details
(user id, email), never includes who authored a submission before the
round result phase, never includes votes before the round result, and
never includes a private image the caller could not otherwise see (they
see it because it was dealt into their room, which is the host's choice).
The big-screen variant (code only, no token) gets the same view a player
in the room gets, minus the caller-specific fields (own hand, own vote).

Rule 12.3.3.5: **sessions are not enumerable.** There is no list endpoint
for sessions except a logged-in user's own remembered ones. A session is
reachable only by its code, and a code only reaches sessions that are
`lobby` or `playing` for joining; a finished session's podium needs a
player token or the host's login.

Rule 12.3.3.6: **share pages are by unguessable slug only** (128 bits from
`secrets`), never by numeric id, and never listable. Memes have no public
index.

Rule 12.3.3.7: **rate limits on the abusable surfaces**, via DRF throttling
keyed by IP for anonymous callers and by user otherwise: session creation
(10/hour/IP), join attempts (30/minute/IP, so a code cannot be brute-forced:
the 4-character space is about a million and a wrong code is a slow 404),
uploads (60/hour/user), solo meme creation (60/hour/IP or user), and the
report link (5/hour/IP). Polling is exempt but cheap (Rule 11.6).

Rule 12.3.3.8: **CSRF and cookies.** Session-cookie-authenticated calls
(profile, bank, saved) require the CSRF token like every other site
endpoint. Player-token calls do not use the session cookie for identity
at all, so a cross-site page holding no token cannot act as a player; the
token cookie is `SameSite=Lax`, `HttpOnly` is not possible because the JS
must read it, so it is additionally scoped to `/memz/` and is only ever
sent by memz's own script as a header, never as an ambient credential
the server accepts on its own.

Rule 12.3.3.9: **the browsable API and the schema are themselves gated**:
staff only in production (`DEBUG = False`), so the schema is not a map for
strangers.

Rule 12.3.3.10: **refusal tests outnumber happy-path tests**, the ratio the
ustrip family API set (roughly two to one). For every resource: anonymous
write refused; another user's object 404; another session's token 403;
host action from a non-host 403; submit in the wrong phase 409; vote for
self 400; second vote 409; join past cap 403; upload past cap 403; private
image of another user not in any list, not retrievable, not dealt. These
tests are what make the API safe to leave open on the internet; they are
written in the same sprint as the endpoint, not after.

### 12.4 Real-time: polling, on purpose

The site runs one Render instance on SQLite with no Redis, so WebSockets
via Channels would mean new infrastructure for a game that needs at most a
few dozen phones seeing a change within a second. Decided: **short polling
of the state endpoint** (Rule 11.6), with `Session.version` (an integer
bumped on every change) driving the ETag. Phase transitions are server
side (Rule 5.4.3). If memz ever outgrows this, the state endpoint is
already the one thing a push transport would carry; nothing else changes.

Rule 12.4.1: SQLite is in WAL mode (it already is on the site); 50 players
submitting in the same 5 seconds is 50 short write transactions, which
WAL handles. A load test of 50 simulated players through one round is part
of the game sprint's exit criteria.

Rule 12.4.2 (ACT-Z.7/Z.8, 2026-09-16): every poll still fetches the full
state JSON and calls its screen's own render function, every second —
what changed is that captioning, revealed, voting and result now each
keep a small key (round number, plus whatever on that screen can actually
change — submitted-state, my vote, which meme index the reveal is on) and
skip rebuilding the DOM entirely when a poll's key matches the last one
rendered. This is a client-side patch for a real symptom (a full
`innerHTML` rebuild every second tore a focused `<textarea>` out from
under the phone keyboard, and replayed every animation on-screen for
users just trying to look at something), not the underlying fix Rule
12.4's own ETag/`Session.version` design already calls for — a 304 would
let the *server* say "nothing changed," skipping the render decision
(and the JSON payload) entirely, rather than each screen re-deriving it
client-side. That's F-Z.3.7's own tracked gap, still open.

Rule 12.4.3 (ACT-Z.9, 2026-09-16): every deadline (`caption_deadline`,
`reveal_deadline`, `vote_deadline`) is a server-issued timestamp; the
countdown shown for it, and the reveal slideshow's own "which meme right
now" index (Rule 4.5's own math), compared that timestamp against the
*client's own* clock (`Date.now()`) — correct only if the device's clock
happens to actually be right, which a phone's is not guaranteed to be.
The state payload now also carries `server_time` on every poll; the
client measures its own offset from it (`serverClockOffsetMs`) and
applies that correction (`serverNow()`) everywhere a deadline comparison
happens, rather than trusting the device's clock outright. A crude,
single-sample clock sync (no round-trip-time compensation), good enough
at the ~1s granularity this game already runs at.

### 12.5 Settings

All `MEMZ_*` caps from §2.4, timers' ranges and defaults from §4.2, hand
size, title thresholds, the polling intervals, and the rendering constants
live in `memz/conf.py` with `getattr(settings, ...)` overrides, so a tune is
an env var, not a deploy.

### 12.6 Session codes

4 characters from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (no 0/O/1/I), generated
with `secrets`, unique among sessions not `finished`/`abandoned` (a partial
unique index), retried on collision, 5 characters if 20 collisions in a row
(it will not happen at this scale; the code handles it anyway). Codes are
matched case-insensitively on entry.

### 12.7 Seeding and one-time imports

`seed_memz` creates the public packs, public images from `seed_assets/`,
the public Hebrew and English caption decks and topics, keyed
(`seed_key`, deck name, topic text). Runs on every deploy from
`render.yaml` like the site's other seeds, and, per building_an_app.md, is a
one-time import: never deletes, never overwrites. Tested by running it
twice.

### 12.8 Tests (what can break silently)

- State machine: every transition in `game.py`, including deadline races
  (two clients advancing at once), host handoff, below-minimum ending.
- Scoring: recompute-from-votes equality in both modes, ties, unanimous,
  judge timeout (Rule 5.3.1).
- Dealing: no repeats within a session, no duplicates within a round, pool
  size check at create.
- Tier caps: join refused at cap, upload refused at cap, snapshot of
  `max_players`, remembered-session release.
- Token: wrong token rejected, token from another session rejected,
  invalidated token rejected, reload rejoins.
- Moderation gate: a `pending` or `rejected` image is never dealt or
  listed.
- Retention: cleanup deletes exactly the right rows (Rule 8.5.1).
- Rendering: Hebrew, mixed Hebrew/English/number captions, 3-line wrap,
  shrink-to-fit floor, watermark on guest memes only.
- Seed idempotence (§12.7).
- Phone-first guard: tap target size (Rule 11.1).
- Titles: each rule with a constructed session.
- API security: the full refusal list of Rule 12.3.3.10, throttles
  trigger at their limits, the state endpoint contains no token and no
  pre-result authors or votes, schema gated in production.

### 12.9 Deploy

Dev first, always (building_an_app.md "Deploy discipline"). `migrate memz`
only. `seed_memz` and `memz_cleanup` wired into `render.yaml` and the
scheduled-jobs endpoint. After a push, verify a memz-only page (the share
page of a seeded meme) is live, not the site homepage.

## 13. Not in v1

- Payments and anything that moves money; the paid tier is granted by an
  admin.
- AI caption *suggestions* — helping a human write their own caption. Not
  the same decision as AI players (§4.11, added 2026-09-16): a bot writing
  its own entire turn, never touching a human's.
- English UI (strings are translatable from day one; the translation is a
  later sprint).
- GIF and video memes.
- Free-position or multi-box text; classic Impact top/bottom style (backlog,
  as a per-session option).
- A public feed, likes, comments, following.
- Native apps; the PWA is the app.
- In-app editing of public content (admin only).
- Team or event features (many rooms under one host, tournaments).
- Generating a meme image from a user's own uploaded selfie. Avi's own
  future idea (noted 2026-09-16), floated as a paid-tier feature once the
  tier boundary is real (§14 item 7) — not specced, not built.

## 14. Decisions still open (small, none blocking Sprint 1)

1. ~~**Google sign-in in v1**~~ — decided 2026-09-15 (Avi): yes, via the
   site's existing allauth provider, the same one babook/ustrip/matazim
   already offer. No new account system, no new credentials to manage —
   `/memz/login/` and `/memz/signup/` link to the shared
   `/accounts/google/login/` flow, carrying `next` the same way the
   password form does. See Rule 3.3.3.
2. ~~**Initial public bank content**~~ — resolved SPR-Z.7 (2026-09-15): 8
   packs, 20 images each, AI-illustrated plus reviewed real photos, real
   people/celebrities and existing meme templates both explicitly ruled
   out. Not the full ~25/pack target; extending it is a re-run of the same
   scripts with more scenes, carried forward, not blocking.
3. ~~**Initial caption decks**~~ — resolved SPR-Z.7 (2026-09-15): Hebrew
   tone-reviewed and expanded to 97 cards / 35 topics. English deferred,
   Avi's own call ("lets stick with hebrew for now").
4. **Emoji in rendered captions**: render or drop (§8.1), decided in the
   rendering sprint.
5. **AI players as a paid-tier feature** (Rule 4.11.1, noted 2026-09-16):
   Avi expects this to move behind the paid tier once the site actually
   has paid users to gate it against. Free-tier accounts get it in the
   meantime — nothing to build until that tier boundary is real.
6. ~~**Imgflip's live template API**~~ — resolved and built 2026-09-16
   (ACT-Z.5): memz calls their captioning service (`memz/imgflip_templates.py`,
   `/memz/api/imgflip/...`) rather than downloading and re-hosting their
   template files. The composited result *is* downloaded and stored like
   any other `Meme` (Rule 7.3.1) — Imgflip's own API docs describe the
   output as something callers "can link, embed, or even download and
   host yourself", so this is within what they themselves sanction; the
   underlying template photo's original copyright is still theirs to
   carry either way, same as it would be calling any meme-bot API. Free
   tier, no cost. Verified against the real API with a live account.
7. **A meme generated from a user's own selfie, paid tier** (raised
   2026-09-16, Avi's own idea): explicitly a future idea, nothing to spec
   yet.
8. ~~**A joining player's own uploads inside a shared game**~~ — decided
   and built 2026-09-16, Rule 6.5.3 (SPR-Z.9). A guest contributes nothing
   (uploads are logged-in-only already, Rule 6.2.1); applies to every
   mode including Same Meme; a player is never dealt their own upload
   back (best-effort in `own_only` with a very small pool — see the
   rule's own note).
9. ~~**Upload-time policy for content Rule 6.1.1 bars from the public
   bank**~~ — decided 2026-09-16, written up as Rule 6.2.5: a plain-text
   notice on the upload form, responsibility on the uploader, no second
   detection pass beyond the existing safety check (Rule 6.4.2) and report
   link (Rule 6.4.3).

## 15. Suggested sprint sequence (input to backlog.md)

1. **Skeleton**: app, models, migrations, admin, base template, home,
   auth pages, seed command with a tiny public bank, DRF wiring, schema.
2. **The engine**: `render.py` + browser preview, solo creator, share page,
   download, guest expiry and cleanup.
3. **The game, Normal mode, Vote scoring, Typed captions**: create, lobby,
   token, join, rounds, reveal, vote, result, podium, play again, presence,
   host handoff, big screen, polling with ETag, load test.
4. **Modes**: Topics, Same Meme, Relaxed, Judge scoring, Cards with hands
   and swap.
5. **Accounts and the bank**: profile, uploads with moderation, packs,
   image source selection, remembered sessions and caps, save.
6. **Delight**: titles, sounds, haptics, animations, copy pass, PWA, phone
   guard test, accessibility pass.
7. **Public content**: real packs, real decks, topics; tier admin; deploy.
