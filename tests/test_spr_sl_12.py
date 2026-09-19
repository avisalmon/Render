"""SL-D1 — SensorLab: an attempt, and who is allowed to see one.

See docs/sensorlab/backlog.md (SL-D1), spec §9.4, data_model.md §5.

`LabAttempt` is the spine of Epics D through H: predictions, recordings,
notebook entries and results all hang off it. It is also the first table in
this app holding a *person's own work* rather than authored content, which
changes what the tests have to be about. Nobody is harmed by a curriculum
row leaking; a student's attempt is theirs.

So three of these are boundaries, not plumbing:

* **Deleting a lab must not erase history.** `PROTECT`, not `CASCADE`. An
  author tidying up an old lab in the admin should be stopped, not quietly
  obeyed — the rows it would take with it are students' work and there is no
  undo.

* **An attempt resolves from the session, never from a URL.** The same rule
  `profile/me/` and the consent endpoint already follow: if no route takes
  an id, no route can be walked.

* **A share link is off until it is on.** `is_public` and `share_slug` are
  two different facts, and holding the slug is not permission. Generating
  the slug at creation is convenient and would quietly mean every attempt
  ever made is one guessed URL from public if the flag is ever mis-read.

And two decisions SL-D1 was asked to settle rather than inherit — re-running
a finished lab, and what a stored `current_step` means once the flow can
grow a step. Both are recorded in the backlog; the tests below are what make
them true.
"""

import pytest

pytestmark = [pytest.mark.sprsl12, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _user(django_user_model, name="ada"):
    return django_user_model.objects.create_user(name, password=PASSWORD)


def _lab():
    from sensorlab.models import Lab

    _seed()
    return Lab.objects.get(slug="measuring-g")


# ----------------------------------------------------------- it exists


def test_starting_a_lab_creates_an_attempt_on_its_first_step():
    from django.contrib.auth import get_user_model

    from sensorlab.models import LAB_STEPS, LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)

    attempt = LabAttempt.objects.start(user=user, lab=lab)
    assert attempt.status == LabAttempt.Status.IN_PROGRESS
    assert attempt.current_step == LAB_STEPS[0]
    assert attempt.started_at is not None
    assert attempt.completed_at is None


def test_an_attempt_walks_the_flow_in_the_models_own_order():
    """`LAB_STEPS`, not a sequence written again here. SL-B4 made that the
    one definition; an attempt that advanced by its own list would be the
    third copy and the first to disagree."""
    from django.contrib.auth import get_user_model

    from sensorlab.models import LAB_STEPS, LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=lab)

    walked = [attempt.current_step]
    while attempt.advance():
        walked.append(attempt.current_step)

    assert walked == list(LAB_STEPS)
    assert attempt.status == LabAttempt.Status.COMPLETED
    assert attempt.completed_at is not None


def test_advancing_past_the_end_does_not_move_or_re_complete():
    from django.contrib.auth import get_user_model

    from sensorlab.models import LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=lab)
    while attempt.advance():
        pass

    finished_at = attempt.completed_at
    assert attempt.advance() is False
    attempt.refresh_from_db()
    assert attempt.completed_at == finished_at


# -------------------------------------------- history outlives the content


def test_deleting_a_lab_with_history_is_refused():
    """`PROTECT`, not `CASCADE`.

    An author tidying an old lab out of the admin would otherwise take every
    student's run of it with them, with no warning and no undo. Being
    stopped is the correct answer; if a lab really must go, its attempts are
    a decision somebody makes explicitly.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import ProtectedError

    from sensorlab.models import LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    LabAttempt.objects.start(user=user, lab=lab)

    with pytest.raises(ProtectedError):
        lab.delete()


def test_deleting_the_person_does_take_their_attempts():
    """The opposite call, and deliberately so. A lab is the institution's;
    an attempt is the person's, and account deletion should mean it."""
    from django.contrib.auth import get_user_model

    from sensorlab.models import LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    LabAttempt.objects.start(user=user, lab=lab)

    user.delete()
    assert LabAttempt.objects.count() == 0


# ------------------------------------------------- re-run or resume (D.1)


def test_starting_a_lab_you_are_midway_through_resumes_it():
    """The decision SL-D1 was asked to settle, half one.

    Unfinished work is resumed, never duplicated. Two half-done attempts at
    the same lab is a state nothing downstream knows how to read — which of
    them owns the prediction? — so it is prevented here rather than
    tolerated and disambiguated later.
    """
    from django.contrib.auth import get_user_model

    from sensorlab.models import LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)

    first = LabAttempt.objects.start(user=user, lab=lab)
    first.advance()
    again = LabAttempt.objects.start(user=user, lab=lab)

    assert again.pk == first.pk
    assert again.current_step == first.current_step, "resuming moved the step"
    assert LabAttempt.objects.filter(user=user, lab=lab).count() == 1


