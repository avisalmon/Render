# The client brief

From ליטל אביב (ראש תחום חינוך חברתי ומובילת תוכנית שבילים, רשת החינוך עתיד),
mail of 2026-08-03, subject "אפיון האתר - תכנית מטצים", forwarded to Avi again
on 2026-09-09.

Her address is `litala@Atid.org.il`; the mail reached Avi's gmail as a forward
on 2026-08-08 and again on 2026-09-09.

Three prototype screens were attached inline (`image011.png`, `image012.png`,
`image013.png`). **They were saved into `prototype/` on 2026-09-09 and read at
full resolution**; `prototype/README.md` is the reading, and the images
themselves are the reference for anything it does not answer. This paragraph
said they had never been read until 2026-10-08, by which point it had been
wrong for a month — worth noting as a doc that outlived its own truth.

**All three screens are the student's site**: דף הבית, הקורסים שלי and
המסלול שלי. She drew no staff screen, so everything behind ניהול is designed
from her written brief and from Avi, not from her drawings.

## Her words

> **מטרת האתר:** להפוך את אתר מטצים ממאגר קורסים ל־מערכת מסודרת שמלווה את
> התלמידים והמובילים לאורך כל התכנית: מתמיינים, לומדים, יוצרים, מדריכים,
> משפיעים.

> **דגש מרכזי:** האתר צריך להיות נקי, פשוט וברור, כך שכל תלמיד יראה מיד: איפה
> אני נמצא, מה כבר השלמתי ומה המשימה הבאה שלי.

Note the framing: there is already a מטצים site that is a **course repository**,
and the job is to turn it into a system that tracks people through a program.
That is the same conclusion this spec reached from the other direction.

## What is on the site, by role

**לתלמידים (the מט״צים themselves)**

- מבחן כניסה בטינקרקאד
- קורסים לפי שלבי התכנית
- העלאת תוצרים
- קבלת משוב ואישור מהמובילים, **ושהתלמיד יוכל לבחור את המוביל שלו**
- מעקב אחר ההתקדמות
- מידע על ימי שיא ופרקטיקום

**למובילי בתי הספר (the teachers)**

- צפייה בכל תלמידי בית הספר
- מעקב אחר ביצוע קורסים
- בדיקת מבחן הכניסה
- אישור תוצרים ומתן משוב
- מעקב אחר פרקטיקום
- דוח התקדמות בית־ספרי

**לצוות התכנית (Avi and Litala)**

- תמונת מצב של כלל בתי הספר
- מעקב לפי תלמיד, בית ספר וקורס
- פתיחת תכנים ומשימות
- אפשרות להכניס תאריכים ליום שיא או עדכון כללי
- אישור תוצרים
- הפקת דוחות ותעודות

## Her site structure (9 sections)

1. דף הבית והסבר על תכנית מטצ״ים
2. המסלול השנתי
3. מבחן הכניסה
4. הקורסים שלי
5. הגשת תוצרים
6. ימי שיא
7. בתי הספר המשתתפים
8. קהילת מט״צים
9. אזור אישי

## What this changes in our spec

| Her ask | Our state | Action |
|---|---|---|
| A student **chooses their own מוביל** | We only had the school leader confirming the student onto a roster. A student picking a mentor is a different relation. | New requirement, see REQ-M.31. Changes the data model. |
| **פרקטיקום** tracked for students and leaders | Not modelled at all. It is the מדריכים stage, the actual teaching, and she wants visibility on it. | New requirement, see REQ-M.32. |
| **בדיקת מבחן הכניסה** by school leaders | We had the entrance test auto-checked only. She wants a human in the loop. | Folded into REQ-M.17. |
| **אישור תוצרים ומתן משוב** by leaders | REQ-M.19 was one thin line. Review plus written feedback is the interaction that matters here. | Expanded, see REQ-M.19. |
| **הפקת תעודות** by staff | We had certification as a status change with nothing printed. | Folded into REQ-M.20. |
| **פתיחת תכנים ומשימות** by staff | Content authoring lives in babook's studio today. Whether program staff get an authoring surface inside מט״צים is undecided. | New open question Q8. |
| Nine named sections | Our REQ-M.5 named four public pages. | REQ-M.5 aligned to her structure. |
| קורסים לפי שלבי התכנית, on the site | Confirms the courses-inside-the-shell decision independently. | No change, good sign. |

## Her terminology, and ours

She writes **תלמידים** for the teenagers and **מובילים** for the adults running
a school. Our docs call the teenagers **מט״צים** and the adults **מובילי בית
ספר** or program staff. Same people, and worth settling on one set of words in
the UI copy before SPR-M.2. Note also that her subject line writes מטצים without
the gershayim; the brand form on the site stays **מט״צים**.

---

## Kickoff mail תשפ״ז (2026-06-25, reached Avi 2026-10-15)

From ליטל אביב to the programme team (Intel's Tal Eshkol and Avi Salmon,
Amir Cain, Atid's שקד פלדי), subject "שבילים משותפים | תכנית מטצים | התנעת
תשפ״ז". Forwarded to Avi on 2026-10-15 by נעמי אושרי (רכזת השתלמויות רשתית,
רשת החינוך עתיד), Litala in Cc, with "the logo and the schedule" attached and
the line "בהמשך לבקשות שלנו באתר החדש של המטצים".

**Avi, 2026-10-15: these are hard requirements from the client and outrank his
own definitions.** They are `spec.md` chapter 0, with the requirement rows in
§5.9. This file keeps her words; the spec keeps what we do about them.

**The model.** לומדים, מתנסים, מובילים, משפיעים. A patrol (סיירת) of about ten
ninth-graders per school; a structured year: screening and acceptance
(Zoom 10.9.2026, a digital TinkerCAD test, a product shown for approval),
leader training 26.10.2026, patrol chosen by mid-November, two Scratch courses
by 2 December, peak day 1 on 17.12.2026 (Scratch products, Intel tour), two 3D
courses December to February, a "good instruction" peak day in February 2027,
the practicum February to May with two elective courses and two practicums
teaching younger students, and a closing peak day on 24.05.2027. Products are
"an inseparable part of the learning": each course ends with an applied product
shown to the school's leaders.

**What she asks of the site ("אתר - תוספות")**

1. The certificate from the site only after the product is submitted to the
   leader.
2. The site more accessible in its order and its content.
3. In the screening test, שקד can see who submitted the product, and there is
   an overview over every school and every student.
4. Updates about changes to the site.
5. Added content.

**Asked of Intel, not of the site.** A mentor per school; online inspiration
sessions led by Intel people; another Zoom to align the stages. Recorded in
`spec.md` chapter 0 so they are not mistaken for missed screens.

**Design.** Naomi's mail brings a new logo, and Avi's instruction is that the
design, styling and colour follow https://atidedu.org.il (REQ-M.188).

**Her typo.** The patrol is chosen "עד 15.11.2027" in one paragraph; the
table, and the rest of the mail, say 2026 (Q24).
