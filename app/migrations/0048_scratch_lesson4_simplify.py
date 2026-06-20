# -*- coding: utf-8 -*-
"""Simplify lesson 4 of the Scratch course ("איך לשתף פרויקט") to three short
steps + a screenshot of the Share button, instead of the long write-up."""
from django.db import migrations

NOTES = """## איך לשתף פרויקט ב-Scratch

כדי שאחרים יוכלו לראות את הפרויקט שלכם (וכדי להגיש אותו כאן בקורס), צריך לשתף אותו. זה פשוט:

1. **התחברו לחשבון** שלכם ב-Scratch.
2. **כנסו לעמוד הפרויקט** שיצרתם.
3. **לחצו על כפתור «שיתוף»** — הכפתור הכתום שלמעלה.

![כפתור השיתוף ב-Scratch](/static/img/courses/scratch-share.png)

זהו! עכשיו פשוט **העתיקו את הקישור** לפרויקט והדביקו אותו כאן בשיעור — וכולם יוכלו לראות אותו ולשחק בו.
"""


def forward(apps, schema_editor):
    Video = apps.get_model("app", "Video")
    v = Video.objects.filter(course__slug="scratch", lesson_order=4).first()
    if not v:
        return
    fields = []
    if v.bunny_video_id:
        v.bunny_video_id = ""          # keep it an explanation-only lesson
        fields.append("bunny_video_id")
    if (v.notes_markdown or "").strip() != NOTES.strip():
        v.notes_markdown = NOTES
        fields.append("notes_markdown")
    if fields:
        v.save(update_fields=fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0047_scratch_project_course"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
