"""A first shelf of course materials, asked for by Avi on 2026-10-21.

A migration rather than the start-up seed on purpose: it runs exactly once per
database, so a material Avi edits or deletes on the site is never put back by a
later deploy. Every link was checked before it was written here (the YouTube
titles through YouTube's oEmbed, the babook courses on the live site), and an
item whose link is already on the shelf is skipped.
"""

from datetime import timedelta

from django.db import migrations
from django.utils import timezone

ITEMS = [
    ("course", "מסע ה-AI: נסו הכל בעצמכם",
     "נקודת ההתחלה: מתנסים בעצמכם בכלי הבינה המלאכותית המרכזיים, צעד אחר צעד. הדרכה במערכת babook.",
     "https://babook.co.il/courses/ai-user-journey/", ""),
    ("video", "מודלי שפה גדולים, בקצרה",
     "שבע דקות של 3Blue1Brown: מה זה מודל שפה גדול ואיך הוא לומד. באנגלית.",
     "https://www.youtube.com/watch?v=LPZh9BOjkQs", "LPZh9BOjkQs"),
    ("video", "מבוא למודלי שפה גדולים",
     "הרצאה של שעה מאנדריי קרפתי: איך מודלי שפה עובדים, איך מאמנים אותם, ולאן זה הולך. באנגלית.",
     "https://www.youtube.com/watch?v=zjkBMFhNj_g", "zjkBMFhNj_g"),
    ("video", "מה זו רשת נוירונים?",
     "הבסיס של למידה עמוקה, דרך זיהוי ספרות בכתב יד. הפרק הראשון בסדרה של 3Blue1Brown. באנגלית.",
     "https://www.youtube.com/watch?v=aircAruvnKk", "aircAruvnKk"),
    ("video", "טרנספורמרים: הטכנולוגיה שמאחורי מודלי השפה",
     "הארכיטקטורה שמאחורי ChatGPT וחבריו, מוסברת בציורים. פרק 5 בסדרה של 3Blue1Brown. באנגלית.",
     "https://www.youtube.com/watch?v=wjZofJX0v4M", "wjZofJX0v4M"),
    ("course", "מהנדס x10: להיות מהנדס פי עשרה עם AI",
     "השלב הבא: לבנות דברים אמיתיים עם בינה מלאכותית, כמו שעשיתם בפרויקט האתר. הדרכה במערכת babook.",
     "https://babook.co.il/courses/engineer-x10/", ""),
]


def add(apps, schema_editor):
    Material = apps.get_model("cohort", "Material")
    User = apps.get_model("auth", "User")
    avi = User.objects.filter(is_superuser=True).order_by("id").first()
    start = timezone.now()
    for i, (kind, title, line, url, yt) in enumerate(ITEMS):
        if Material.objects.filter(url=url).exists():
            continue
        Material.objects.create(kind=kind, title=title, line=line, url=url, youtube_id=yt,
                                created_at=start + timedelta(seconds=i), created_by=avi)


def remove(apps, schema_editor):
    Material = apps.get_model("cohort", "Material")
    Material.objects.filter(url__in=[item[3] for item in ITEMS]).delete()


class Migration(migrations.Migration):
    dependencies = [("cohort", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(add, remove)]
