"""Materials Avi asked for on 2026-10-21: his AI education policy compass and
three of his talks. Once per database, like 0002, so nothing he edits or
deletes on the site comes back. Every link checked first: the compass on the
live blog, the videos through YouTube (the first is unlisted and embeddable)."""

from datetime import timedelta

from django.db import migrations
from django.utils import timezone

ITEMS = [
    ("link", "מצפן למדיניות חינוך לבינה מלאכותית",
     "שלוש רמות של ידע, אחריות ושפה משותפת: מסגרת לחינוך, להכשרה וליישום מושכל של בינה מלאכותית, מאת אבי סלמון.",
     "https://babook.co.il/blog/ai-education-compass/", ""),
    ("video", "מהנדס x10: ההרצאה",
     "ההרצאה של אבי סלמון על עבודה של מהנדס עם בינה מלאכותית.",
     "https://youtu.be/eQdYIxiAw4E", "eQdYIxiAw4E"),
    ("video", "The Art of co-coding #1",
     "אבי סלמון ב-Tech Tal: האמנות של לכתוב קוד יחד עם בינה מלאכותית.",
     "https://youtu.be/iMrC16J-LaQ", "iMrC16J-LaQ"),
    ("video", "AI and I",
     "הרצאה של אבי סלמון: הבינה המלאכותית ואני.",
     "https://youtu.be/Lqd2Sa8TkC8", "Lqd2Sa8TkC8"),
]


def add(apps, schema_editor):
    Material = apps.get_model("cohort", "Material")
    User = apps.get_model("auth", "User")
    avi = User.objects.filter(is_superuser=True).order_by("id").first()
    last = Material.objects.order_by("-created_at").values_list("created_at", flat=True).first()
    start = max(timezone.now(), last + timedelta(seconds=1)) if last else timezone.now()
    for i, (kind, title, line, url, yt) in enumerate(ITEMS):
        if Material.objects.filter(url=url).exists():
            continue
        Material.objects.create(kind=kind, title=title, line=line, url=url, youtube_id=yt,
                                created_at=start + timedelta(seconds=i), created_by=avi)


def remove(apps, schema_editor):
    Material = apps.get_model("cohort", "Material")
    Material.objects.filter(url__in=[item[3] for item in ITEMS]).delete()


class Migration(migrations.Migration):
    dependencies = [("cohort", "0003_material_link_kind")]
    operations = [migrations.RunPython(add, remove)]
