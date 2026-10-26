"""Where a patient's file lands (spec Rule 2.5, 6.4).

X-rays, photos and scanned consents are health records. They go to Google
Cloud Storage under `dentist/<clinic>/`, private, served by signed links
that expire, and never to the server's disk, which is shared by every app
on the site and lost on a bad deploy.

Like CrashTech's storage, this is an indirection that is **built now and
switched on by one environment variable**: until `DENTIST_GCS_BUCKET` is set
and `django-storages[google]` is installed, uploads land on the local disk,
which is fine for development on invented data and not fine for a single
real record. The migration records the callable, not the backend, so the
same code runs on a laptop and in production.

Nothing here runs at import beyond reading settings (building_an_app.md,
mistake 17: a `mkdir` at import time failed a deploy during collectstatic).
"""

import logging

from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def _bucket():
    return getattr(settings, "DENTIST_GCS_BUCKET", "") or ""


def is_remote():
    if not _bucket():
        return False
    try:
        import storages.backends.gcloud  # noqa: F401
    except Exception:
        return False
    return True


def media_storage():
    if not is_remote():
        return default_storage
    from storages.backends.gcloud import GoogleCloudStorage

    return GoogleCloudStorage(
        bucket_name=_bucket(),
        # Every file is private: a signed link that expires is the only way
        # to read one, and the link is made per request for a member of the
        # patient's clinic.
        default_acl="private",
        querystring_auth=True,
        expiration=getattr(settings, "DENTIST_SIGNED_URL_SECONDS", 600),
    )


def upload_path(instance, filename):
    """`dentist/<clinic slug>/<patient id>/<kind>/<name>`: the clinic's own
    folder first, so one clinic's files can be listed, exported and deleted
    without touching another's."""
    import os
    import uuid

    ext = os.path.splitext(filename)[1].lower()[:8]
    patient = getattr(instance, "patient", None)
    clinic = patient.clinic.slug if patient is not None else "unassigned"
    kind = getattr(instance, "kind", "file")
    return f"dentist/{clinic}/{patient.pk if patient else 0}/{kind}/{uuid.uuid4().hex}{ext}"
