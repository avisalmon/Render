"""REQ-M.186 - the ten milestones of תשפ״ז, seeded once.

Atid's kickoff mail (ליטל אביב, 2026-06-25; forwarded by נעמי אושרי on
2026-10-15) carries a table of the year's milestones. This writes it into the
database for every institution that has none yet, and never touches one that
already has rows: after the first run the database is the only source, so a
program manager's edit is never overwritten by a later deploy (Rule 1, and the
seeding rule in docs/building_an_app.md).

The data is inlined here rather than imported from app code, so the migration
means the same thing on the day the app's code has moved on.
"""

import datetime

from django.db import migrations

D = datetime.date

ROWS = [
    (1, "10.9.2026", D(2026, 9, 10), None, "screening", "זום חשיפה",
     "הצגת התכנית לבתי הספר, פתיחת תהליך המיון והשקת המבחן הדיגיטלי.", False),
    (2, "אוקטובר 2026", D(2026, 10, 1), D(2026, 10, 31), "screening", "מבחן כניסה",
     "מבחן דיגיטלי בטינקרקאד והצגת תוצר לצורך קבלה לתכנית.", False),
    (3, "26.10.2026", D(2026, 10, 26), None, "training", "הכשרת מובילים",
     "הכשרת מובילי התכנית, הצגת המודל השנתי, תהליך הליווי ודרכי העבודה.", False),
    (4, "עד אמצע נובמבר 2026", D(2026, 10, 26), D(2026, 11, 15), "recruiting", "גיוס תלמידים",
     "בחירת סיירת של כ-10 תלמידים בכל בית ספר.", False),
    (5, "נובמבר-דצמבר 2026", D(2026, 11, 1), D(2026, 12, 16), "learning", "למידה עצמאית",
     "שתי הדרכות Scratch והכנת תוצר ראשון.", False),
    (6, "17.12.2026", D(2026, 12, 17), None, "peak", "יום שיא 1",
     "הצגת תוצרי Scratch, מפגש בין הסיירות, סיור באינטל וחשיפה לעולם החדשנות.", True),
    (7, "דצמבר-פברואר", D(2026, 12, 18), D(2027, 2, 28), "learning", "למידה עצמאית",
     "שתי הדרכות תלת־ממד והכנת תוצר.", False),
    (8, "פברואר 2027", D(2027, 2, 1), D(2027, 2, 28), "peak", "יום שיא: הדרכה טובה",
     "פיתוח מיומנויות הדרכה, עמידה מול קהל והכנה לפרקטיקום.", True),
    (9, "פברואר-מאי 2027", D(2027, 2, 15), D(2027, 5, 23), "practicum", "פרקטיקום",
     "שתי הדרכות בחירה והכנת תוצרים, שני פרקטיקומים והובלת תלמידים צעירים.", False),
    (10, "24.05.2027", D(2027, 5, 24), None, "peak", "יום שיא מסכם",
     "הצגת תוצרים, שיתוף תהליכים, הרצאות AI, הוקרה וסיכום התכנית.", True),
]


def seed(apps, schema_editor):
    Institution = apps.get_model("matazim", "Institution")
    ProgramMilestone = apps.get_model("matazim", "ProgramMilestone")
    for institution in Institution.objects.all():
        if ProgramMilestone.objects.filter(institution=institution).exists():
            continue
        for order, when_text, starts_on, ends_on, stage, title, activities, peak in ROWS:
            ProgramMilestone.objects.create(
                institution=institution, order=order, when_text=when_text,
                starts_on=starts_on, ends_on=ends_on, stage=stage, title=title,
                activities=activities, is_peak_day=peak,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("matazim", "0039_program_milestone"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
