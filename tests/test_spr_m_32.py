"""SPR-M.32 — קהילת מט״צים, the feed inside the walls.

REQ-M.26, M.131, M.132, M.133, M.134. Spec §4.12. The last of the three
SPR-M.1 placeholders becomes real.

Four tests here carry more weight than the rest, and each holds a rule that a
reasonable-looking simplification would destroy.

`test_another_institutions_feed_is_not_yours` is §4.4 applied to words rather
than to records. A leader at another school reading a fourteen-year-old's post
is not a smaller breach than reading their grades.

`test_a_taken_down_post_keeps_its_row_and_says_why` holds REQ-M.131. The
obvious implementation of moderation is `delete()`, and it is wrong: a post that
vanishes teaches its writer nothing, and a writer who cannot tell whether they
were moderated or glitched learns to distrust the room.

`test_the_public_page_carries_no_posts` holds REQ-M.133, the rule most likely to
be softened later by somebody who thinks a feed would make the public page
livelier.

`test_the_api_cannot_reach_further_than_the_screen` holds REQ-M.134's reason for
existing. An API that built its own queryset would be a second answer to "who
may see this", free to drift from the one the screens use.

Traces: REQ-M.26, M.131, M.132, M.133, M.134, M.102, §4.4, §4.10, §4.12.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm32

PASSWORD = "sprm32-pass-4471"


@pytest.fixture(autouse=True)
def no_model_calls(settings):
    """The relevance gate is babook's, and babook's tests exercise it.

    Off by default here so these tests measure מט״צים's decisions rather than
    somebody's API uptime. The two tests about moderation turn it back on with
    a stub, which is the part that is ours.
    """
    settings.CONTENT_RELEVANCE_ENABLED = False


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _manager(email="naomi@example.com", name="נעמי"):
    from matazim.models import MemberProfile

    user = _user(email, name)
    _make_manager(user)
    return user


def _leader(email, name, manager):
    from matazim.models import Leader

    return Leader.objects.create(
        user=_user(email, name), institution=_inst(manager), approved_at=timezone.now()
    )


def _student(email, leader, name="יובל כהן"):
    from matazim.models import MemberProfile, Student

    user = _user(email, name)
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    return Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)


def _post(author, manager, body="לימדתי היום לולאות", **extra):
    from matazim.models import Post

    return Post.objects.create(author=author, institution=_inst(manager), body=body, **extra)


# ------------------------------------------- who the room belongs to


def test_another_institutions_feed_is_not_yours(client, db):
    """T-F-M.32.2-1: §4.4, applied to words.

    Not merely hidden: never in the queryset. A leader at another school
    reading a fourteen-year-old's post is not a smaller breach than reading
    their grades.
    """
    from matazim.access import visible_posts

    naomi = _manager("naomi@example.com")
    other = _manager("other@example.com", "מנהלת אחרת")

    mine = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _post(mine.user, naomi, "מה שכתבנו")
    _post(other, other, "מה שכתבו הם")

    bodies = set(visible_posts(mine.user).values_list("body", flat=True))
    assert bodies == {"מה שכתבנו"}, "another institution's words were readable"


def test_a_candidate_has_no_standing_in_the_room(client, db):
    """T-F-M.32.2-2: REQ-M.99, REQ-M.102, §4.12.

    Somebody waiting on approval belongs to no institution, so no feed is
    theirs. Not an error in them, and not everybody's feed either.
    """
    from matazim.access import institution_of, visible_posts
    from matazim.models import Leader

    naomi = _manager()
    _post(naomi, naomi, "הודעה")

    waiting = _user("waiting@example.com", "איתי")
    Leader.objects.create(user=waiting, institution=_inst(naomi), approved_at=None)

    assert institution_of(waiting) is None
    assert not visible_posts(waiting).exists()


def test_a_candidate_gets_the_page_about_the_community_not_the_feed(client, db):
    """T-F-M.32.3-1: REQ-M.102 — one door, and each reader gets their own page."""
    from matazim.models import Leader

    naomi = _manager()
    _post(naomi, naomi, "סוד מהתוכנית")

    waiting = _user("waiting@example.com", "איתי")
    Leader.objects.create(user=waiting, institution=_inst(naomi), approved_at=None)

    client.force_login(waiting)
    html = client.get(reverse("matazim:community")).content.decode()

    assert "סוד מהתוכנית" not in html, "a candidate was shown the feed"
    assert "איך נכנסים" in html


# ------------------------------------------- the public page


def test_the_public_page_carries_no_posts(client, db):
    """T-F-M.32.6-1: REQ-M.133, §4.10, REQ-M.30a.

    Every row in that feed is a fourteen-year-old writing about themselves. An
    internal feed and a consented public gallery are different products, and
    building the first must not quietly open the second.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _post(student.user, naomi, "לימדתי היום לולאות")

    html = client.get(reverse("matazim:community")).content.decode()

    assert "לימדתי היום לולאות" not in html, "a minor's post was published"
    assert "יובל כהן" not in html, "a member was named on a public page"
    assert "איך נכנסים" in html


