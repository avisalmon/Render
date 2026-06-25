"""Python course: wire the real GitHub repo (avisalmon/PythonPath) into lesson 5
("היכן להוריד את הקבצים") - as a course material AND in the lesson text (replacing
the placeholder repo URL, plus a concrete ZIP-download step). Idempotent."""
from django.db import migrations

REPO = "https://github.com/avisalmon/PythonPath"
MATERIAL_TITLE = "קבצי הקורס ב-GitHub"


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    CourseMaterial = apps.get_model("app", "CourseMaterial")
    try:
        course = Course.objects.get(slug="python")
    except Course.DoesNotExist:
        return

    # 1) Course material (shows on the course page + every lesson page).
    CourseMaterial.objects.update_or_create(
        course=course, title=MATERIAL_TITLE,
        defaults={"material_type": "link", "url": REPO, "order": 0},
    )

    # 2) Lesson 5 text: real clone URL + a concrete ZIP step.
    v = course.videos.filter(lesson_order=5).first()
    if not v or not v.notes_markdown:
        return
    n = v.notes_markdown
    n = n.replace("https://github.com/YourUsername/YourRepository.git", REPO + ".git")
    n = n.replace(
        "החליפו את ה-URL בכתובת של הריפוזיטורי של הקורס",
        "זהו הריפוזיטורי של הקורס: " + REPO,
    )
    if "הורדת הקבצים כקובץ ZIP" not in n and "#### הורדת הקבצים באמצעות Git" in n:
        zip_block = (
            "#### הורדת הקבצים כקובץ ZIP\n\n"
            "1. היכנסו לריפוזיטורי של הקורס: " + REPO + "\n"
            "2. לחצו על הכפתור הירוק **Code** ואז על **Download ZIP**.\n"
            "3. חלצו את הקובץ למחשב - וכל קבצי הקורס אצלכם.\n\n"
        )
        n = n.replace(
            "#### הורדת הקבצים באמצעות Git",
            zip_block + "#### הורדת הקבצים באמצעות Git", 1,
        )
    if n != v.notes_markdown:
        v.notes_markdown = n
        v.save(update_fields=["notes_markdown"])


def backwards(apps, schema_editor):
    CourseMaterial = apps.get_model("app", "CourseMaterial")
    CourseMaterial.objects.filter(
        course__slug="python", title=MATERIAL_TITLE).delete()


class Migration(migrations.Migration):
    dependencies = [("app", "0065_alter_userprofile_is_public")]
    operations = [migrations.RunPython(forwards, backwards)]
