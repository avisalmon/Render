# Security Relay — Specification

**A new app module inside the existing babook.co.il host system**
Version 1.0 · Prepared for build hand-off · 2026-08-15

---

## 1. Overview

A private home security system runs on a PC at the owner's house: 7 Hikvision
cameras, an NVR, GPU person-detection and face recognition. It works perfectly
**inside the house** and is completely unreachable **outside** it.

This module makes babook.co.il the owner's window onto that system from
anywhere. babook receives a **live event log** — *when, which camera, who was
recognised, how serious* — and shows it on one private page.

**babook stores no video, ever.** Video that is worth keeping is uploaded by the
house to the owner's own Google Drive; babook stores only a link to it. Live
camera streams never touch babook at all.

The single most important property to hold in mind while building this:

> **babook is a projection, never a source of truth.** If this database were
> dropped entirely, the home system could rebuild it from scratch. Nothing here
> is authoritative and nothing here may ever be the only copy of anything.

That is what makes the module safe to build quickly: it cannot lose data that
matters, because it never owns any.

---

## 2. Background — what the home system is

You do not need to build any of this. It exists and works. It is described so
the data you receive makes sense.

### 2.1 What it does

| Stage | What happens |
|---|---|
| **Detect** | YOLO on a GPU watches all 7 cameras. A person entering a defined zone raises an **event**. |
| **Record** | A 4K clip of that person is recorded locally while they are present. |
| **Recognise** | Once the clip is on disk, faces are detected, clustered and matched against an enrolled gallery → **names**. |
| **Judge** | A recognised household member is quiet (*info*); a stranger is *warning*; someone on a watchlist is *critical*. |
| **Squeeze** | A 720p H.264 viewing copy is made (~0.5–2 MB) — this is the file that may go to Google Drive. |
| **Retain** | A retention policy decides whether an incident's video is kept or dropped. |

### 2.2 Vocabulary you will see in the payloads

- **event** — one detection on one camera at one moment. Has an integer id that
  is unique and permanent in the home system.
- **incident** — a chain of events close together in time, possibly across
  several cameras. One person walking past three cameras is one incident.
  Carried as `incident_key`; events sharing it belong together.
- **names** — people recognised in that event, e.g. `["Avi"]`. May be empty.
- **unidentified** — count of faces seen but not matched to anyone known.
- **severity** — `info` | `warning` | `critical`, already decided by the house.
  **Do not recompute it.** Display it.

### 2.3 Scale

A quiet house. Expect **50–500 events per day**, in bursts (a person walking
past generates several seconds apart). After the house has been offline you may
receive a few hundred at once.

---

## 3. Why babook, and why it works this way

The house is behind **carrier-grade NAT**: the ISP shares one public address
between many subscribers, so **no inbound connection is possible** and no port
can be opened. A VPN to the house was the original plan and is not available.

CGNAT blocks *inbound* and does nothing to *outbound*. So the house **dials
out** — the same shape the owner's burglar alarm already uses, and the same
shape essentially every consumer security product uses, for exactly this reason.

**Consequence for your design:** babook never initiates anything toward the
house. To send an instruction to the house (§7.2) you place it in a queue and
the house collects it on its next poll. There is no other channel and there
cannot be.

---

## 4. Scope — the boundary

### 4.1 babook DOES

- Accept event pushes from the house (one authenticated machine).
- Store them and show them on one private page.
- Hold a small queue of commands for the house to collect.
- Track whether the house is still reporting, and say loudly when it is not.

### 4.2 babook DOES NOT — please treat these as hard rules

- **No video.** Not stored, not proxied, not streamed. Not even briefly.
- **No live camera access.** babook cannot reach the cameras or the NVR, by
  design, and must never be given a route to them.
- **No independent deletion.** babook never decides a record is old and removes
  it. Retention is decided at the house and pushed here (§7.5).
- **No second user.** One human. Not a family plan, not roles, not sharing.
- **No recomputation.** Severity, names and grouping arrive already decided.
  Displaying them differently is fine; deriving them again is not.

---

## 5. Roles and access

| Actor | How it authenticates | What it may do |
|---|---|---|
| **The house** (one machine) | Static bearer token, §6 | Write everything, read the command queue |
| **The owner** (one person) | Google login (existing `allauth`) | Read the page. No write access at all. |
| **Everyone else** | — | Nothing. `/home` must return **404**. |

The owner's email comes from an environment variable, `SECURITY_OWNER_EMAIL`.
Any other logged-in Google user gets **404**, not 403 — do not confirm that the
page exists.