# ------------------------------------------- writing


def test_a_member_writes_and_the_institution_is_stamped_not_guessed(client, db):
    """T-F-M.32.1-1: REQ-M.26, §4.4.

    Stamped at write time rather than read back through the author later,
    because `Student.leader` can change (REQ-M.98) and a post must not move to a
    different school when a teenager does.
    """
    from matazim.models import Post

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    client.force_login(student.user)
    client.post(reverse("matazim:community"), {"body": "לימדתי היום לולאות"})

    post = Post.objects.get()
    assert post.institution_id == _inst(naomi).id
    assert post.kind == Post.POST


def test_the_program_managers_words_are_an_announcement(client, db):
    """T-F-M.32.1-2: REQ-M.26. Three kinds, and the kind is not typed by hand."""
    from matazim.models import Post

    naomi = _manager()
    _leader("noa@example.com", "נעה", naomi)

    client.force_login(naomi)
    client.post(reverse("matazim:community"), {"body": "מפגש בשבוע הבא"})

    assert Post.objects.get().kind == Post.ANNOUNCEMENT


def test_an_empty_post_is_refused(client, db):
    """T-F-M.32.3-2: a row nothing was typed into is not a post."""
    from matazim.models import Post

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    client.force_login(student.user)
    response = client.post(reverse("matazim:community"), {"body": "   "})

    assert response.status_code == 200
    assert not Post.objects.exists()


def test_moderation_is_asked_before_a_post_is_stored(client, db, monkeypatch, settings):
    """T-F-M.32.4-1: REQ-M.131, §2.1.

    babook's engine, our decision about what to do with the answer. The engine
    is babook's to test. What is ours is that we ask it at all, and that a
    refusal stops the write rather than being logged and ignored.
    """
    from matazim.models import Post

    settings.CONTENT_RELEVANCE_ENABLED = True
    asked = {}

    def refuse(text, context_label="", user=None):
        asked["text"] = text
        return False, {"categories": ["off_topic"]}

    monkeypatch.setattr("app.safety.text_relevance_ok", refuse)

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    client.force_login(student.user)
    response = client.post(reverse("matazim:community"), {"body": "משהו לא קשור"})

    assert asked.get("text") == "משהו לא קשור", "the post was stored without being asked about"
    assert not Post.objects.exists(), "a refused post was stored anyway"
    assert "לא מתאים" in response.content.decode()


def test_a_post_survives_the_model_being_unreachable(client, db, monkeypatch, settings):
    """T-F-M.32.4-2: REQ-M.131 — fail open, like everything else here.

    A model having a bad afternoon must never cost somebody their words.
    """
    from matazim.models import Post

    settings.CONTENT_RELEVANCE_ENABLED = True

    def explode(text, context_label="", user=None):
        raise RuntimeError("no model today")

    monkeypatch.setattr("app.safety.text_relevance_ok", explode)

    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    client.force_login(student.user)
    client.post(reverse("matazim:community"), {"body": "לימדתי היום לולאות"})

    assert Post.objects.count() == 1, "a member lost their post to an API outage"


