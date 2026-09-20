"""Deleting a row deletes its file (Rule 6.8.1).

Django stopped removing files for deleted `FileField` rows in 1.3, for a
good reason (a rolled-back transaction cannot un-delete a file), and the
usual advice is to leave the orphans alone. memz cannot afford that
advice. Every image path in this app already deletes rows -- the player's
own library (ACT-Z.18), the admin bank screen (ACT-Z.17) -- and SPR-W.2
deletes them by design: a photo-booth game writes one file per photo and
is *promised* to delete every one of them at the end. Left alone, a 1 GB
disk shared with the whole site accumulates every photo ever taken at
every party, having told the room they were gone.

So: on a committed delete, the file goes too. `on_commit` is what makes
this safe -- a transaction that rolls back never fires it, so a row that
still exists never loses its bytes. Failures are swallowed on purpose: a
missing or already-deleted file must not turn a successful delete into a
500, and the leak it would leave behind is the exact thing this is here to
avoid, not to trade for an error page.
"""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Meme, MemeImage


def _delete_file_after_commit(field_file):
    if not field_file:
        return
    name = field_file.name
    storage = field_file.storage

    def drop():
        try:
            storage.delete(name)
        except Exception:
            pass

    transaction.on_commit(drop)


@receiver(post_delete, sender=MemeImage, dispatch_uid="memz_image_file_cleanup")
def delete_image_file(sender, instance, **kwargs):
    _delete_file_after_commit(instance.file)


@receiver(post_delete, sender=Meme, dispatch_uid="memz_meme_file_cleanup")
def delete_rendered_meme(sender, instance, **kwargs):
    """A rendered meme is a file too, and the biggest single class of them:
    a five-player, five-round game renders 25. Guest memes are deleted
    after 48 hours (`GUEST_MEME_TTL_HOURS`), which until now deleted 25
    rows and kept 25 JPEGs."""
    _delete_file_after_commit(instance.rendered)
