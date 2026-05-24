import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0007_billing_entitlement"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorporateLead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("company", models.CharField(max_length=150)),
                ("role", models.CharField(blank=True, max_length=100)),
                ("team_size", models.CharField(choices=[("1-5", "1-5"), ("6-15", "6-15"), ("16-50", "16-50"), ("50+", "50+")], max_length=10)),
                ("training_type", models.CharField(choices=[("workshop", "Workshop"), ("bootcamp", "Bootcamp"), ("keynote", "Keynote"), ("not_sure", "Not sure")], max_length=20)),
                ("message", models.TextField(blank=True)),
                ("source_page", models.CharField(default="/corporate/", max_length=100)),
                ("utm_source", models.CharField(blank=True, max_length=100)),
                ("utm_medium", models.CharField(blank=True, max_length=100)),
                ("utm_campaign", models.CharField(blank=True, max_length=100)),
                ("utm_content", models.CharField(blank=True, max_length=100)),
                ("referrer_url", models.URLField(blank=True, max_length=500)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(choices=[("new", "New"), ("contacted", "Contacted"), ("meeting_scheduled", "Meeting Scheduled"), ("proposal_sent", "Proposal Sent"), ("won", "Won"), ("lost", "Lost")], default="new", max_length=30)),
                ("status_changed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
