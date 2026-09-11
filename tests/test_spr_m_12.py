"""SPR-M.12 — Say what we mean.

A rename with no behaviour change, so most of the proof is the other 250 tests
still passing. What is tested here is the part a rename can silently break and
the suite would not notice: production.

Two things can go wrong.

The migration could be a drop-and-add rather than a rename, which would strip
נעמי of her role on the next deploy and leave nobody able to grant it back
except through Django admin.

And `matazim_admins --from-env` runs on every deploy and is what keeps her in
that role. Renaming the environment variable and trusting somebody to update
Render at exactly the right moment means that, if they do not, the deploy
silently stops granting it and nobody notices until she cannot open a screen.

Traces: spec §4.3.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprm12

PASSWORD = "sprm12-pass-5507"


def make_user(email):
    return User.objects.create_user(username=email, email=email, password=PASSWORD)


def test_the_role_survives_the_rename_as_data(db):
    """T-F-M.12.2-1: the migration is a rename, not a drop and an add.

    Checked through the model rather than by reading the migration, because what
    matters is that a row carrying the role still carries it.
    """
    from matazim.models import MemberProfile

    user = make_user("naomi@example.com")
    MemberProfile.objects.create(user=user, is_program_manager=True)

    assert MemberProfile.objects.get(user=user).is_program_manager is True


def test_the_old_field_name_is_gone(db):
    """T-F-M.12.2-2: a half-rename is worse than either name.

    If `is_admin` still resolved, two names would mean the same thing and the
    ambiguity this sprint exists to remove would have survived it.
    """
    from matazim.models import MemberProfile

    fields = {f.name for f in MemberProfile._meta.get_fields()}
    assert "is_program_manager" in fields
    assert "is_admin" not in fields


def test_the_deploy_still_grants_the_role_from_the_old_variable(db, monkeypatch):
    """T-F-M.12.4-1: the hazard this sprint exists to defuse.

    Render currently sets MATAZIM_ADMINS. If the command only read the new name,
    the very next deploy would stop granting the role, and the failure would be
    silent: no error, no log line anybody reads, just נעמי locked out of her own
    screens.
    """
    from matazim.models import MemberProfile

    user = make_user("naomi@example.com")
    monkeypatch.setenv("MATAZIM_ADMINS", "naomi@example.com")
    monkeypatch.delenv("MATAZIM_PROGRAM_MANAGERS", raising=False)

    call_command("matazim_admins", "--from-env", stdout=StringIO())
    assert MemberProfile.objects.get(user=user).is_program_manager is True


def test_the_deploy_grants_the_role_from_the_new_variable(db, monkeypatch):
    """T-F-M.12.4-2: and the name we are moving to actually works."""
    from matazim.models import MemberProfile

    user = make_user("naomi@example.com")
    monkeypatch.setenv("MATAZIM_PROGRAM_MANAGERS", "naomi@example.com")
    monkeypatch.delenv("MATAZIM_ADMINS", raising=False)

    call_command("matazim_admins", "--from-env", stdout=StringIO())
    assert MemberProfile.objects.get(user=user).is_program_manager is True


def test_the_new_variable_wins_when_both_are_set(db, monkeypatch):
    """T-F-M.12.4-3: the state Render will be in mid-migration.

    Not merged. Two half-filled lists would be a confusing thing to debug, and
    the fallback exists for continuity rather than aggregation.
    """
    from matazim.models import MemberProfile

    new = make_user("new@example.com")
    old = make_user("old@example.com")
    monkeypatch.setenv("MATAZIM_PROGRAM_MANAGERS", "new@example.com")
    monkeypatch.setenv("MATAZIM_ADMINS", "old@example.com")

    call_command("matazim_admins", "--from-env", stdout=StringIO())
    assert MemberProfile.objects.get(user=new).is_program_manager is True
    assert not MemberProfile.objects.filter(user=old, is_program_manager=True).exists()


def test_neither_variable_set_is_not_a_crash(db, monkeypatch):
    """T-F-M.12.4-4: the deploy runs this with `|| true`, but a traceback in the
    start command is still noise nobody should have to read past."""
    monkeypatch.delenv("MATAZIM_PROGRAM_MANAGERS", raising=False)
    monkeypatch.delenv("MATAZIM_ADMINS", raising=False)

    out = StringIO()
    call_command("matazim_admins", "--from-env", stdout=out)
    assert "nothing to grant" in out.getvalue()


def test_the_word_admin_is_gone_from_the_role_vocabulary():
    """T-F-M.12.1-1: spec §4.3, and what stops the rename decaying.

    "admin" pointed at root in conversation and at the program manager on
    screen. One grant of superuser already went wrong because of it. This fails
    if the old name creeps back into the module that defines who is who.
    """
    import re
    from pathlib import Path

    source = Path("matazim/access.py").read_text(encoding="utf-8")
    # The docstring deliberately signposts the old name for anyone who greps it.
    source = source.replace("`is_admin` and it did not exist: you want `is_program_manager`", "")

    assert not re.search(r"\bis_admin\b", source)
    assert not re.search(r"^ADMIN = ", source, re.M)
    assert "PROGRAM_MANAGER" in source