# ------------------------------------------- taking one down


def test_a_taken_down_post_keeps_its_row_and_says_why(client, db):
    """T-F-M.32.4-3: REQ-M.131.

    The obvious implementation of moderation is `delete()`, and it is wrong. A
    post that vanishes teaches its writer nothing, and a writer who cannot tell
    whether they were moderated or glitched learns to distrust the room.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    post = _post(student.user, naomi, "משהו שצריך לרדת")

    client.force_login(naomi)
    client.post(reverse("matazim:hide_post", args=[post.pk]), {"reason": "יש כאן שם של ילד"})

    from matazim.models import Post

    # Checked before refreshing, because a deleted row raises DoesNotExist and
    # the test would then fail on a stack trace instead of saying what broke.
    assert Post.objects.filter(pk=post.pk).exists(), (
        "the row was destroyed instead of marked"
    )

    post.refresh_from_db()
    assert post.is_hidden
    assert post.body == "משהו שצריך לרדת", "the words were edited"

    client.force_login(student.user)
    html = client.get(reverse("matazim:community")).content.decode()
    assert "הוסתר" in html, "the writer was not told what happened"
    assert "יש כאן שם של ילד" in html, "the writer was not told why"


def test_a_hidden_post_leaves_everybody_elses_feed(client, db):
    """T-F-M.32.4-4: REQ-M.131 — hidden means hidden, for everyone but its writer."""
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    author = _student("kid1@example.com", noa)
    reader = _student("kid2@example.com", noa, name="דנה לוי")
    post = _post(author.user, naomi, "משהו שירד")

    client.force_login(naomi)
    client.post(reverse("matazim:hide_post", args=[post.pk]), {"reason": "סיבה"})

    client.force_login(reader.user)
    assert "משהו שירד" not in client.get(reverse("matazim:community")).content.decode()


def test_hiding_without_words_is_refused(client, db):
    """T-F-M.32.4-5: the same argument `submission_views` makes about returning
    work. An action that only says no tells the person it happened to that they
    failed, and not what to do about it.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    post = _post(student.user, naomi)

    client.force_login(naomi)
    client.post(reverse("matazim:hide_post", args=[post.pk]), {"reason": "  "})

    post.refresh_from_db()
    assert not post.is_hidden


def test_only_the_program_manager_takes_something_down(client, db):
    """T-F-M.32.4-6: §4.4a."""
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    author = _student("kid1@example.com", noa)
    other = _student("kid2@example.com", noa, name="דנה לוי")
    post = _post(author.user, naomi)

    for user in (noa.user, other.user):
        client.force_login(user)
        response = client.post(
            reverse("matazim:hide_post", args=[post.pk]), {"reason": "כי"}
        )
        assert response.status_code == 403

    post.refresh_from_db()
    assert not post.is_hidden


def test_she_cannot_reach_another_institutions_post(client, db):
    """T-F-M.32.4-7: §4.4, on a write."""
    naomi = _manager("naomi@example.com")
    other = _manager("other@example.com", "אחרת")
    theirs = _post(other, other, "לא שלה")

    client.force_login(naomi)
    response = client.post(
        reverse("matazim:hide_post", args=[theirs.pk]), {"reason": "כי"}
    )
    assert response.status_code == 404

    theirs.refresh_from_db()
    assert not theirs.is_hidden


# ------------------------------------------- sharing work


def test_only_your_own_approved_work_can_be_shared(client, db):
    """T-F-M.32.5-1: REQ-M.132, REQ-M.30a.

    Approved only, because the feed is not a place to be seen failing. Your own
    only, because §4.10 says whose decision that is.
    """
    from matazim.models import Post, Submission

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    mine = _student("kid1@example.com", noa)
    theirs = _student("kid2@example.com", noa, name="דנה לוי")

    waiting = Submission.objects.create(
        student=mine, leader=noa, title="עוד לא אושר", status=Submission.WAITING
    )
    somebody_elses = Submission.objects.create(
        student=theirs, leader=noa, title="של דנה", status=Submission.APPROVED
    )

    client.force_login(mine.user)
    for submission in (waiting, somebody_elses):
        client.post(
            reverse("matazim:community"),
            {"body": "תראו מה עשיתי", "submission": str(submission.pk)},
        )

    assert not Post.objects.exists(), "work that was not shareable reached the feed"