def test_starting_a_lab_you_have_finished_makes_a_second_attempt():
    """The decision, half two.

    A finished run is a record, so it is never reopened. Spec §6 wants
    improvement over time as a learning signal, and overwriting the first
    attempt would throw away exactly the signal it asks for. The cost is
    that "the attempt" becomes "which attempt", which every later epic has
    to ask — accepted, and cheaper than the history being gone.
    """
    from django.contrib.auth import get_user_model

    from sensorlab.models import LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)

    first = LabAttempt.objects.start(user=user, lab=lab)
    while first.advance():
        pass

    second = LabAttempt.objects.start(user=user, lab=lab)
    assert second.pk != first.pk
    assert LabAttempt.objects.filter(user=user, lab=lab).count() == 2

    first.refresh_from_db()
    assert first.status == LabAttempt.Status.COMPLETED, "finishing was undone"


def test_two_people_do_not_share_an_attempt():
    from django.contrib.auth import get_user_model

    from sensorlab.models import LabAttempt

    lab = _lab()
    User = get_user_model()
    ada = User.objects.create_user("ada", password=PASSWORD)
    bob = User.objects.create_user("bob", password=PASSWORD)

    assert LabAttempt.objects.start(user=ada, lab=lab).pk != \
        LabAttempt.objects.start(user=bob, lab=lab).pk


# ------------------------------------ a step name that outlived its flow


def test_a_step_that_no_longer_exists_degrades_visibly():
    """The second decision, and the one with no obvious answer.

    `current_step` stores a step *name*, and `LAB_STEPS` can grow or lose
    one. A row written before that change then points at nothing. Throwing
    locks a student out of their own work over a word; silently resetting to
    the first step throws their progress away without saying so.

    So it reports: `resume_step` falls back to the first step, and
    `step_is_known` is False, so a screen can say what happened. Same
    answer as a missing translation — degrade visibly, never blank.
    """
    from django.contrib.auth import get_user_model

    from sensorlab.models import LAB_STEPS, LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=lab)

    LabAttempt.objects.filter(pk=attempt.pk).update(current_step="reflect")
    attempt.refresh_from_db()

    assert attempt.step_is_known is False
    assert attempt.resume_step == LAB_STEPS[0]

    attempt.current_step = LAB_STEPS[1]
    attempt.save(update_fields=["current_step"])
    assert attempt.step_is_known is True
    assert attempt.resume_step == LAB_STEPS[1]


# -------------------------------------------------------------- sharing


def test_a_share_slug_is_not_permission():
    """Two different facts. Holding the link is not being allowed in.

    The slug is generated at creation because generating it later means a
    second write at the worst moment — which quietly makes every attempt
    ever made one guessed URL away from public if `is_public` is ever
    mis-read. So the flag is what decides, and it is off.
    """
    from django.contrib.auth import get_user_model

    from sensorlab.models import LabAttempt

    lab = _lab()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=lab)

    assert attempt.share_slug, "no slug was minted"
    assert attempt.is_public is False, "an attempt was shareable the moment it existed"
    assert LabAttempt.objects.shared(attempt.share_slug) is None

    attempt.is_public = True
    attempt.save(update_fields=["is_public"])
    assert LabAttempt.objects.shared(attempt.share_slug) == attempt


def test_share_slugs_are_not_guessable_from_each_other():
    from django.contrib.auth import get_user_model

    from sensorlab.models import LabAttempt

    lab = _lab()
    User = get_user_model()
    slugs = {
        LabAttempt.objects.start(
            user=User.objects.create_user(f"u{i}", password=PASSWORD), lab=lab
        ).share_slug
        for i in range(5)
    }
    assert len(slugs) == 5
    assert all(len(str(slug)) >= 32 for slug in slugs)


def test_an_unknown_slug_is_simply_nothing():
    import uuid

    from sensorlab.models import LabAttempt

    _seed()
    assert LabAttempt.objects.shared(uuid.uuid4()) is None


# ---------------------------------------------------------- in the admin


def test_an_attempt_is_visible_but_not_editable_in_the_admin():
    """Readable because support questions are real; read-only because a
    student's run is a record of what happened, and an admin quietly
    changing one produces history that never occurred."""
    from django.contrib import admin

    from sensorlab.models import LabAttempt

    assert LabAttempt in admin.site._registry
    options = admin.site._registry[LabAttempt]
    assert options.has_change_permission(None) is False
    assert options.has_add_permission(None) is False


def test_the_attempt_admin_opens(client, django_user_model):
    """Registration is not the same claim as "it opens".

    Four defects in Epic B passed every structural assertion and were
    obvious the moment somebody looked. `list_display` naming a field that
    no longer exists is exactly that shape — `manage.py check` catches some
    of it, a rendered page catches the rest.
    """
    from sensorlab.models import LabAttempt

    lab = _lab()
    student = django_user_model.objects.create_user("ada", password=PASSWORD)
    LabAttempt.objects.start(user=student, lab=lab)

    staff = django_user_model.objects.create_superuser(
        username="sl-admin", email="a@example.com", password="x"
    )
    client.force_login(staff)

    listing = client.get("/admin/sensorlab/labattempt/")
    assert listing.status_code == 200
    assert "measuring-g" in listing.content.decode()

    # No "Add" affordance, because adding one by hand invents history.
    assert "/admin/sensorlab/labattempt/add/" not in listing.content.decode()
