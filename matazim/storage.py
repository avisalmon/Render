"""Where a teenager's work is kept.

Spec §4.10, finding P2. Entrance-test uploads used to go straight into
`MEDIA_ROOT` under the name of the file the member chose, and `/media/` is
served with no authentication whatsoever. `settings.py` says so in a comment.

Two separate mistakes were stacked there, and both needed fixing:

**The directory.** Anything under `MEDIA_ROOT` is public by construction, so no
amount of cleverness with filenames would have helped. These files now live on
the persistent disk outside it, and reach a browser only through a view that
checks who is asking.

**The name.** School work is named after the pupil roughly always: `יובל כהן
מודל.stl` is the normal case, not the unlucky one. A path built from that is a
minor's full name in a URL, and a guessable one. Names are now random, and the
original is not kept anywhere, because we have no use for it and it is the part
that identifies a child.
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    """A filesystem store with no public URL, on purpose.

    `base_url` is left unset so that calling `.url` raises rather than quietly
    handing back a path that would 404 in dev and, worse, might one day resolve.
    Everything that needs to serve one of these files goes through
    `matazim:attempt_file`, which is where the permission check lives.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("location", str(settings.MATAZIM_PRIVATE_DIR))
        kwargs.setdefault("base_url", None)
        super().__init__(**kwargs)


private_storage = PrivateStorage()


def entrance_upload_path(instance, filename):
    """A random name, keeping only the extension.

    The extension survives because it is how the measuring code and the browser
    both decide what they are looking at. Nothing else about the original name
    is worth the risk of keeping.
    """
    suffix = Path(filename).suffix.lower()[:10]
    return f"entrance/{uuid.uuid4().hex}{suffix}"


# REQ-M.206 - the kinds of file a browser shows by itself, so a leader can open
# the work on the screen instead of downloading it. Only these: an SVG or an
# HTML file shown inline runs whatever a teenager put in it, on our address.
SHOWN_INLINE = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}
PICTURES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def is_picture(name):
    """True for a file the page can show as a picture."""
    return Path(str(name or "")).suffix.lower() in PICTURES


def file_response(fieldfile, request):
    """REQ-M.206 - hand back a private file, shown in the browser when it can be.

    `?view=1` asks for it on the screen. A picture or a PDF is shown; anything
    else (an STL, a Word file) is still a download, because a browser cannot show
    it and an inline response would only turn into a blank page.
    """
    from django.http import FileResponse

    suffix = Path(fieldfile.name).suffix.lower()
    if request.GET.get("view") and suffix in SHOWN_INLINE:
        return FileResponse(
            fieldfile.open("rb"), as_attachment=False, content_type=SHOWN_INLINE[suffix]
        )
    return FileResponse(fieldfile.open("rb"), as_attachment=True)


def submission_upload_path(instance, filename):
    """REQ-M.122 — the same treatment as an entrance attempt, for the same reason.

    A separate folder rather than a shared one, so that the retention rules can
    differ later without a migration: a failed audition and a piece of work a
    leader gave feedback on are not the same kind of record, and REQ-M.86 will
    eventually want to say so.
    """
    suffix = Path(filename).suffix.lower()[:10]
    return f"submissions/{uuid.uuid4().hex}{suffix}"