def test_sharing_approved_work_marks_it_as_a_work_post(client, db):
    """T-F-M.32.5-2: REQ-M.132 — three kinds, and this is the third."""
    from matazim.models import Post, Submission

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    mine = _student("kid@example.com", noa)
    work = Submission.objects.create(
        student=mine, leader=noa, title="המשחק שלי", status=Submission.APPROVED
    )

    client.force_login(mine.user)
    client.post(
        reverse("matazim:community"),
        {"body": "תראו מה עשיתי", "submission": str(work.pk)},
    )

    post = Post.objects.get()
    assert post.kind == Post.WORK
    assert post.submission_id == work.pk


def test_the_maker_can_take_their_work_back_out(client, db):
    """T-F-M.32.5-3: REQ-M.132, REQ-M.30a.

    Consent that cannot be withdrawn is not consent. The work itself survives:
    withdrawing a share is not unmaking the thing.
    """
    from matazim.models import Post, Submission

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    mine = _student("kid@example.com", noa)
    work = Submission.objects.create(
        student=mine, leader=noa, title="המשחק שלי", status=Submission.APPROVED
    )
    post = _post(mine.user, naomi, "תראו", kind=Post.WORK, submission=work)

    client.force_login(mine.user)
    client.post(reverse("matazim:unshare_post", args=[post.pk]))

    assert not Post.objects.exists()
    assert Submission.objects.filter(pk=work.pk).exists(), "the work itself was destroyed"


def test_nobody_deletes_somebody_elses_words(client, db):
    """T-F-M.32.5-4: deletion is withdrawal, not moderation."""
    from matazim.models import Post

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    author = _student("kid1@example.com", noa)
    other = _student("kid2@example.com", noa, name="דנה לוי")
    post = _post(author.user, naomi)

    client.force_login(other.user)
    assert client.post(reverse("matazim:unshare_post", args=[post.pk])).status_code == 404
    assert Post.objects.filter(pk=post.pk).exists()


# ------------------------------------------- the API (REQ-M.134)


def test_the_api_cannot_reach_further_than_the_screen(client, db):
    """T-F-M.32.7-1: REQ-M.134, §4.4.

    The reason the API reads `access.visible_posts` rather than a queryset of
    its own. A second answer to "who may see this" is free to drift from the
    first, and the drift is invisible until somebody reads another child's
    words.
    """
    naomi = _manager("naomi@example.com")
    other = _manager("other@example.com", "אחרת")
    mine = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    _post(mine.user, naomi, "מה שכתבנו")
    _post(other, other, "מה שכתבו הם")

    client.force_login(mine.user)
    payload = client.get("/matazim/api/posts/").json()
    rows = payload["results"] if isinstance(payload, dict) else payload
    bodies = {row["body"] for row in rows}

    assert bodies == {"מה שכתבנו"}, "the API reached another institution's feed"


def test_the_api_will_not_let_a_client_name_its_own_author(client, db):
    """T-F-M.32.7-2: REQ-M.134.

    A client that could name its author could post as another teenager. The
    serializer makes the field read-only; this says so from outside.
    """
    from matazim.models import Post

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    mine = _student("kid1@example.com", noa)
    victim = _student("kid2@example.com", noa, name="דנה לוי")

    client.force_login(mine.user)
    client.post(
        "/matazim/api/posts/",
        {"body": "לא כתבתי את זה", "author": victim.user.id},
        content_type="application/json",
    )

    assert Post.objects.get().author_id == mine.user.id


def test_the_api_will_not_let_a_client_choose_its_institution(client, db):
    """T-F-M.32.7-3: §4.4 undone through the back door is still §4.4 undone."""
    from matazim.access import institution_of
    from matazim.models import Post

    naomi = _manager("naomi@example.com")
    other = _manager("other@example.com", "אחרת")
    mine = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))

    client.force_login(mine.user)
    client.post(
        "/matazim/api/posts/",
        {"body": "שלום", "institution": institution_of(other).id},
        content_type="application/json",
    )

    assert Post.objects.get().institution_id == institution_of(naomi).id


