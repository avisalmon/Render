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
