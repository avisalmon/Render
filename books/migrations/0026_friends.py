import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0025_spine_size")]

    operations = [
        migrations.AlterField(
            model_name="copy", name="visibility",
            field=models.CharField(choices=[("hidden", "only me"), ("private", "friends"), ("public", "public")],
                                   default="private", max_length=8)),
        migrations.AddField(model_name="profile", name="invited_by",
                            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                    related_name="invited", to="books.profile")),
        migrations.AddField(model_name="profile", name="invited_via",
                            field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="profile", name="followers_see_spines",
                            field=models.BooleanField(default=True)),
        migrations.AddField(model_name="notification", name="person",
                            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="+", to="books.profile")),
        migrations.CreateModel(
            name="Invite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=16, unique=True)),
                ("joined", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("inviter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invites",
                                              to="books.profile")),
            ],
        ),
        migrations.CreateModel(
            name="Follow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "pending"), ("accepted", "accepted")],
                                            db_index=True, default="pending", max_length=8)),
                ("source", models.CharField(choices=[("request", "request"), ("invite", "invite"), ("open", "open")],
                                            default="request", max_length=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("follower", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="following",
                                               to="books.profile")),
                ("followee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="followers",
                                               to="books.profile")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("follower", "followee"), name="books_follow_once")]},
        ),
    ]
