# Proposal — Google Drive as the single source of truth (relay `v2`)

**From:** the babook side
**To:** the home system, which owns the contract
**Status:** proposal only. Nothing here is decided, and nothing has been built.
**Date:** 2026-08-15 · Against `v1` as implemented and deployed today.

---

## 0. What this is, and what it is not

This is a request to change the shape of the integration, written by the side
that would lose the most code if you accept it. It is **not** a contract
revision: `relay_api.md` is yours, and if you take any of this it should land
there first and babook will implement against it as usual.

The `v1` relay works. It is deployed, it is tested, and nothing here is prompted
by a problem with it. The proposal comes from the owner, who asked a good
question: why are there two copies of the event log at all?

---

## 1. Why

Today the log exists twice. The house holds the truth, babook holds a
projection, and the whole of §8 in your document exists to keep those two copies
from drifting: idempotent upsert, partial success, 4xx versus 5xx, unknown-field
tolerance, ordering by `ts` and not arrival. Every one of those rules is
correct, and every one of them is only necessary **because there are two
copies**.

Meanwhile the video already lives in Google Drive, which the owner controls,
which outlives both of our machines, and which is more durable than the 1 GB
Render disk babook currently keeps its SQLite database on.

The proposal is to put the event log where the video already is.

**The property that motivates it:** if the house PC dies today, the footage on
its local disk dies with it and babook holds only what was successfully pushed
before it went. If Drive is the store, neither machine holds anything
irreplaceable. That is a better answer than "babook is a projection", because it
stops being something we maintain by discipline and becomes true by
construction.

---

## 2. The shape

**One JSON file per event, written once, never modified.**

This is the heart of it. A single large log file on Drive was the owner's first
idea and we talked him out of it: Drive has no transactions and no reliable
compare-and-swap on file contents, so two writers doing read-modify-write on one
file will silently lose events. In a security log that is the worst available
failure, because it is invisible.

One file per event removes the problem rather than managing it. Each file has
exactly one writer, is written exactly once, and is never edited. There is no
read-modify-write window anywhere in the design.

```
/BabookSecurity/                         <- shared, read-only, with babook
  heartbeat.json                         <- overwritten by the house every ~5 min
  /2026-08-15/
      evt-20260815T181355Z-14096.json    <- the event record
      evt-20260815T181355Z-14096.jpg     <- snapshot, if enabled
      clip-14096.mp4                     <- the 720p viewing copy, as today
  /2026-08-14/
  ...
```

- **Filename** is `evt-<UTC compact>-<event_id>.json`. UTC so it sorts
  lexicographically into chronological order; the true local timestamp with its
  offset stays inside the file, because §8.5 is right and we are not giving that
  up.
- **Folder per day**, not one flat folder. At 200 to 500 events a day, thirty
  days is 6,000 to 15,000 files. Drive copes with that in one folder but listing
  gets slow, and retention becomes a mass delete instead of removing a folder.
- **File body** is the `v1` event object from your §7.1, unchanged, including
  `alarm_state` and `armed`. No new vocabulary to agree.

---

## 3. The decision that makes or breaks it: metadata in the listing

If babook has to open each file to draw a row, then showing fifty events costs
fifty content fetches, because Drive has no batched content read. That is slow
and it burns quota for no reason.

**Request:** write the display fields as Drive `appProperties` on each file.
A single `files.list` call can return them, so babook renders a whole page from
**one** API call and only opens a file when it wants full detail. Drive also
allows querying on `appProperties`, which gives the camera filter almost for
free.

Suggested keys, all short strings:

| Key | Example | Why babook needs it in the listing |
|---|---|---|
| `ts` | `2026-08-15T21:13:55+03:00` | row header, and the sort key for display |
| `event_id` | `14096` | identity, and the delete request |
| `camera` | `Main enterance` | row header, and the camera filter |
| `type` | `person` | row text |
| `severity` | `info` | text colour |
| `armed` | `1` / `0` | the red row |
| `alarm_state` | `AWAY` | shown for context, never interpreted |
| `names` | `Avi` (comma-joined) | row text |
| `unidentified` | `0` | row text |
| `incident_key` | `inc-14090` | grouping, and "delete the whole incident" |
| `clip` | Drive file id of the mp4 | the ▶ Watch link |
| `snap` | `1` / `0` | whether to draw a thumbnail |

Drive caps both the size and the count of properties per file, so keep the
values short and treat the JSON body as the authoritative full record. The
properties are an index, not a second copy of the truth.

**If you would rather not use `appProperties`**, the workable alternative is a
small `index.json` per day that the house appends to. It keeps the one-writer
property, since only the house writes it, but it reintroduces a mutable file and
a partially-written-index window. We prefer `appProperties`, but this is your
call and either can be made to work.

---

## 4. Credentials, and why we are asking for less than you might offer

Today babook holds **no Drive credentials at all**. It stores a link, and Drive
enforces access in the owner's own browser session. If babook were compromised
tomorrow, the attacker would get a copy of the event log and nothing else.

Reading from Drive means babook holds a token, so the scope of that token
matters more than anything else in this document.

**Request: a dedicated service account, with `/BabookSecurity/` shared to it,
read-only.** Not the broad `drive.readonly` scope, which would let babook read
everything in the owner's Drive. A service account sees only what is explicitly
shared with it, which makes the blast radius exactly one folder.

**And babook should keep no write access whatsoever.** Deletes continue to work
the way they do today: babook queues a `delete_incident` command, the house
collects it and removes the JSON, the snapshot and the clip. That keeps "babook
never deletes anything" literally true rather than a promise, and it means a
compromise of babook cannot destroy the footage of a break-in. For a system
whose job is watching a house, that asymmetry seems worth preserving.

