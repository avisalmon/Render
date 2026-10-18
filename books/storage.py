"""Where Books keeps its images (spec BK1 §1.6).

A private Google Cloud Storage bucket of Books' own when one is configured
(ACT-BK.6: `BOOKS_GCS_BUCKET` plus a service-account key limited to that
bucket), else a `books/` folder under MEDIA_ROOT, which is what dev uses
until the bucket exists. Never the web server's disk alone in production:
the bucket is the design, the folder is the fallback and says so in the log.

Personal images (shelf photos, copy photos) are served through short-lived
signed links; covers may be public. `books_storage` is a callable so Django's
migrations serialise the reference, not the instance.
"""

import json
import logging
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

log = logging.getLogger(__name__)
_instance = None


def _build():
    bucket = getattr(settings, "BOOKS_GCS_BUCKET", "")
    if bucket:
        from storages.backends.gcloud import GoogleCloudStorage

        credentials = None
        raw = getattr(settings, "BOOKS_GCS_CREDENTIALS_JSON", "")
        if raw:
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_info(json.loads(raw))
        return GoogleCloudStorage(
            bucket_name=bucket, location="books", credentials=credentials,
            default_acl=None, querystring_auth=True, expiration=timedelta(minutes=10), file_overwrite=False,
        )
    if not settings.DEBUG:
        log.warning("books: BOOKS_GCS_BUCKET is not set; images are on the local disk, which is the dev fallback")
    # No mkdir here: Django calls this while the models load, which on Render
    # happens during the build, before the persistent disk is mounted. The
    # first save creates the folder (broke the BK2 deploy, 2026-10-18).
    root = Path(settings.MEDIA_ROOT) / "books"
    return FileSystemStorage(location=str(root), base_url=f"{settings.MEDIA_URL}books/")


def books_storage():
    global _instance
    if _instance is None:
        _instance = _build()
    return _instance


def reset_for_tests():
    global _instance
    _instance = None


def is_bucket():
    return bool(getattr(settings, "BOOKS_GCS_BUCKET", ""))
