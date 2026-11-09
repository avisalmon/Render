# gallery: Data model

Status: **approved by Avi 2026-11-09** (kickoff step 3); the three open points
in section 5 were left unanswered, so their defaults stand. Spec:
[spec.md](spec.md).

## 1. The picture

```
User (babook's, shared) ──1:1── Person ── training (private), language,
                                   │       unlimited skills?, blocked?
                                   │
                 ┌─────────────────┼──────────────────┬─────────────┐
                 │                 │                  │             │
              Exhibit           Like / Star        Comment      Strike
   kind: page | skill | bkm    (person, exhibit)  (exhibit,     (a risky
   topics ── Topic (Avi's list)                    author,       skill upload)
                 │                                  reply_to)
                 │ kind = skill
                 ▼
               Skill ── SkillVersion (1 + up to 4 updates) ── SkillFile
                 ▲
                 │ publishes
          SkillChat ── ChatMessage
              │
              └── AICall (every OpenAI call, its tokens and cost)

Training: Avi's list for the first-post question
```

Everything a visitor sees hangs off **Exhibit**: one table for pages, skills
and BKMs, so likes, comments, a person's page and search work the same for all
three. A skill adds its own rows on top. Getting a skill in goes through a
**SkillChat**, and every cent spent on it is an **AICall** row.

## 2. Models

### Person

The app's own record of a person (Rule 2: nothing is added to babook's `User`).
Created the first time a signed-in person does anything in the gallery.

| Field | Type | Notes |
|---|---|---|
| user | OneToOne → User | cascade |
| display_name | char 80 | shown on cards, comments and their page; defaults to the account's name |
| slug | slug, unique | their public page, `/gallery/u/<slug>/` |
| language | choice | `he` (default), `en`. A visitor's choice is a cookie, not a row |
| training | FK → Training, null | private: the person and Avi only. Asked on the first post |
| training_other | char 200, blank | when they picked "other": where they came from, if they wrote it |
| training_set_at | datetime, null | null means the question has not been answered yet |
| is_admin | bool | Avi; a superuser is admin regardless |
| unlimited_skills | bool | Avi's grant: no 2-skill limit |
| skills_blocked_at | datetime, null | set on the second strike; Avi clears it to unblock |
| created_at | datetime | |

### Training

Avi's list for the "which training did you join" question. Edited on his screen.

| Field | Type | Notes |
|---|---|---|
| name_he, name_en | char 120 | shown in the person's language |
| position | int | order in the list; "other" is always last and is not a row |
| is_open | bool | closed trainings leave the list but keep their people, for the statistics |
| created_at | datetime | |

Seeded once with the five trainings in the spec (one-time seed rule: an
existing row is never touched).

### Topic

Avi's list of areas (Excel, frontend, Arduino, data...). People pick from it for
their pages; the AI picks from it for skills.

| Field | Type | Notes |
|---|---|---|
| name_he, name_en | char 60 | |
| slug | slug, unique | for the search filter |
| position | int | |

### Exhibit

One card in the gallery.

| Field | Type | Notes |
|---|---|---|
| owner | FK → Person | cascade |
| kind | choice | `page`, `skill`, `bkm` (`bkm` only for an admin) |
| title | char 120 | |
| blurb | char 400, blank | a short line; for a skill, its description |
| url | URL, blank | `http`/`https`. A page's site, a BKM's `/bkm/` link. Empty for a skill |
| topics | M2M → Topic | |
| shot | image, blank | the card's picture |
| shot_source | choice | `auto`, `upload`, `none` |
| shot_status | choice | `waiting`, `ok`, `failed` |
| created_at, updated_at | datetime | |

Likes are counted, not stored on the row (as in cohort), so a count never drifts.
Avi's delete removes the card for good; that frees a skill slot.

### Like and Star

Same as cohort: two tables of the same shape, kept apart because likes are
public and stars are private.

| Field | Type | Notes |
|---|---|---|
| person | FK → Person | cascade |
| exhibit | FK → Exhibit | cascade |
| created_at | datetime | |

Unique together (person, exhibit).

### Comment

Same as cohort: one flat thread per card, a reply quotes the comment it answers.

| Field | Type | Notes |
|---|---|---|
| exhibit | FK → Exhibit | cascade |
| author | FK → Person | cascade |
| reply_to | FK → Comment, null | |
| body | text 2000 | |
| created_at | datetime | |
| edited_at | datetime, null | |
| deleted_at | datetime, null | soft delete, so replies still read |

### Skill

What a skill exhibit carries beyond the card.

| Field | Type | Notes |
|---|---|---|
| exhibit | OneToOne → Exhibit | cascade |
| name | slug | the skill's own name, from its SKILL.md |
| origin | choice | `claude`, `copilot`: what was uploaded |
| current | FK → SkillVersion, null | the version people download |
| updates_used | int | 0 to 4; a fifth update is refused |
| downloads | int | counted on every download |

**The 2-skill limit** is counted, not stored: a person's skill exhibits, unless
`unlimited_skills`. A refused or abandoned chat never made a Skill, so it does
not count.