def test_the_api_refuses_to_delete_somebody_elses_post(client, db):
    """T-F-M.32.7-4: REQ-M.131 — the API has the same manners as the screen."""
    from matazim.models import Post

    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    author = _student("kid1@example.com", noa)
    other = _student("kid2@example.com", noa, name="דנה לוי")
    post = _post(author.user, naomi)

    client.force_login(other.user)
    response = client.delete(f"/matazim/api/posts/{post.pk}/")

    assert response.status_code in (403, 404)
    assert Post.objects.filter(pk=post.pk).exists()


def test_the_api_hides_rather_than_deletes(client, db):
    """T-F-M.32.7-5: REQ-M.134 and REQ-M.131 together.

    A take-down through the API must be the same act as one on the screen, or
    the rule holds in one place and not the other.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    post = _post(student.user, naomi)

    client.force_login(naomi)
    response = client.post(
        f"/matazim/api/posts/{post.pk}/hide/",
        {"reason": "יש כאן שם של ילד"},
        content_type="application/json",
    )

    assert response.status_code == 200
    post.refresh_from_db()
    assert post.is_hidden
    assert post.hidden_reason == "יש כאן שם של ילד"


def test_a_take_down_can_be_undone(client, db):
    """T-F-M.32.4-8: REQ-M.131, and `docs/building_an_app.md`.

    A take-down is a person's judgement, so it can be a person's mistake. The
    methodology's question for whether a feature is finished is whether somebody
    can fix a mistake in it without going to /admin/, and hide without show
    fails that on the one action aimed at a teenager's own words.
    """
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    post = _post(student.user, naomi, "משהו שירד בטעות")

    client.force_login(naomi)
    client.post(reverse("matazim:hide_post", args=[post.pk]), {"reason": "טעות"})
    client.post(reverse("matazim:show_post", args=[post.pk]))

    post.refresh_from_db()
    assert not post.is_hidden
    assert post.hidden_reason == "", "the take-down's reason outlived the take-down"

    reader = _student("kid2@example.com", student.leader, name="דנה לוי")
    client.force_login(reader.user)
    assert "משהו שירד בטעות" in client.get(reverse("matazim:community")).content.decode()


def test_only_the_program_manager_puts_something_back(client, db):
    """T-F-M.32.4-9: §4.4a. The way back is not a wider door than the way out."""
    naomi = _manager()
    noa = _leader("noa@example.com", "נעה", naomi)
    author = _student("kid@example.com", noa)
    post = _post(author.user, naomi, hidden_at=timezone.now(), hidden_by=naomi,
                 hidden_reason="סיבה")

    for user in (noa.user, author.user):
        client.force_login(user)
        assert client.post(reverse("matazim:show_post", args=[post.pk])).status_code == 403

    post.refresh_from_db()
    assert post.is_hidden


def test_the_api_can_put_something_back_too(client, db):
    """T-F-M.32.7-6: REQ-M.134 — the API has the same two doors the screen has."""
    naomi = _manager()
    student = _student("kid@example.com", _leader("noa@example.com", "נעה", naomi))
    post = _post(student.user, naomi, hidden_at=timezone.now(), hidden_by=naomi,
                 hidden_reason="סיבה")

    client.force_login(naomi)
    response = client.post(f"/matazim/api/posts/{post.pk}/show/")

    assert response.status_code == 200
    post.refresh_from_db()
    assert not post.is_hidden


# --- SPR-M.40: the role is Institution.managers, the FKs are `institution` ---

def _make_manager(user):
    """One institution per test manager, so two managers are two worlds."""
    from matazim.models import Institution

    Institution.objects.create(name=f"מוסד {user.pk}").managers.add(user)


def _inst(user):
    from matazim.access import institution_of

    return institution_of(user)


def _is_pm(user):
    from matazim.access import is_program_manager

    return is_program_manager(user)