---

## 5. What stays exactly as it is

- **The command queue, on babook, over HTTP.** The house is behind CGNAT, so it
  must collect instructions from somewhere reachable, and that reasoning is
  unchanged. Commands cannot move to Drive precisely because that would require
  babook to have Drive write access, which §4 argues against.
- **`GET /commands`, `POST /commands/{id}/ack`**, unchanged, including the
  idempotency rule.
- **`delete_incident`** and its central rule: a request is not a deletion. babook
  marks the row pending and leaves it alone.
- **The heartbeat**, in substance. It moves from `POST /state` to a
  `heartbeat.json` the house overwrites every few minutes; babook reads its
  contents and its `modifiedTime`. Silence detection is unchanged and remains the
  single most important thing the page can tell the owner.
- **Every display rule in your §10**, including the armed red row and its three
  must-nots.

---

## 6. What disappears

- **`POST /events`.** The house writes to Drive instead.
- **`POST /deletions`.** It is no longer needed: the absence of the file *is* the
  deletion. babook notices on its next read.
- **`POST /state`**, replaced by the heartbeat file.
- **Most of §8.** Idempotent upsert, partial success, and the 4xx/5xx contract
  exist to reconcile two copies of the log. With one copy they have nothing to
  do. Ordering by `ts` and unknown-field tolerance both survive, because they are
  about time and about deployment independence rather than about reconciliation.
- **babook's models and migrations for events.**

The contract gets meaningfully smaller. For an integration between two
independently built systems, that is the main prize here, more than any
efficiency.

---

## 7. Retention, and one question we cannot answer for you

The owner suggested **30 days, unless starred**.

With a folder per day, retention is deleting a folder, which is about as simple
as this gets. Starred events are moved or copied to a `/Starred/` folder before
their day is removed.

**Who stars?** Two options, and it is worth choosing deliberately:

1. The owner stars in the Drive UI. babook needs no write access. Simplest.
2. A star button on the phone. It becomes another command kind, exactly like
   `delete_incident`, and babook still needs no write access.

**The question we cannot settle from here:** is thirty days a *storage* policy or
a *privacy* policy? It changes what babook is allowed to do. If it is storage,
babook can cache freely and let entries age out. If it is privacy, then "deleted
from Drive" has to mean "gone from babook within minutes", and we will build the
cache with that as a hard rule rather than an eviction policy. Please tell us
which.

**Related:** today retention drops the video while the text row could reasonably
stay. In a per-file design, does dropping an incident delete the JSON as well as
the clip, or delete only the clip and leave the record? Both are defensible. The
second keeps a searchable history at almost no storage cost; the first is
cleaner if the driver is privacy.

---

## 8. babook's cache

babook would keep a local cache, and we want to be explicit about its status: it
is **a speed layer, never authoritative, and disposable at any moment**. If it is
empty the page still works, just slower. If it disagrees with Drive, Drive wins
without argument. It can be deleted at any time with no loss.

This is the same projection property as `v1`, but it degrades far better: the
worst case is a slow page rather than a lost log.

---

## 9. Failure modes we have thought about

| Situation | Behaviour we intend |
|---|---|
| Drive unreachable or over quota | Page serves cached rows with a clear "cannot reach Drive" banner. Never a blank page, never a silent stale one. |
| House PC dies | Drive intact, page keeps working read-only, heartbeat goes stale and the banner goes red. **Strictly better than today.** |
| babook dies | Nothing lost. Rebuild reads Drive. |
| Clip uploaded but JSON not written | Invisible orphan. Acceptable. |
| JSON written but clip upload failed | A row promising a video that does not exist. **Please write the JSON last**, after the clip and snapshot are safely up, so that anything visible is complete. |
| Event deleted while babook is reading | Row vanishes on the next read. Harmless. |
| Clock skew between house and Drive | Filenames sort by UTC, display uses the offset in the body. Unchanged from §8.5. |

---

## 10. Migration

Data is short-lived under a 30-day policy, so this can be a clean cut rather
than a dual-write marathon:

1. The house starts writing to Drive. Nothing else changes; babook ignores it.
2. babook builds the Drive reader behind a flag and we compare the two views for
   a few days against live data.
3. Cut babook over. The `v1` push endpoints stay live but unread.
4. After a week of quiet, remove them and the event models.

The house can keep pushing to `v1` throughout step 2 and 3 if you would rather
have belt and braces during the changeover. We do not think it is necessary,
but the cost is only that babook ignores it.

---

## 11. Questions for you

1. Can the house write per-event JSON to Drive as reliably as it already
   uploads clips? You know your upload path; we are assuming the answer is yes
   because the clips already get there.
2. Are you willing to write `appProperties`, or would you rather do a daily
   `index.json`? This is the single biggest performance decision.
3. Is a read-only service account with folder sharing acceptable, or do you have
   a reason to prefer OAuth?
4. Should the JSON outlive the clip when retention runs, or die with it? (§7)
5. Is thirty days privacy or storage? (§7)
6. Who stars? (§7)
7. Do you want to keep pushing to `v1` during the changeover?
8. Anything in `v1` we are proposing to drop that you actually rely on? We would
   rather be told now than find out.

---

## 12. What we will do

Nothing, until you have decided. If you accept some or all of this, put it in
`relay_api.md` as `v2` and babook will implement against that document exactly as
it did for `v1`. If you reject it, `v1` is deployed and working and we are happy
to keep building on it. If you accept part of it, that is the most likely and
probably the best outcome.

The one piece we would argue for hardest, independently of everything else, is
**§4**: whatever shape the data takes, babook should hold read-only credentials
scoped to a single folder and should never be able to delete anything itself.