### SkillVersion

One published state of a skill: the first upload, then each update.

| Field | Type | Notes |
|---|---|---|
| skill | FK → Skill | cascade |
| number | int | 1, 2, 3... |
| upload | file | exactly what the person sent (SKILL.md or zip), kept for the record |
| package_claude | file | ready to download: `.claude/skills/<name>/...` |
| package_copilot | file | ready to download: `.github/skills/<name>/...` |
| changes_note | text, blank | what was adapted for the other platform, as told to the uploader |
| chat | OneToOne → SkillChat, null | the conversation that published it; null only if that chat is ever removed |
| created_at | datetime | |

### SkillFile

Each file inside a version, so the check, the page and the download all see the
same list (Rule 1: not a list kept in a JSON field).

| Field | Type | Notes |
|---|---|---|
| version | FK → SkillVersion | cascade |
| path | char 255 | inside the skill folder, e.g. `SKILL.md`, `scripts/run.py` |
| size | int | bytes; the whole skill is capped (about 1MB) |
| sha256 | char 64 | |
| text | text | added in SPR-G.5: the file's text, so the page shows it without opening a zip (skills are text only) |

### SkillChat

The upload conversation, from the first file to the end.

| Field | Type | Notes |
|---|---|---|
| person | FK → Person | cascade |
| skill | FK → Skill, null | set for an update; set at publish for a new skill |
| status | choice | `open`, `published`, `refused`, `abandoned`, `out_of_budget` |
| upload | file | the file the chat is about; replaced when the person sends a fixed one |
| similar_to | FK → Skill, null | the existing skill the duplicate check pointed at |
| verdict | choice, blank | `clean`, `risky`: the last safety reading |
| findings | text, blank | what the safety check found, in plain words |
| cost_usd | decimal | running total of its AICalls; stops at 0.40 |
| stage | choice, blank | `similar`, `fixing`, `confirm`, `retry`: what the chat waits for (SPR-G.6) |
| proposed_blurb, proposed_topics, platform_note | text, M2M → Topic, text | what will be published, exactly as shown to the person (SPR-G.6) |
| started_at, ended_at | datetime | |

### ChatMessage

| Field | Type | Notes |
|---|---|---|
| chat | FK → SkillChat | cascade |
| role | choice | `person`, `assistant`, `system` (a note such as "a fixed file was uploaded") |
| body | text | |
| created_at | datetime | |

### AICall

Every OpenAI call, for the 40-cent ceiling and Avi's per-person cost analysis.

| Field | Type | Notes |
|---|---|---|
| person | FK → Person, null | set null: cost records outlive a deleted card or account, and never block deleting one (SPR-G.9) |
| chat | FK → SkillChat, null | |
| purpose | choice | `duplicate`, `safety`, `convert`, `tag`, `reply` |
| model | char 60 | |
| input_tokens, output_tokens | int | |
| cost_usd | decimal | |
| created_at | datetime | |

### Strike

A risky skill upload. The first one is a warning in the chat; the second blocks
the person and mails Avi.

| Field | Type | Notes |
|---|---|---|
| person | FK → Person | cascade |
| chat | FK → SkillChat | |
| findings | text | what was found |
| created_at | datetime | |
| emailed_at | datetime, null | the email to Avi, set once, so it goes once |
| cleared_at | datetime, null | set when Avi lifts a block: kept on record, no longer counted (SPR-G.8) |

## 3. What is shared, and what is not

- Shared with babook: the `User` table and sign-in only.
- Nothing reads or writes another app's tables. A BKM card is a plain link to
  `/bkm/` that Avi adds, not a read of the bkm app's data. The look is copied
  from cohort into gallery's own templates; no cohort code is imported.
- Files (screenshots, skill uploads and packages) live on the persistent disk
  under the app's own folder, created on first write, never at import.

## 4. The REST API (Rule 6)

Under `/gallery/api/`, with DRF's browsable API:

- read for everyone: `exhibits` (with filters by kind, topic, person, free text),
  `skills` and their versions, `comments`, `topics`, `persons` (public fields
  only, never the training).
- write when signed in: own exhibits, likes, stars, comments, own person row
  (name, language, training), `skillchats` and their messages.
- admin only: `trainings`, `topics` writes, deleting anything, `unlimited_skills`
  and unblocking, `aicalls` and `strikes` (read), the cost-per-person summary.
- skills (SPR-G.9): `skills` (read for all, delete by owner or Avi), `skillchats`
  (POST a file to start, POST `act/` to go on, stop, fix, publish, retry or reply;
  your own, Avi reads all and speaks in none).

## 5. Open points for Avi

1. **BKM cards:** I read "BKM" as cards you add yourself, each linking to one BKM
   in `/bkm/`, with likes and comments like any card. If you meant a single tab
   that just links to `/bkm/`, the `bkm` kind goes away.
2. **Stars:** kept from cohort (a private favourite). Say if you want them out.
3. **Updates:** 4 per skill for its whole life. Should Avi be able to reset that
   for a person, like the unlimited grant?
