# bkm: Data model

Status: **approved by Avi, 2026-10-26.** Spec:
[spec.md](spec.md).

## 1. The picture

```
User (babook's, shared) ──1:1── Reader (display name)
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
           Like (public)      Star (private)       Comment
         (reader, bkm)       (reader, bkm)     (bkm, author, reply_to)
                │                  │                  │
                └──────────────────┴──────────────────┘
                                   │
                                  Bkm  (one card on the wall; added by Avi only)
```

One thing on the wall (Bkm), three things a signed-in person does to it
(Like, Star, Comment), and one small row per person (Reader) so the app
never adds anything to babook's `User` (Rule 2).

## 2. Models

### Bkm

One BKM, one card. Created and changed only by Avi, through the chat (a
management command) or the API as admin. Never by a form for others.

| Field | Type | Notes |
|---|---|---|
| slug | slug, unique | e.g. `full-stack`; also the card's anchor on the wall |
| name | char 80 | e.g. "FullStackBKM", as shown on the card |
| tagline | char 160 | the one line on the card |
| repo_url | URL | the GitHub repository; what people clone |
| page_url | URL | the BKM's GitHub Pages page; where the card leads |
| picture | image, blank | a picture of what the BKM makes: the real DE10-Lite board, the Single Button kit, an illustration for full stack. Kept in the app's own folder |
| position | int | order on the wall; Avi decides it |
| is_published | bool | off hides the card without deleting its likes and comments |
| added_at, updated_at | datetime | |

When Avi gives a repo, Claude fills name, tagline and page_url from GitHub
once; after that the row is the truth (one-time filling, never synced again
over Avi's edits).

**The picture is the result, not the page** (Avi, 2026-10-26): a photo of
the thing the BKM teaches you to make (mostly hardware: boards, kits,
robotic dogs), or a creative illustration when the result is not a thing
(full stack). Avi sends the photo in the chat, or Claude takes one from the
BKM's own repo or Pages site, or draws one, and Avi approves it. Never an
automatic screenshot.

**Which BKMs are on the wall:** only finished ones. Avi says when a BKM is
complete, and Claude adds it. As of 2026-10-26: FullStackBKM,
SingleButtonKitBKM, De10LiteBKM. De10NanoBKM is not started and is not on
the wall.

### Reader

The app's own record of a signed-in person, made the first time they do
something here.

| Field | Type | Notes |
|---|---|---|
| user | OneToOne → User | cascade |
| display_name | char 80 | shown on comments; from the account's name at first |
| joined_at | datetime | |

### Like and Star

Two tables of the same shape, kept apart because one is public and the
other private (the same choice as cohort, for the same reason: one shared
table with a filter is one bug away from showing someone's stars).

| Field | Type | Notes |
|---|---|---|
| reader | FK → Reader | cascade |
| bkm | FK → Bkm | cascade |
| created_at | datetime | |

Unique together (reader, bkm). Likes are counted on the page, never stored
on the Bkm row.

### Comment

One thread per BKM; a reply quotes the comment it answers, WhatsApp style.

| Field | Type | Notes |
|---|---|---|
| bkm | FK → Bkm | cascade |
| author | FK → Reader | cascade |
| reply_to | FK → Comment, null | set null if that comment is removed for good |
| body | text 2000 | plain text, escaped on the page |
| created_at, edited_at | datetime | edited_at null until edited |
| deleted_at | datetime, null | soft delete, so replies still have something to quote |

The author edits or deletes their own; Avi can delete any.

## 3. What is shared, and what is not

- Shared with babook: the `User` table and sign-in only.
- Nothing about a visitor who is not signed in is stored.
- The phone notice's "dismiss" is remembered in the browser, not in the
  database: it is a per-device convenience, not data.
- Pictures live on the persistent disk in the app's own folder, created on
  first write, never at import (methodology 17).

## 4. The REST API (Rule 6)

Under `/bkm/api/`, DRF, browsable:

- `bkms`: list and read for everybody (the wall is public); create, update,
  delete for admins only.
- `likes`: list counts for everybody; create and delete your own.
- `stars`: only your own, ever.
- `comments`: read for signed-in people; create, edit and delete your own;
  admins delete any.
- `readers`: your own row (display name).

## 5. Decided

1. **The card's picture** is a picture of the result (see Bkm above).
2. **De10NanoBKM** stays off the wall; BKMs go on only when Avi says they
   are complete.
