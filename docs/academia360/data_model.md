# Academia360: Data model

> **Status: approved by Avi, 2026-11-26**, with the open questions in
> section 12 left to settle during the build. One addition from the same
> conversation: every write records its actor, a person in the app or Avi's
> agent working from the chat (`ChangeLog.actor_kind`, section 10 and spec
> chapter 3).
> This is the shape of the data on its own, kept apart from the spec on
> purpose ([building_an_app.md](../building_an_app.md), Rule 4). The
> decisions it rests on are in [spec.md](spec.md) chapters 1 and 2. The
> reference data it is modeled on is described in
> [reference/README.md](reference/README.md).

Five things shape everything here:

1. **Everything is a row.** An institution, a study program, a professor, a
   KPI, a budget line, a review answer, a letter: each is a model with its
   own fields, never a blob of text or a JSON file the app reads. The
   reference's `institutions.json`, the per-institution `data_structured.json`
   files, the CSVs, the spreadsheets and the letters are imported once into
   these models; after that the database is the only truth, and the app
   grows by adding rows.
2. **Every row knows how public it is.** The app has three circles of
   visibility: **public**, **institution** (its own leaders) and
   **committee**. Each model below sits in exactly one circle, marked in its
   table. A query never crosses a circle the person is not in, and the AI
   index carries the same mark on every chunk.
3. **The public side and the program side are separate.** What an
   institution *is* (section 3) is public knowledge that outlives any
   program. What it *submitted to Academia 360* (sections 4 to 7) hangs off a
   separate `Participation` row. Tomorrow's second program, or a second
   round, is another `Program` and another `Participation`, not a rewrite.
4. **Time is a column.** Student counts, KPI values and budgets are rows with
   a year, so a trend is a query and a forecast sits next to the actual.
5. **Files are evidence, not data.** A submitted PDF or spreadsheet is kept
   (privately) and linked, but the numbers and texts the app shows are
   extracted into rows the person can read, compare, fix and search.

---

## 0. The map

```
Program ──* Criterion ──* ReviewQuestion
Program ──* KpiDefinition (mandatory ones)
Program ──* AcademicYear

Institution ──* Unit ──* StudyProgram
Institution ──* Researcher ──* ResearcherMetric / ResearcherLink
Institution ──* ResearchCenter, Collaboration, InstitutionMetric, ProfileSection
Institution ──* PublicComment, Like, CorrectionProposal

Institution ──* Participation ──1 Program
Participation ──* Submission ──* SubmittedFile
Submission ──1 Analysis ──* CriterionFinding
Submission ──* PlanProgram            (the study programs the plan updates)
Submission ──* KpiDefinition (institutional ones) ──* KpiValue
Submission ──* BudgetLine, Commitment
Submission ──* Review ──* ReviewAnswer
Submission ──* Discussion ──* DiscussionPost
Submission ──1 Decision
Submission ──1 ResponseLetter ──* LetterSection

User ──* Role (admin / committee / leader), CommitteeAttribute, LeaderOf
User ──* AiConversation ──* AiMessage ; AiUsage
Everything ──* ChangeLog ; sensitive rows ──* AccessLog
```

---

## 1. People, roles and attributes

Circle: **committee** (the admin sees it all; a person sees their own).

| Model | What it is | Main fields |
| --- | --- | --- |
| **Role** | One role a person holds in this app. A person may hold several; the higher one wins (spec 2.6.1). The app's own model, one-to-many to the site's shared `User`; it never adds fields to `User` | user, kind: `admin` / `committee` / `leader`, granted_by, granted_at, active |
| **CommitteeAttribute** | A mark on a committee member: `chair` (decides) or `reviewer` of one institution (the split in the reference). Attributes, not roles (spec 2.6.2 and 2.6.3) | user, kind: `chair` / `reviewer`, institution (reviewers only), program, since |
| **LeaderOf** | Links a program leader to their institution. Several leaders per institution are allowed (2.6.4); a leader of two institutions is two rows | user, institution, title as shown (e.g. "סגנית נשיא לעניינים אקדמיים"), active |
| **Invitation** | A role granted to an email before the person has an account, redeemed on first sign-in | email, role kind, institution (for leaders), token, sent_at, accepted_at, sent_by |
| **PublicProfile** | What a signed-in member of the public may set: a display name for comments | user, display_name |

