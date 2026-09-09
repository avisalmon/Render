# The client brief

From ליטל אביב (ראש תחום חינוך חברתי ומובילת תוכנית שבילים, רשת החינוך עתיד),
mail of 2026-08-03, subject "אפיון האתר - תכנית מטצים", forwarded to Avi again
on 2026-09-09.

Three prototype screens were attached inline (`image011.png`, `image012.png`,
`image013.png`). **They have not been read yet.** The Gmail tooling returns
attachment metadata only, so they need saving into `prototype/` by hand. Until
then, every layout decision in `spec.md` is ours rather than hers.

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
