"""SPR-M.84, REQ-M.220 - the graduates' two peak days, seeded once.

Lital, 2026-11-17: "יום שיא: 17.12.2026" and "יום שיא לסיום השנה: 24.5.2027".
One-time: if any graduate date already exists (the team may have edited or
removed these), nothing is touched. Owned by the programme's one institution
when there is one, else by nobody (shown to everybody).
"""

import datetime

from django.db import migrations

ROWS = [
    ("יום שיא", datetime.date(2026, 12, 17)),
    ("יום שיא לסיום השנה", datetime.date(2027, 5, 24)),
]


def seed(apps, schema_editor):
    GraduateDate = apps.get_model("matazim", "GraduateDate")
    Institution = apps.get_model("matazim", "Institution")
    if GraduateDate.objects.exists():
        return
    institution = Institution.objects.order_by("created_at").first()
    for title, on in ROWS:
        GraduateDate.objects.create(institution=institution, title=title, on=on)


class Migration(migrations.Migration):
    dependencies = [("matazim", "0049_graduates")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
