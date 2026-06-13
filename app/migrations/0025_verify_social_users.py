"""Backfill: mark users who signed in via a social provider (Google/GitHub)
as email-verified (REQ-7.2.1). Their email is already verified by the provider,
so they should never see the verify-email nudge."""
from django.db import migrations


def verify_social_users(apps, schema_editor):
    UserProfile = apps.get_model("app", "UserProfile")
    try:
        SocialAccount = apps.get_model("socialaccount", "SocialAccount")
    except LookupError:
        return
    social_user_ids = set(SocialAccount.objects.values_list("user_id", flat=True))
    if social_user_ids:
        UserProfile.objects.filter(
            user_id__in=social_user_ids, email_verified=False
        ).update(email_verified=True)


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0024_userprofile_email_verified_and_more"),
        ("socialaccount", "0001_initial"),
    ]
    operations = [migrations.RunPython(verify_social_users, migrations.RunPython.noop)]
