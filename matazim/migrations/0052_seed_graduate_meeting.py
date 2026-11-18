"""SPR-M.88, REQ-M.226 - the graduates' yearly track starts with מפגש 1, seeded once.

Lital, 2026-11-18: "תוסיף במסלול השנתי מפגש 1 – היכרות עם התכנית". One-time:
if any meeting already exists (the team may have edited or removed it), nothing
is touched. Owned by the programme's one institution when there is one, else by
nobody (shown to everybody), like the peak days (0050).
"""

from django.db import migrations


def seed(apps, schema_editor):
    GraduateMeeting = apps.get_model("matazim", "GraduateMeeting")
    Institution = apps.get_model("matazim", "Institution")
    if GraduateMeeting.objects.exists():
        return
    institution = Institution.objects.order_by("created_at").first()
    GraduateMeeting.objects.create(institution=institution, number=1, title="היכרות עם התכנית")


class Migration(migrations.Migration):
    dependencies = [("matazim", "0051_graduate_track")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
