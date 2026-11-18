"""SPR-M.89, REQ-M.228 - the students' year path starts with מפגש 1, seeded once.

Lital, 2026-11-18 12:29: on the grade 9 students' path she does not see מפגש 1.
One-time: if any student meeting already exists, nothing is touched. Owned by the
programme's one institution when there is one, else by nobody (shown to all).
"""

from django.db import migrations


def seed(apps, schema_editor):
    StudentMeeting = apps.get_model("matazim", "StudentMeeting")
    Institution = apps.get_model("matazim", "Institution")
    if StudentMeeting.objects.exists():
        return
    institution = Institution.objects.order_by("created_at").first()
    StudentMeeting.objects.create(institution=institution, number=1, title="היכרות עם התכנית")


class Migration(migrations.Migration):
    dependencies = [("matazim", "0053_student_track")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
