"""Rename `MemberProfile.is_admin` to `is_program_manager`.

Spec §4.3, settled with Avi on 2026-09-11. "admin" pointed at root in
conversation and at the program manager on screen, an ambiguity that had already
produced one wrong grant of superuser. The Hebrew label was right all along;
only the English was lying.

**Written by hand on purpose.** `makemigrations` asks interactively whether a
removed field and an added field are the same field, and answering wrong, or
letting `--no-input` answer for you, produces a `RemoveField` plus an `AddField`.
That pair is not a rename: it drops the column and creates a new one with the
default, which in production would silently strip נעמי of the role on the next
deploy and leave nobody able to grant it back except through Django admin.

A `RenameField` carries the data across. Reversible, because nothing about this
is destructive in either direction.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("matazim", "0009_retentionrun")]

    operations = [
        migrations.RenameField(
            model_name="memberprofile",
            old_name="is_admin",
            new_name="is_program_manager",
        ),
    ]
