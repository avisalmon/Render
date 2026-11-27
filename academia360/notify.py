"""Notifications (spec 4.8, backlog E.1): the bell and the mails, from one
place. Every event is one function here; a view or the API calls it and
nothing else writes a `Notification` row or sends an event mail.

`tell` writes one bell row per person, never for the actor, and mails the same
people when a body is given. The mail count is the backend's own
(methodology 53): the caller may say "mailed" only when it is above zero.
The bell gets everything; mail goes only where 4.8 lists it.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import access, mail
from .models import CommitteeAttribute, LeaderOf, Notification, Role

PAGE = 100


def _name(user):
    if user is None:
        return "מישהו"
    return (user.get_full_name() or "").strip() or user.email or user.get_username()


def _inst_name(inst):
    return inst.short_name_he or inst.name_he


def _url(name, *args, anchor=""):
    return reverse(f"academia360:{name}", args=args) + (f"#{anchor}" if anchor else "")


def tell(users, kind, title, url="", actor=None, mail_body=None, base=None):
    """Bell rows for everyone in `users` but the actor; a mail to the same
    people when `mail_body` is given. Returns (rows made, mails the backend
    accepted)."""
    people = {}
    for u in users or []:
        if u is None or not u.is_active or (actor is not None and u.pk == actor.pk):
            continue
        people[u.pk] = u
    if not people:
        return 0, 0
    rows = Notification.objects.bulk_create([
        Notification(user=u, kind=kind, title=title[:200], url=url[:300], actor=actor) for u in people.values()])
    mailed = 0
    if mail_body:
        link = (base or mail.base_url()) + url if url else ""
        body = f"{mail_body}\n{link}\n" if link else f"{mail_body}\n"
        mailed = mail.send(title, body, [u.email for u in people.values() if u.email])
    return len(rows), mailed


# ------------------------------------------------------------- who to tell

def committee_members():
    User = get_user_model()
    ids = Role.objects.filter(kind=Role.COMMITTEE_MEMBER, active=True).values_list("user_id", flat=True)
    return list(User.objects.filter(pk__in=ids, is_active=True))


def admins():
    User = get_user_model()
    ids = Role.objects.filter(kind=Role.ADMIN, active=True).values_list("user_id", flat=True)
    return list(User.objects.filter(is_active=True).filter(Q(pk__in=ids) | Q(is_superuser=True)))


def chairs(program):
    User = get_user_model()
    ids = CommitteeAttribute.objects.filter(kind=CommitteeAttribute.CHAIR, program=program).values_list("user_id", flat=True)
    return list(User.objects.filter(pk__in=ids, is_active=True))


def reviewers_of(program, institution):
    User = get_user_model()
    ids = (CommitteeAttribute.objects.filter(kind=CommitteeAttribute.REVIEWER, program=program, institution=institution)
           .values_list("user_id", flat=True))
    return list(User.objects.filter(pk__in=ids, is_active=True))


def leaders_of(institution):
    User = get_user_model()
    ids = LeaderOf.objects.filter(institution=institution, active=True).values_list("user_id", flat=True)
    return list(User.objects.filter(pk__in=ids, is_active=True))


# ------------------------------------------------------------------ events

def submission_arrived(submission, actor=None, base=None):
    """A package was submitted: the committee hears, and the institution's
    reviewers hear that a review waits for them (spec 4.8: committee, and
    "a review is due")."""
    inst = submission.participation.institution
    program = submission.participation.program
    name = _inst_name(inst)
    url = _url("committee_file", inst.slug, anchor=f"sub-{submission.pk}")
    reviewers = reviewers_of(program, inst)
    rest = [u for u in committee_members() if u.pk not in {r.pk for r in reviewers}]
    n1, m1 = tell(reviewers, "review", f"סקירה מחכה לך: {name}, {submission.get_kind_display()}",
                  _url("committee_review", submission.pk), actor,
                  f"שלום,\n\n{name} הגיש/ה {submission.get_kind_display()} לאקדמיה 360°, ואת/ה בין הסוקרים. הסקירה מחכה בחדר הוועדה.", base)
    n2, m2 = tell(rest, "submission", f"הגשה הגיעה: {name}, {submission.get_kind_display()}", url, actor,
                  f"שלום,\n\n{name} הגיש/ה {submission.get_kind_display()} לאקדמיה 360°. התיק פתוח בחדר הוועדה.", base)
    return n1 + n2, m1 + m2


def review_assigned(user, program, institution, actor=None, base=None):
    """A member was made reviewer of an institution that has a package open
    for review: a review waits for them."""
    from .models import Submission

    sub = (Submission.objects.filter(participation__program=program, participation__institution=institution,
                                     status__in=("submitted", "under_review")).order_by("-submitted_at", "-pk").first())
    if sub is None:
        return 0, 0
    name = _inst_name(institution)
    return tell([user], "review", f"סקירה מחכה לך: {name}, {sub.get_kind_display()}", _url("committee_review", sub.pk),
                actor, f"שלום,\n\nסומנת כסוקר/ת של {name} באקדמיה 360°, ויש הגשה שמחכה לסקירה.", base)


def letter_sent(letter, actor=None, base=None):
    """The committee's letter went out: the institution's leaders hear (spec 4.8)."""
    inst = letter.submission.participation.institution
    return tell(leaders_of(inst), "letter", f"מכתב הוועדה על {letter.submission.get_kind_display()} של {_inst_name(inst)}",
                _url("letter", letter.pk), actor,
                f"שלום,\n\nועדת אקדמיה 360° שלחה את תשובתה ל{letter.submission.get_kind_display()} של {_inst_name(inst)}. המכתב פתוח באתר.", base)


def decision_recorded(decision, actor=None, base=None):
    """A decision was recorded: the admin hears (spec 4.8)."""
    sub = decision.submission
    inst = sub.participation.institution
    return tell(admins(), "decision", f"החלטה נרשמה: {_inst_name(inst)}, {decision.get_outcome_display()}",
                _url("committee_file", inst.slug, anchor=f"decision-{sub.pk}"), actor,
                f"שלום,\n\n{_name(actor)} רשם/ה החלטה על {sub.get_kind_display()} של {_inst_name(inst)}: {decision.get_outcome_display()}.", base)


def correction_proposed(proposal, program=None, actor=None, base=None):
    """The public proposed a correction: the admin and the chairs hear (spec 4.8)."""
    people = admins() + (chairs(program) if program is not None else [])
    return tell(people, "correction", "הצעת תיקון חדשה מהציבור", _url("manage", anchor="corrections"), actor,
                f"שלום,\n\n{_name(actor)} הציע/ה תיקון לעובדה באקדמיה 360°: {proposal.proposed_value[:120]}. ההצעה מחכה בניהול.", base)


def mentioned(users, post, actor=None, base=None):
    """Members ticked under a post hear, by bell and by mail (spec 4.8)."""
    d = post.discussion
    return tell(users, "mention", f"{_name(actor)} אזכר/ה אותך בדיון: {d.title}",
                _url("committee_thread", d.pk, anchor=f"post-{post.pk}"), actor,
                f"שלום,\n\n{_name(actor)} אזכר/ה אותך בדיון \"{d.title}\" בחדר הוועדה של אקדמיה 360°.", base)


def new_post(users, post, actor=None):
    """The thread's earlier people hear of a new post, by bell only."""
    d = post.discussion
    return tell(users, "post", f"{_name(actor)} הגיב/ה בדיון: {d.title}", _url("committee_thread", d.pk, anchor=f"post-{post.pk}"), actor)


# ------------------------------------------------------------------- reading

def unread_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def my_notifications(request):
    """The bell's page: mine, newest first, unread marked."""
    if not request.user.is_authenticated:
        return redirect(f"{reverse('academia360:login')}?next={request.get_full_path()}")
    rows = list(Notification.objects.filter(user=request.user).select_related("actor")[:PAGE])
    return render(request, "academia360/notifications.html", {
        "section": "notifications", "rows": rows, "unread": sum(1 for r in rows if r.unread),
        "is_committee": access.is_committee(request.user),
    })


def follow(request, pk):
    """Following an item marks it read and goes where it points, inside the
    app only (the url is ours, but the rule holds anyway)."""
    if not request.user.is_authenticated:
        return redirect(f"{reverse('academia360:login')}?next={request.get_full_path()}")
    row = get_object_or_404(Notification, pk=pk, user=request.user)
    if row.read_at is None:
        row.read_at = timezone.now()
        row.save(update_fields=["read_at", "updated_at"])
    url = row.url or ""
    if url.startswith("/academia360/") and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}):
        return redirect(url)
    return redirect("academia360:notifications")


@require_POST
def read_all(request):
    if not request.user.is_authenticated:
        return redirect("academia360:login")
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return redirect("academia360:notifications")