---

## 6. Authentication (machine)

Every API request carries:

```http
Authorization: Bearer <SECURITY_RELAY_TOKEN>
```

Requirements:

1. Token from a Render environment variable with `sync: false`. Never in git.
2. Compare with **`hmac.compare_digest`**, not `==` — `==` leaks the token's
   length and prefix through timing.
3. Missing or wrong → **401**, with no hint as to which.
4. **CSRF-exempt.** These are machine calls, not browser forms.
5. **HTTPS only.**

This is the same pattern as the existing `app/course_api.py`
(`COURSE_MGMT_API_KEY`), which already does local-machine → production pushes
with a bearer token. **Copying that file's structure is the recommended
starting point** — same idiom, plain Django JSON views, no DRF needed.

---

## 7. The API

Base path: `/api/v1/security/`. JSON in, JSON out, UTF-8.

### 7.1 `POST /api/v1/security/events`

The primary endpoint. The house pushes one or more events.

**Request**

```json
{
  "events": [
    {
      "event_id": 14096,
      "ts": "2026-08-15T21:13:55+03:00",
      "channel": "2",
      "camera": "Main enterance",
      "type": "person",
      "severity": "info",
      "names": ["Avi"],
      "unidentified": 0,
      "incident_key": "inc-14090",
      "drive_url": null,
      "drive_file_id": null,
      "snapshot_b64": null
    }
  ]
}
```

| Field | Required | Notes |
|---|---|---|
| `event_id` | ✅ | integer, **the natural key** |
| `ts` | ✅ | ISO 8601 **with UTC offset** |
| `channel` | ✅ | string |
| `camera` | ✅ | display name |
| `type` | ✅ | `person`, `VMD`, … |
| `severity` | ✅ | `info`/`warning`/`critical` |
| `names` | — | list of strings, default `[]` |
| `unidentified` | — | integer, default `0` |
| `incident_key` | — | string or null |
| `drive_url` | — | string or null |
| `drive_file_id` | — | string or null, needed for deletion |
| `snapshot_b64` | — | base64 JPEG, only if §9 enabled |

**Response `200`**

```json
{ "accepted": 38, "updated": 12, "rejected": [ { "event_id": 99, "reason": "bad ts" } ] }
```

**Limits:** ≤ **200 events** per request, body ≤ **10 MB**. Beyond → `413`.

### 7.2 `GET /api/v1/security/commands`

The house polls this every ~10 seconds. **This is the only way anything reaches
the house.**

**Response `200`**

```json
{ "commands": [ { "id": 77, "kind": "snapshot", "params": { "channel": "2" }, "created_at": "2026-08-15T21:20:00+03:00" } ] }
```

- Only commands not yet acknowledged, oldest first, **max 20**.
- Idle → `{"commands": []}` with **200**. Never 204, never an error.
- `kind` is an **open string**. Phase 1 uses `snapshot` and `resync`. Pass
  through any value; babook does not need to understand them.

### 7.3 `POST /api/v1/security/commands/{id}/ack`

```json
{ "status": "done", "detail": "" }
```

`status` is `done` or `failed`. Stops §7.2 returning it. Acking an unknown or
already-acked id returns **200** — it must be idempotent, because the house may
retry an ack whose response it never received.

### 7.4 `POST /api/v1/security/state`

Roughly every 5 minutes. Overwrites a single row (not a log).

```json
{
  "ok": true,
  "cameras_online": 7,
  "cameras_total": 7,
  "last_event_ts": "2026-08-15T21:13:55+03:00",
  "disk_free_gb": 412.5,
  "notes": ""
}
```

**Its real purpose is detecting silence.** If this stops arriving, the house is
down, the internet is down, or the app crashed — and that is the single most
important thing the owner can learn from this page. Events cannot tell you;
absent events look exactly like a quiet afternoon. See §8.5.

### 7.5 `POST /api/v1/security/deletions`

Retention removed these at the house; babook must forget them.

```json
{ "event_ids": [14096, 14097] }
```

**Response `200`**: `{ "deleted": 2 }`. Unknown ids are **not** an error.

Delete the row **and any stored snapshot file**. The Drive video is deleted by
the house directly — babook does not touch Drive.

---

## 8. Contract rules — where two teams normally drift

These six rules are the ones that cause integration bugs. Each has a reason.

### 8.1 Idempotent upsert on `event_id`

The house retries after failures and flushes a queue after being offline. **The
same event will arrive more than once.** Re-posting an existing `event_id` must
**update** that row — never duplicate, never error.

