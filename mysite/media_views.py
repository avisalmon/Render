"""Serving /media/ (security review, 2026-10-24).

Everything under MEDIA_ROOT used to be handed out to anyone who knew the
path, in production too. Most of it is public by nature (covers, avatars,
blog pictures, memes). Some of it is not: a family's trip photos, course
materials that only an enrolled person may download, hackathon submissions,
a learner's own note pictures. Those folders are refused here, and each app
hands its own files out through a view that checks who is asking.
"""

from django.conf import settings
from django.http import Http404
from django.views.static import serve

# The first folder of a media path; anything under these never comes out of here.
PRIVATE_MEDIA_PREFIXES = (
    "ustrip/",
    "crashtech/submissions/",
    "crashtech/videos/",
    "crashtech/code/",
    "course_materials/",
    "entrance_tests/",
    "notes/",
)


def is_private(path):
    path = (path or "").lstrip("/")
    return any(path.startswith(prefix) for prefix in PRIVATE_MEDIA_PREFIXES)


def protected_serve(request, path):
    if is_private(path):
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT)