Signed-in people with no `Role` row are the public. Anonymous visitors are
the public too, with no row at all.

## 2. The program

Circle: **public**, except where marked.

| Model | What it is | Main fields |
| --- | --- | --- |
| **Program** | A funding program of ות״ת. Academia 360 is the first row | name, short name, body (ות״ת / מל״ג), years (2024 to 2028), total budget, description, official link, status |
| **AcademicYear** | A year the program runs in, with both names | program, hebrew name (תשפ"ה), gregorian span, order |
| **Criterion** | One domain the committee judges by, in order: formal requirements, institutional strategy, the 20% target, the standard (תו תקן), innovation in teaching, employability, community, faculty training, additional components, management and budget, performance measures. Also the frame for every analysis and every review | program, name, order, description, weight (if ever used) |
| **ReviewQuestion** | One line of the committee's review form under a criterion ("הוצג תכנון לעדכון לפחות 20% מתכניות הלימוד") | criterion, text, order, kind: `checklist` / `text`, active |
| **GuidelineSection** | The program's guidelines as the app shows them, section by section, editable by the admin | program, title, body (sanitized), order |
| **KpiDefinition** (mandatory ones) | The four measures ות״ת requires of everyone. Institutional ones live on the submission (section 5) | program, name, explanation, how measured, `is_mandatory=True`, order |
| **Allocation** | How much each institution may ask for, and its base numbers (the tracking sheet). *Committee circle* | program, institution, undergrad students (תשפ"ד), approved programs count, allocation (thousands ₪), notes |

## 3. The institution, as public knowledge

Circle: **public**. This is the general-interest site anyone can read.

| Model | What it is | Main fields |
| --- | --- | --- |
| **Institution** | One higher-education institution. 32 rows from the reference to start; the list grows | name he, name en, slug, kind: `university` / `academic_college` / `teacher_training` / `research_institute`, city, region (B.2: `north` / `haifa` / `center` / `tel_aviv` / `jerusalem` / `south` / `judea_samaria`, from the city), lat, lng (B.2: the main campus, seeded by city in the import, for the map), website, founded, founder, campuses (rows below), logo, unique identity (short text), is budgeted by ות״ת, active |
| **Campus** | A campus or site | institution, name, city |
| **Unit** | A faculty, school or department, nested | institution, parent unit, name, kind: `faculty` / `school` / `department`, website |
| **StudyProgram** | A degree program ("learning track"). The thing the 20% target counts | institution, unit, name, degree (B.A., B.Sc., B.Ed., ...), field (one of the 15 למ"ס fields), level: `undergrad` / `masters` / `phd`, active |
| **StudyProgramCount** | Students and graduates of a program in a year (נספח א, sheet 2) | study program, academic year, year-1, year-2, year-3, year-4 counts, graduates, source |
| **InstitutionMetric** | A number about the institution at a point in time: total students, faculty count, by level, by rank, growth. The CSVs of the reference, as rows | institution, metric key, year, value, unit, source, source url, as_of |
| **Researcher** | A professor or researcher worth showing: the "leading researchers" pages | institution, unit, name he, name en, title, areas (text), focus, kind: `algorithmic` / `applied` / other, is_leading, photo, bio (short) |
| **ResearcherMetric** | h-index or citations, dated, so it can be refreshed | researcher, metric: `h_index` / `citations`, value, as_of, source |
| **ResearcherLink** | A verified external profile | researcher, kind: `scholar` / `orcid` / `dblp` / `homepage` / `other`, url, verified_at |
| **Publication** | A selected work of a researcher | researcher, title, venue, year, citations, url |
| **Grant** | A notable grant | researcher, funder, title, year |
| **ResearchCenter** | A center or lab | institution, name, full name, founded, focus, equipment, partners, url |
| **Collaboration** | A partner of the institution | institution, kind: `academic` / `industry` / `government` / `community`, partner name, description |
| **ProfileSection** | Long-form public text about the institution: overview, research strengths, innovation and entrepreneurship, rankings, timeline. Written by the admin, from the reference's reports to start | institution, kind, title, body (sanitized), order, as_of |
| **TimelineEvent** | A dated milestone in the institution's story | institution, year, text |
| **PublicDocument** | A public file worth linking (a public strategic plan an institution chose to publish, a press item) | institution, title, file or url, kind, published_at |

## 4. Taking part in the program

Circle: **institution** for what the institution itself submitted and sees;
**committee** for the rest. Everything under here hangs off one
`Participation`.

| Model | What it is | Main fields |
| --- | --- | --- |
| **Participation** | One institution in one program. Did it apply, where it stands now | institution, program, applied (yes / no / did not apply), status: `invited` / `submitted` / `under review` / `responded` / `approved` / `declined` / `reporting`, first submitted at, notes (committee) |
| **Submission** | One package the institution sent in: the original proposal, an updated plan, an execution report, an annual KPI report. Each is reviewed and answered on its own, so the cycle repeats cleanly (spec 2.1 step 6) | participation, kind: `proposal` / `updated plan` / `execution report` / `kpi report` / `budget report`, academic year, submitted at, submitted by (leader or admin), status: `draft` / `submitted` / `under review` / `responded`, cover note |
| **SubmittedFile** | One file of a submission, kept in private storage, never under the public media folder | submission, kind: `plan` / `annex A measures` / `annex B budget` / `commitment to matching funds` / `declaration` / `cover letter` / `signature page` / `report` / `other`, file, original name, size, uploaded by, uploaded at, extracted text (for the AI index) |
| **ContactPerson** | Who speaks for the institution on the program, as the submission names them. *Committee circle* | participation, name, title, email, phone, is_primary |
| **GraduateProfile** | דמות הבוגר: the graduate the institution says it is shaping. The committee asks for it explicitly | submission, text, skills (rows below) |
| **GraduateSkill** | One skill or trait in the graduate profile | graduate profile, name, description, order |
| **Standard** | The institution's תו תקן for an updated program: what makes a program count as updated | submission, description, levels addressed (institution / faculty / program / course), minimum bar, review mechanism |
| **PlanProgram** | A study program the plan commits to update, with its state (נספח א, sheet 2 and the 20% target) | submission, study program, planned year, status: `planned` / `in progress` / `updated`, students covered, notes |
| **PlanComponent** | One concrete thing the plan does, under a criterion: a new course type, a career center, an internal call to faculties, a faculty training program, an AI-in-teaching initiative, a community course. The building blocks the committee reads for | submission, criterion, title, description, unit (if specific), years active, is from another ות״ת program (leverage) |
| **Governance** | The institutional set-up for running the program: who leads, the steering committee, how faculty are rewarded | submission, lead person and title, steering body, reward mechanism, description |

## 5. Success measures (KPIs)

Circle: **institution** (own) / **committee** (all). נספח א as rows.

| Model | What it is | Main fields |
| --- | --- | --- |
| **KpiDefinition** (institutional) | A measure the institution adds (2 to 4 of them), beside the mandatory ones from section 2 | submission (null for mandatory), name, explanation, how measured, `is_mandatory=False`, order |
| **KpiValue** | One number for one KPI in one year: the current state or a forecast at submission time, an actual later | kpi definition, participation, academic year, kind: `baseline` / `forecast` / `actual`, value, notes, reported in (submission) |
| **TargetChoice** | Which of the two 20% targets the institution chose to be measured by (programs or students) | participation, basis: `programs` / `students`, total programs, total undergrads, rationale |

The four mandatory KPIs from the reference: programs updated per the
standard, students in updated programs, students with a 100-hour practical
experience, courses taught by faculty tied to the business / public / third
sector, students in community-engagement courses for credit.

## 6. Budget

Circle: **institution** (own) / **committee** (all). נספח ב as rows.

| Model | What it is | Main fields |
| --- | --- | --- |
| **BudgetLine** | One amount: a category in a year, planned or spent | submission, academic year, category: `staff` / `activity` / `infrastructure` / `other`, unit (optional: a faculty the money went to), kind: `planned` / `transferred` / `spent`, amount, notes |
| **Commitment** | The institution's signed undertaking: matching funds (100% of ות״ת's support), and that the budget covers only additions since תשפ"ה | submission, kind, amount, signed by (name, title), signed at, file (SubmittedFile) |
| **CommunityShare** | The share of the ות״ת budget going to academia-community ties, against the required 15% | submission, percent, amount |

## 7. Review, discussion, decision, letter

Circle: **committee**, except the sent letter, which the institution sees.

| Model | What it is | Main fields |
| --- | --- | --- |
| **Analysis** | The committee-side reading of a submission against the criteria: the reference's `programAlignment`. One per submission; written by a committee member or drafted by the AI and then edited | submission, summary, author, drafted by AI (flag), updated at |
| **CriterionFinding** | What the submission does under one criterion, plus strengths and challenges | analysis, criterion, text, kind: `finding` / `strength` / `challenge`, order |
| **Review** | One committee member's review of one submission, following the form | submission, reviewer, status: `in progress` / `done`, started at, done at, overall note |
| **ReviewAnswer** | The reviewer's answer to one review question: the checklist mark, the main points found in the plan, notes for improvement | review, review question, check: `yes` / `partly` / `no` / `n/a`, main points, improvement notes |
| **Discussion** | An internal thread of the committee about a submission (or about the program as a whole) | submission (nullable), title, opened by, opened at |
| **DiscussionPost** | One post in a thread | discussion, author, body (sanitized), posted at, edited at |
| **Decision** | The chair's decision on a submission (spec 2.6.3) | submission, decided by (a chair or the admin), outcome: `approved` / `approved with conditions` / `revise and resubmit` / `declined`, approved amount, conditions, decided at |
| **ResponseLetter** | The committee's letter back. Drafted from the reviews, edited, then sent; the institution's leaders see it only once `sent_at` is set (spec 2.3) | submission, addressee (name, title), status: `draft` / `sent`, drafted by, sent by, sent at, file (the signed PDF, if any) |
| **LetterSection** | One section of the letter: the general comments shared by all letters of the round, then the specific comments to this institution, each as its own section so the general text is one row reused, not pasted 24 times | letter, kind: `general` / `specific` / `closing`, shared text (for general: a `LetterTemplateSection` row), body, order |
| **LetterTemplateSection** | A general-comments section written once per round and used by every letter of that round | program, academic year, title, body, order |

## 8. The public talks back

Circle: **public** for the content, **committee** for handling.

| Model | What it is | Main fields |
| --- | --- | --- |
| **PublicComment** | A signed-in person's comment on an institution's public page or a researcher | author, target (institution / researcher / profile section), body (sanitized), posted at, hidden (by admin) |
| **Like** | One person liked one public thing, once | user, target, at |
| **CorrectionProposal** | "This fact is wrong, here is the right one". Committee members see them; only the admin or a chair accepts, and acceptance applies the change and records who did it (spec 2.6.6) | proposer, target row, field, current value, proposed value, reason, status: `open` / `accepted` / `rejected`, decided by, decided at |

## 9. AI

Circle: the person's own conversations; usage is **committee** (admin).

| Model | What it is | Main fields |
| --- | --- | --- |
| **AiConversation** | One chat: smart search, "discuss my proposal", "help me with my KPIs", "how do I fill in the plan" | user, kind, scope (institution, submission or none), started at, title |
| **AiMessage** | One turn | conversation, role: `user` / `assistant` / `system`, body, cited chunks, model, tokens, cost, at |
| **IndexChunk** | A piece of text the search retrieves over: from a public profile, a guideline, a submitted file's extracted text, a letter, an analysis. **Carries the circle and the institution of its source**, so retrieval filters by what the asker may see before the model ever sees it (spec 1.4) | source row, institution (nullable), circle: `public` / `institution` / `committee`, text, embedding, built at |
| **AiUsage** | Spend per person per day, against a cap in settings | user, date, calls, tokens, cost |

## 10. Audit

| Model | What it is | Main fields |
| --- | --- | --- |
| **ChangeLog** | Who changed what, when, from what to what, on every row in the institution and committee circles and on public facts. The actor is a person in the app or the agent working for Avi from the chat (spec chapter 3) | model, row, field, old, new, by (user), actor_kind: `person` / `agent` / `import`, at, reason (for accepted corrections; for the agent, the source it worked from) |
| **AgentRun** | One piece of work the agent did from the chat: what it was asked, which rows it touched, which sources it used. The admin's trail of the enrichment | started at, finished at, purpose, sources (urls, files), rows touched (count), notes |
| **AccessLog** | Every opening or download of a submitted file or a letter | user, target, action: `view` / `download`, at |

---

## 11. What gets imported on day one, from where

| Reference | Becomes |
| --- | --- |
| `data/institutions.json` and `non_participating_institutions.json` | `Institution` (32), `Participation` (applied or not), `Submission` (proposal) with `SubmittedFile` rows for the listed files, `ContactPerson`, `Analysis` + `CriterionFinding` from `programAlignment` (25 institutions) |
| `documents/proposals/<inst>/data_structured.json`, `data_ai_researchers.csv`, `data_enrollment_*.csv` | `Unit`, `StudyProgram`, `InstitutionMetric`, `Researcher`, `ResearcherMetric`, `ResearcherLink`, `Publication`, `Grant`, `ResearchCenter`, `Collaboration` |
| `research_report.md`, `index.html`, `researchers.html` per institution | `ProfileSection`, `TimelineEvent`, and more `Researcher` rows where the structured files lack them |
| נספח א spreadsheets | `KpiDefinition` (institutional), `KpiValue` (baseline + forecasts), `PlanProgram`, `TargetChoice` |
| נספח ב spreadsheets and budget PDFs | `BudgetLine`, `Commitment`, `CommunityShare` |
| מעקב הגשות 360.xlsx | `Allocation`, submission dates |
| חלוקה לחברי הוועדה ופורמט לבדיקה.xlsx | `Criterion`, `ReviewQuestion` (the form); `CommitteeAttribute(reviewer)` once those people have accounts |
| `documents/responses/<inst>.pdf` | `ResponseLetter` (sent, April 2025) with its file and, where extraction is clean, `LetterSection` rows; one `LetterTemplateSection` set for the general comments |
| `Academia360_Guidelines.md`, `guidelines.html`, `about.html` | `Program`, `GuidelineSection`, `KpiDefinition` (mandatory) |

The import is one-time and idempotent (building_an_app.md, "seeding is
one-time only"): run twice, it changes nothing the second time, and a test
proves it. Where a value could not be extracted cleanly, the row is created
with the file linked and the field left empty for the admin to fill in the
app, not guessed.

## 12. Open questions for Avi

1. **`StudyProgram` vs `PlanProgram`.** I keep the institution's full list of
   degree programs as public knowledge and mark separately which ones the
   plan updates. Right?
2. **Researchers as a public showcase.** The reference's "leading AI
   researchers" are public in this model. Is the AI focus a property of
   Academia 360, or just what the reference happened to collect? (It affects
   whether `Researcher.kind` is about AI or general.)
3. **Analysis authorship.** The reference's `programAlignment` reads as the
   committee's working analysis. I put it in the committee circle. Should
   any of it ever be public, as a neutral summary of what the institution
   plans?
4. **Execution reports.** I modeled every later package (updated plan,
   execution report, annual KPI report) as another `Submission`, reviewed and
   answered the same way. Is that the real cycle, or are reports lighter
   (no letter)?
5. **Leaders submitting.** Can a leader also edit the structured rows (KPI
   values, plan programs, budget lines) in the app, or only upload files and
   let the committee side extract?
6. **One `Decision` per submission** or one per participation (the whole
   application)?