### 8.2 Partial success

If 40 events arrive and 2 are malformed: **store the 38**, list the 2 in
`rejected`, return 200. Rejecting the whole batch makes the house retry all 40
forever and the good 38 never land.

### 8.3 `4xx` and `5xx` mean different things

The house treats them as a contract:

- **`5xx` / network error** → *babook's problem, retry forever with backoff.*
- **`4xx`** → *this request will never succeed, drop it and log.*

**Therefore: never return `5xx` for bad input.** A malformed event answered with
500 will be retried indefinitely and will block the queue behind it.

### 8.4 Ignore unknown fields

The house may add fields before babook knows about them. Unknown keys must be
**ignored, not rejected**, so the two sides deploy independently and neither
blocks the other's release.

### 8.5 Time is explicit

Every timestamp carries a **UTC offset** (`+03:00`). The house is in Israel,
which observes DST; a naive timestamp would silently shift by an hour twice a
year and the log would be quietly wrong. Store as given; display in local time.

### 8.6 Order by `ts`, not arrival

Events arrive **late and out of order** after the house reconnects. Always sort
for display by `ts`. Gaps in `event_id` are normal and mean nothing.

---

## 9. Snapshots — one decision needed before building

`snapshot_b64` carries the JPEG frame that triggered the event (~30–80 KB).

- **Enabled**: the page shows *who was at the door* — a thumbnail per row. This
  is most of the page's value.
- **Disabled**: text only; babook holds no imagery of the house whatsoever.

**Recommended: enable, with limits.** Video never touches babook either way,
which is the line that actually matters.

If enabled:

- Cap **200 KB** per event; larger → `413`.
- Store as **files on the persistent disk** under `/var/data/security/`, not as
  database blobs.
- Delete the file when §7.5 removes the row.
- **Watch the disk**: it is **1 GB total and shared with the site's own SQLite
  database**. At 50 KB each, 10,000 snapshots ≈ 500 MB. A cap plus a simple
  usage check is required, not optional.

**→ Owner must confirm: enable snapshots, yes or no?**

---

## 10. The `/home` page

One page. One user. Phone first — it will mostly be read on a phone.

```
┌────────────────────────────────────────────┐
│  🟢  System OK · last contact 2 min ago    │   ← from §7.4; RED when stale
│      7/7 cameras online · 412 GB free      │
├────────────────────────────────────────────┤
│  [ Today ▾ ]  [ All cameras ▾ ]            │
├────────────────────────────────────────────┤
│ ▣  [15/08/26] 21:13  Main enterance        │
│    person: Avi                      ▶ Watch│
├────────────────────────────────────────────┤
│ ▣  [15/08/26] 20:48  Kitchen view    ⚠     │
│    person: Unrecognized             ▶ Watch│
├────────────────────────────────────────────┤
│ ▣  [15/08/26] 19:02  Loundry Yard          │
│    person: Noam                            │
└────────────────────────────────────────────┘
```

**Required elements**

1. **Status banner** from §7.4. Green when fresh. **Red and prominent** when the
   last `/state` is older than **15 minutes**: *"⚠ No contact for 34 minutes."*
2. **Event list, newest first.** Row format — deliberately identical to the
   home system's own UI so the two read alike:
   `[dd/mm/yy] hh:mm · Camera · person: Avi`
   24-hour clock, no seconds.
3. **Severity styling**: `info` neutral · `warning` amber · `critical` red.
4. **Snapshot thumbnail** per row when present (§9).
5. **▶ Watch** when `drive_url` is set. A plain link — it opens Google Drive,
   which enforces its own access control, so it works only in the owner's
   logged-in Google session. **babook neither proxies nor stores the video.**
6. **Filters**: by day, by camera.
7. **Pagination or lazy load** — at 500 events/day the list grows quickly.

**Refresh:** the page may poll a small JSON endpoint every ~30 s to append new
rows. There is no requirement for anything faster, and **no WebSocket** (see
§11.2).

---

## 11. Implementation notes for this codebase

### 11.1 Reuse what is already here

`app/course_api.py` already implements this exact shape — bearer token, plain
Django JSON views, no DRF, idempotent upsert, machine pushing to production.
Start there. `app/dashboard_views.py` shows the same token idiom for triggered
actions (`BACKUP_TRIGGER_TOKEN`).

### 11.2 WSGI — no WebSockets

