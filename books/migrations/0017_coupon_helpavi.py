"""The one coupon Avi asked for (2026-10-20): "helpavi", 90 days of the 4.99
tier. Created once; editing or switching it off happens in admin."""

from django.db import migrations


def add(apps, schema_editor):
    Coupon = apps.get_model("books", "Coupon")
    Coupon.objects.get_or_create(code="helpavi", defaults={
        "tier": "plus", "days": 90, "is_active": True, "note": "Avi, 2026-10-20: free Plus for 90 days"})


class Migration(migrations.Migration):
    dependencies = [("books", "0016_tiers")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
