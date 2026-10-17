"""Register "Daily news" (avisalmon/daily on GitHub Pages) with a key chosen in advance.

Normally a site is registered in the dashboard and counter generates its key. This one was
needed before Avi could sign in: the site's owner was holding the install instructions with a
placeholder key and asked for the real one. So the key was generated once, handed over at the
same time, and this migration makes it exist in production on the next deploy.

It runs once, like every migration. It touches nothing if the key is already taken (somebody
registered it by hand first), and it does nothing on a database with no superuser to own it,
which is every test database.
"""

from django.conf import settings
from django.db import migrations

KEY = "a67e8d5598"


def create(apps, schema_editor):
    Site = apps.get_model("counter", "Site")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    if Site.objects.filter(key=KEY).exists():
        return
    # Avi's own account, so the site appears on his dashboard (sites are
    # scoped to their owner). The first superuser is the fallback.
    owner = (
        User.objects.filter(email__iexact="avi.salmon@gmail.com", is_superuser=True).first()
        or User.objects.filter(is_superuser=True).order_by("pk").first()
    )
    if owner is None:
        return
    Site.objects.create(
        owner=owner,
        name="Daily news",
        key=KEY,
        base_url="https://avisalmon.github.io/daily/",
        repo="avisalmon/daily",
    )


def remove(apps, schema_editor):
    Site = apps.get_model("counter", "Site")
    Site.objects.filter(key=KEY, name="Daily news").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("counter", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(create, remove)]
