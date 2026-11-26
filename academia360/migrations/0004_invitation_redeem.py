"""Epic C: an invitation remembers who redeemed it (ownership first,
methodology 55) and carries the leader's title to show."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academia360", "0003_institution_places"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="invitation",
            name="accepted_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="a360_invitations_accepted", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="invitation",
            name="title",
            field=models.CharField(blank=True, max_length=160, help_text="For leaders: the title shown"),
        ),
    ]
