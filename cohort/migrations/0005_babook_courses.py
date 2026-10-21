"""The babook courses Avi listed for the course on 2026-10-21, in his order.
Once per database, like 0002 and 0004. Each address was opened on the live
site first. "Co-Coding: לפתח עם GitHub Copilot" was on his list too and is left
out: it is hidden on babook (404), replaced by מהנדס x10."""

from datetime import timedelta

from django.db import migrations
from django.utils import timezone

ITEMS = [
    ("טינקרקאד, מבוא לתכנון תלת-מימד", "תכנון תלת-מימד ראשון, בדפדפן ובלי התקנה.", "tinkercad"),
    ("Fusion 360, תכנון תלת-מימד מתקדם", "תכנון תלת-מימד מקצועי: שרטוטים, הרכבות והכנה להדפסה.", "fusion360"),
    ("פייתון, מבוא לתכנות", "צעדים ראשונים בתכנות, בשפה שמאחורי רוב כלי הבינה המלאכותית.", "python"),
    ("מיקרופייתון עם תוני", "מתכנתים בקרים וחיישנים בפייתון, בסביבת Thonny.", "micropython-thonny"),
    ("ארגונים אקספוננציאליים", "ארגונים שצומחים בקצב מעריכי, ומה אפשר ללמוד מהם על מערכת החינוך.", "exponential-organizations"),
    ("להוביל חדשנות: מייקרים, מוטיבציה וכישורים", "איך מובילים חדשנות בבית הספר: תרבות מייקרים, מוטיבציה וכישורים.", "leading-innovation"),
    ("סדנת רעיונאות: Future Press Release", "כותבים את הודעת העיתונות של העתיד, ובונים ממנה את הרעיון אחורה.", "press-ideation"),
]


def add(apps, schema_editor):
    Material = apps.get_model("cohort", "Material")
    User = apps.get_model("auth", "User")
    avi = User.objects.filter(is_superuser=True).order_by("id").first()
    last = Material.objects.order_by("-created_at").values_list("created_at", flat=True).first()
    start = max(timezone.now(), last + timedelta(seconds=1)) if last else timezone.now()
    for i, (title, line, slug) in enumerate(ITEMS):
        url = f"https://babook.co.il/courses/{slug}/"
        if Material.objects.filter(url=url).exists():
            continue
        Material.objects.create(kind="course", title=title, line=line, url=url,
                                created_at=start + timedelta(seconds=i), created_by=avi)


def remove(apps, schema_editor):
    Material = apps.get_model("cohort", "Material")
    Material.objects.filter(url__in=[f"https://babook.co.il/courses/{s}/" for _t, _l, s in ITEMS]).delete()


class Migration(migrations.Migration):
    dependencies = [("cohort", "0004_avi_materials")]
    operations = [migrations.RunPython(add, remove)]
