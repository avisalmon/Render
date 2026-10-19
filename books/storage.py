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


_problem = ""


def _credentials(raw):
    """The service-account key from the environment. strict=False lets a key
    whose line breaks were pasted as real newlines still parse."""
    from google.oauth2 import service_account

    info = json.loads(raw.strip(), strict=False)
    return service_account.Credentials.from_service_account_info(info)


def _disk():
    # No mkdir here: Django calls this while the models load, which on Render
    # happens during the build, before the persistent disk is mounted. The
    # first save creates the folder (broke the BK2 deploy, 2026-10-18).
    root = Path(settings.MEDIA_ROOT) / "books"
    return FileSystemStorage(location=str(root), base_url=f"{settings.MEDIA_URL}books/")


def _build():
    """The bucket when it is configured and its key reads; otherwise the disk.
    A bad key must never take the site down (a deploy failed on 2026-10-19
    the day the key was first set): it is logged, shown on the staff check
    page, and Books keeps working on the disk until it is fixed."""
    global _problem
    _problem = ""
    bucket = getattr(settings, "BOOKS_GCS_BUCKET", "")
    if bucket:
        try:
            from storages.backends.gcloud import GoogleCloudStorage

            raw = getattr(settings, "BOOKS_GCS_CREDENTIALS_JSON", "")
            credentials = _credentials(raw) if raw else None
            return GoogleCloudStorage(
                bucket_name=bucket, location="books", credentials=credentials,
                default_acl=None, querystring_auth=True, expiration=timedelta(minutes=10), file_overwrite=False,
            )
        except Exception as exc:  # noqa: BLE001
            _problem = f"{exc.__class__.__name__}: {str(exc)[:200]}"
            log.error("books: the bucket is configured but could not be used, falling back to disk: %s", _problem)
            return _disk()
    if not settings.DEBUG:
        log.warning("books: BOOKS_GCS_BUCKET is not set; images are on the local disk, which is the dev fallback")
    return _disk()


def books_storage():
    global _instance
    if _instance is None:
        _instance = _build()
    return _instance


def reset_for_tests():
    global _instance
    _instance = None


def is_bucket():
    return type(books_storage()).__name__ == "GoogleCloudStorage"


def status():
    st = books_storage()
    return {"backend": type(st).__name__, "bucket": getattr(settings, "BOOKS_GCS_BUCKET", ""),
            "problem": _problem, "key_set": bool(getattr(settings, "BOOKS_GCS_CREDENTIALS_JSON", ""))}
