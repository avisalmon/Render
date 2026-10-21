# cohort: Data model

Status: **written 2026-10-21**; Avi waived the approval gate. Spec:
[spec.md](spec.md).

## 1. The picture

```
User (babook's, shared) ──1:1── Member ── status: pending / approved / declined
                                   │
             ┌─────────────────────┼──────────────────────┬───────────────┐
             │                     │                      │               │
         Exhibit (a site)      Like / Star            Comment         Track (owner)
          │  owner             (member, exhibit)      (exhibit,         three links
          │                                            author,
          └── screenshot                               reply_to)

Material (Avi's shelf): video | file | course
```

Six things a participant meets, one thing only Avi touches (Material), and one
row per person that decides everything they may see (Member).

## 2. Models

### Member

The app's own record of a person (Rule 2: nothing is added to babook's `User`).
One per user who ever asked to join.

| Field | Type | Notes |
|---|---|---|
| user | OneToOne → User | cascade |
| display_name | char 80 | shown on cards and comments; defaults to the account's name |
| status | choice | `pending`, `approved`, `declined` |
| is_admin | bool | Avi and anybody he names; a superuser is admin regardless |
| requested_at | datetime | |
| decided_at | datetime, null | |
| decided_by | FK → User, null | who approved or declined |
| welcomed_at | datetime, null | when the approval email went out; set once, so it is sent once |

Access is one function: signed in, and (`status == approved` or admin). It is
asked by every page and every API viewset (REQ-C.42).

### Exhibit

A site hung in the exhibition.

| Field | Type | Notes |
|---|---|---|
| owner | FK → Member | cascade |
| title | char 120 | |
| url | URL | `http`/`https` only |
| blurb | char 280, blank | optional short line |
| shot | image, blank | the card's picture |
| shot_source | choice | `auto`, `upload`, `none` |
| shot_status | choice | `waiting`, `ok`, `failed` |
| shot_taken_at | datetime, null | |
| created_at, updated_at | datetime | |

Likes are counted, not stored on the row, so a count can never drift from the
likes themselves.

### Like and Star

Two tables of the same shape, kept apart because one is public and the other
private, and a mistake in a shared table's filter would leak one into the other.

| Field | Type | Notes |
|---|---|---|
| member | FK → Member | cascade |
| exhibit | FK → Exhibit | cascade |
| created_at | datetime | |

Unique together (member, exhibit). Stars are only ever read for their own
member.

### Comment

One thread per exhibit; a reply quotes the comment it answers, WhatsApp style
(a flat thread, not a tree).

| Field | Type | Notes |
|---|---|---|
| exhibit | FK → Exhibit | cascade |
| author | FK → Member | cascade |
| reply_to | FK → Comment, null | set null if that comment is removed for good |
| body | text 2000 | |
| created_at | datetime | |
| edited_at | datetime, null | |
| deleted_at | datetime, null | soft delete: the row stays so replies still have something to quote; it renders as "deleted" |

### Track

A subject track page: a container of three links.

| Field | Type | Notes |
|---|---|---|
| name | char 80 | e.g. "מדעי המחשב" |
| slug | slug, unique | |
| owner | FK → Member, null | one owner; null until Avi names one |
| is_example | bool | the imaginary example track |
| position | int | order on the tracks page |
| vision_url | URL, blank | the vision document |
| graduate_url | URL, blank | the graduate profile |
| project_url | URL, blank | the project definition |
| updated_at | datetime | |

Tracks and their owners are created through the chat, by a management command
(`cohort_track add|owner`), and seeded once at the start (one-time seed rule:
an existing track is never touched by the seed).

### Material

Avi's shelf.

| Field | Type | Notes |
|---|---|---|
| kind | choice | `video`, `file`, `course` |
| title | char 160 | |
| line | char 280 | one short line of explanation |
| url | URL, blank | YouTube link, or the babook course link |
| youtube_id | char 20, blank | taken from the URL when saved, for the embedded player |
| file | file, blank | an uploaded document (kind `file`) |
| created_at | datetime | the order shown |
| created_by | FK → User | |

## 3. What is shared, and what is not

- Shared with babook: the `User` table and sign-in only.
- Files (screenshots, uploads) live on the persistent disk under the app's own
  folder, created on first write, never at import (methodology 17).
- Nothing here reads or writes another app's tables. The babook course links
  are plain links Avi pastes.

## 4. The REST API (Rule 6)

Under `/cohort/api/`, every viewset scoped by the access function:

- `members`: list approved members (names only) to participants; full rows to
  admins; create is "ask to join"; approve/decline are admin actions.
- `exhibits`: CRUD; update and delete by the owner or an admin; `retake`
  action.
- `likes`, `stars`: create and delete your own; stars list only your own.
- `comments`: CRUD; edit by the author; delete is soft, by the author or an
  admin.
- `tracks`: read by all participants; update of the three links by the owner
  or an admin; create and delete by admins.
- `materials`: read by participants; CRUD by admins.
