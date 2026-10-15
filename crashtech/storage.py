"""Where a user's file actually lands (spec Rule 9.5).

**This is the one piece of SPR-C.6 that is built and not switched on**, and
it is deliberate rather than forgotten.

The rule says no user upload touches the application disk. The arithmetic
behind it: one event produces roughly 26 GB of phone video (already solved
by making video a link with no upload path at all) plus several gigabytes
of photographs and artifacts, against a 1 GB Render disk shared by every
app on the site. Museum photographs are also permanent and public, so they
are exactly the files that must not live somewhere a redeploy can lose.

Switching it on takes three things, none of which this session can do:

1. `crashtech-media`, a bucket of its own, separate from the backups
   bucket so the blast radius of a mistake stays inside one product.
2. `django-storages[google]` in `requirements.txt`.
3. `CRASHTECH_GCS_BUCKET` set in the Render environment.

Until all three exist, `media_storage()` returns Django's default, which
is the local disk, and uploads work normally for development and for a
demo. The indirection is here now so that turning it on later is an
environment variable rather than a migration.
"""

import logging

from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def _bucket():
    return getattr(settings, "CRASHTECH_GCS_BUCKET", "") or ""


def is_remote():
    """Whether user uploads are actually leaving the application disk."""
    if not _bucket():
        return False
    try:
        import storages.backends.gcloud  # noqa: F401
    except Exception:
        return False
    return True


def media_storage():
    """The storage for every CrashTech user upload.

    A callable rather than an instance, because Django evaluates it at
    runtime: the same code then works on a laptop with no bucket and in
    production with one, and no migration records which was in force.
    """
    if not is_remote():
        return default_storage

    from storages.backends.gcloud import GoogleCloudStorage

    return GoogleCloudStorage(
        bucket_name=_bucket(),
        # Museum photographs are public and permanent by design (Rule 9.1,
        # 9.2); submission artifacts are not, and get signed URLs. Keeping
        # one bucket with per-object ACLs rather than two is a deliberate
        # simplification, and the reason the bucket is CrashTech's own.
        default_acl=None,
        querystring_auth=True,
    )


def warn_if_local():
    """Called once at startup, so that running on the disk in production is
    visible rather than something somebody discovers when it fills."""
    if not is_remote() and not settings.DEBUG:
        logger.warning(
            "crashtech: user uploads are going to the application disk. "
            "Rule 9.5 wants CRASHTECH_GCS_BUCKET and django-storages[google].",
        )