`render.yaml` starts `gunicorn mysite.wsgi:application`. That is WSGI, so
**WebSockets and long-lived SSE are not available** without migrating the whole
site to ASGI. This is why the design is polling on both sides. **Do not migrate
the deployment for this module** — polling is entirely adequate here.

### 11.3 Environment variables

Add to `render.yaml` with `sync: false`:

```yaml
      - key: SECURITY_RELAY_TOKEN
        sync: false
      - key: SECURITY_OWNER_EMAIL
        sync: false
```

### 11.4 Storage

- Rows in the existing SQLite database (`/var/data/db.sqlite3`).
- Snapshots as files under `/var/data/security/` if §9 is enabled.
- **The disk is 1 GB and shared with the site.** Currently ~13 MB is used, so
  there is room — but this module is the first thing here that grows
  continuously, so the cap in §9 matters.

### 11.5 Indexes

Query patterns are "newest first", "by day", "by camera", and "upsert by
event_id". Index `event_id` (unique) and `ts`.

### 11.6 Migrations

Additive only. The house and babook deploy independently and neither waits for
the other (§8.4).

---

## 12. Errors

```json
{ "error": "bad_request", "detail": "events[3].ts is not ISO 8601" }
```

| Code | When |
|---|---|
| `400` | malformed JSON, missing required field |
| `401` | missing or invalid bearer token |
| `404` | authenticated human who is not the owner |
| `413` | over the limits in §7.1 or §9 |
| `429` | rate limited (the house backs off) |
| `5xx` | babook's own failure — **never for bad input** (§8.3) |

---

## 13. Non-functional

| | |
|---|---|
| **Write rate** | 50–500 events/day; bursts to 200 in one request after downtime |
| **Poll rate** | One `GET /commands` every ~10 s, continuously, forever |
| **Latency** | Not critical. Seconds are fine everywhere. |
| **Availability** | babook may be down for hours. The house queues and re-sends; nothing is lost. |
| **Retention** | None of babook's own. Driven entirely by §7.5. |
| **Versioning** | `v1` never breaks. New behaviour goes to `v2`. |

---

## 14. Definition of done

Acceptance tests — each maps to a rule above.

1. ☐ Five endpoints from §7 exist and require the bearer token (§6).
2. ☐ **Idempotency**: post the same batch twice → one set of rows, `updated`
   reflects the second call.
3. ☐ **Partial success**: a batch of 3 with 1 malformed → 2 stored, 1 in
   `rejected`, HTTP 200.
4. ☐ **Bad input returns 4xx, never 5xx** (§8.3).
5. ☐ **Unknown extra field** in an event payload is ignored, not rejected.
6. ☐ Wrong/missing token → 401. Token compared in constant time.
7. ☐ `GET /commands` with nothing pending → `200 {"commands": []}`.
8. ☐ Ack of an unknown id → 200.
9. ☐ `POST /deletions` removes rows **and snapshot files**; unknown ids are not
   an error.
10. ☐ `/home` requires Google login; a non-owner account gets **404**.
11. ☐ `/home` shows the **"no contact for N minutes"** banner when `/state` is
    older than 15 minutes.
12. ☐ Events display ordered by `ts`, not arrival order.
13. ☐ `▶ Watch` renders only when `drive_url` is present, as a plain link.
14. ☐ **No video is stored, proxied or streamed anywhere in the module.**
15. ☐ Env vars present in `render.yaml` with `sync: false`.

---

## 15. Out of scope — please do not build

Listed because each is a plausible good idea that would be wrong here:

- Video hosting, transcoding, thumbnails-from-video, or streaming.
- Any direct connection to the house, its cameras, or its NVR.
- User accounts, invitations, roles, or sharing.
- babook-side retention, archiving or clean-up jobs.
- Recomputing severity, re-grouping incidents, or re-identifying faces.
- Push notifications (a later phase, and probably not from babook).
- A write API for the owner. The page is **read-only** to humans.

---

## 16. Open questions for the owner

1. **Snapshots — enable?** (§9) Recommended yes, with the 200 KB cap.
2. **How long should the log live on babook?** The house drives deletion for
   incidents whose video is dropped, but text-only rows could stay indefinitely.
   Suggested: keep all text rows, since they are tiny.
3. **Any second viewer ever?** The design assumes exactly one human forever.
   If that could change, say so now — it is much cheaper to allow for than to
   retrofit.

---

## 17. Contact / source of truth

The interface contract is owned by the home-system repository and mirrored here.
If this document and the home system's `docs/relay_api.md` ever disagree, **the
home system's copy is authoritative** — it is generated from the code that
sends the data.
