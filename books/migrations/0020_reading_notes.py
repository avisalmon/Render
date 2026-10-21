import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0019_scan_is_single")]

    operations = [
        migrations.CreateModel(
            name="ReadingNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("page", models.PositiveIntegerField(blank=True, null=True)),
                ("body", models.TextField(max_length=2000)),
                ("source", models.CharField(choices=[("typed", "typed"), ("voice", "voice")], default="typed",
                                            max_length=6)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notes",
                                            to="books.catalogentry")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="reading_notes", to="books.profile")),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                              related_name="notes", to="books.readingsession")),
            ],
            options={"ordering": ["created_at"],
                     "indexes": [models.Index(fields=["profile", "entry"], name="books_note_profile_entry")]},
        ),
    ]
