"""Make the Arduino course order explicit in their titles (REQ-7.1.5 / QA-15)."""
from django.db import migrations

OLD = {
    "arduino-tinkercad": "ארדואינו עם טינקרקאד , מבוא לאלקטרוניקה",
    "arduino": "ארדואינו , בקרה וחיישנים",
}


def set_titles(apps, schema_editor):
    from app.content_fixes import renumber_arduino_titles
    renumber_arduino_titles(apps.get_model("app", "Course"))


def revert_titles(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    for slug, title in OLD.items():
        Course.objects.filter(slug=slug).update(title=title)


class Migration(migrations.Migration):
    dependencies = [("app", "0022_cookieconsent")]
    operations = [migrations.RunPython(set_titles, revert_titles)]
