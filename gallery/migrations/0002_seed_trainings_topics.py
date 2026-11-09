"""Day one: Avi's trainings (2026-11-09 interview) and a first list of topics.

One-time seed (methodology: "seeding is one-time only"): a row that exists is
never touched, so Avi's later edits on his own screen survive every deploy.
"""

from django.db import migrations

TRAININGS = [
    ("קורס סמסטריאלי בטכניון", "Technion semester course"),
    ("אינטל, מפגש אורח חודשי, אוקטובר 2026", "Intel monthly guest session, October 2026"),
    ("אינטל, מפגש אורח חודשי, נובמבר 2026", "Intel monthly guest session, November 2026"),
    ("אינטל, מפגש אורח חודשי, דצמבר 2026", "Intel monthly guest session, December 2026"),
    ("טכניון, מפגש מעשי של 3 שעות, יום חמישי 12.11.2026",
     "Technion hands-on session, 3 hours, Thursday 12 November 2026"),
]

TOPICS = [
    ("frontend", "פרונטאנד", "Frontend"),
    ("full-stack", "פולסטאק", "Full stack"),
    ("backend", "בקאנד ו-API", "Backend and APIs"),
    ("ai", "בינה מלאכותית", "AI"),
    ("automation", "אוטומציה", "Automation"),
    ("data", "נתונים", "Data"),
    ("office", "אופיס: אקסל, וורד, פאוורפוינט", "Office: Excel, Word, PowerPoint"),
    ("hardware", "חומרה ומיקרו-בקרים", "Hardware and microcontrollers"),
    ("devops", "גיט ו-DevOps", "Git and DevOps"),
    ("games", "משחקים", "Games"),
    ("education", "הוראה ולמידה", "Teaching and learning"),
    ("productivity", "פרודוקטיביות", "Productivity"),
]


def seed(apps, schema_editor):
    Training = apps.get_model("gallery", "Training")
    Topic = apps.get_model("gallery", "Topic")
    for i, (he, en) in enumerate(TRAININGS):
        if not Training.objects.filter(name_en=en).exists():
            Training.objects.create(name_he=he, name_en=en, position=(i + 1) * 10)
    for i, (slug, he, en) in enumerate(TOPICS):
        if not Topic.objects.filter(slug=slug).exists():
            Topic.objects.create(slug=slug, name_he=he, name_en=en, position=(i + 1) * 10)


class Migration(migrations.Migration):
    dependencies = [("gallery", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
