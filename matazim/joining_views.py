"""How anyone becomes anyone.

Before this, nothing in the app could create a `Leader` or a `Student`: the
roles existed and Django admin was the only way in.

Four people walk four different paths through here, and Avi's brief was that the
UX is the feature. So the rule every view below follows is that **no state is a
dead end and nothing is silently dropped**. Someone who taps an invite before
they have an account, or before they have passed the entrance test, has not done
anything wrong: they are simply early, and the invite has to survive being
early. Losing it quietly is how a teenager ends up in the program attached to
nobody.

Asking is not the same as being accepted. `Student.leader` is who has them,
`Student.pending_leader` is who they asked. An invite link sets `leader`
outright, because the leader handed out the link and the choice is already
theirs (REQ-M.9). The open door sets `pending_leader` and waits (REQ-M.10).
"""

import io

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .access import institution_of, is_program_manager, leader_of, visible_leaders
from .consent import consent_blocker, needs_guardian_consent
from .history import record_arrival, record_leader_change, set_status
from .models import Application, Leader, Notification, Student
from .views import member_profile, shell

LOGIN_URL = "/matazim/login/"

# An invite lives here rather than in a column. A WhatsApp link survives being
# tapped again, which is the real recovery path, and a column would need a
# migration to hold something that usually lives for twenty minutes. What makes
# it safe is that the leader's name is shown at every step, so nobody has to
# trust that it is still there.
INVITE_KEY = "mz_invite_code"


def pending_invite(request):
    """The leader whose link brought them here, if that is still true."""
    code = request.session.get(INVITE_KEY)
    if not code:
        return None
    return Leader.objects.filter(join_code=code, is_active=True).first()


def student_of(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return Student.objects.filter(user=user).order_by("-cohort_year").first()


def has_passed(user):
    profile = member_profile(user)
    return bool(profile and profile.has_passed_entrance_test())


# --- Journey A: someone arrives with a link ---------------------------------

CODE_TRIES = 8
CODE_WINDOW = 15 * 60


def _client_key(request):
    """Who is guessing: the address when there is one, the session otherwise."""
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or "-"


def enter_code(request):
    """REQ-M.165, REQ-M.166 — "I want to be a מטצ": a box for a leader's code.

    Public on purpose, like the link it stands in for: the code is read off a
    board or out of a chat and typed by someone who may have no account yet.
    A right code goes to the same page the link opens, which remembers it
    through registering. A wrong code says so and nothing more.

    Throttled, because a code is a secret that gets typed into a box: eight
    wrong guesses in fifteen minutes from one place and the box rests. The
    codes are long random strings, so this is a seatbelt and not the lock.
    """
    from django.core.cache import cache

    error = ""
    key = f"mz_code_fail:{_client_key(request)}"
    if request.method == "POST":
        if (cache.get(key) or 0) >= CODE_TRIES:
            error = "ניסיתם הרבה פעמים. נסו שוב בעוד כמה דקות."
        else:
            raw = (request.POST.get("code") or "").strip()
            # A pasted link carries the code as its last path segment.
            code = raw.rstrip("/").rsplit("/", 1)[-1].strip()
            leader = (
                Leader.objects.filter(join_code=code, is_active=True).first() if code else None
            )
            if leader is not None:
                return redirect("matazim:join", code=leader.join_code)
            # REQ-M.171: one box for both kinds of code. A class code goes to
            # the class's own page, which asks nothing of anybody.
            from .access import open_class_for_code

            cls = open_class_for_code(code)
            if cls is not None:
                return redirect("matazim:open_join", code=cls.code)
            if cache.add(key, 1, CODE_WINDOW) is False:
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, 1, CODE_WINDOW)
            error = "הקוד הזה לא מוכר. בדקו אותו מול המוביל/ה שלכם ונסו שוב."
    return render(
        request,
        "matazim/code.html",
        shell(request, "join", error=error, invite=pending_invite(request)),
    )



def join(request, code):
    """REQ-M.9 — the landing page an invite opens.

    Reachable logged out on purpose: the link gets pasted into WhatsApp groups
    and meets people with no account. A bare login form would tell them nothing
    about where they had landed or who had asked them.
    """
    leader = Leader.objects.filter(join_code=code, is_active=True).first()
    if leader is None:
        # A mistyped or retired link says so, rather than showing an empty
        # invitation from nobody.
        raise Http404("unknown invite")

    # Remembered from this moment, so the invite survives whatever has to happen
    # before they are eligible (REQ-M.72).
    request.session[INVITE_KEY] = code

    already = student_of(request.user)
    passed = has_passed(request.user)

    if request.method == "POST" and request.POST.get("action") == "join":
        if not request.user.is_authenticated:
            return redirect(f"{LOGIN_URL}?next={request.path}")
        # REQ-M.191 (Atid, 2026-10-15): only after passing the test is somebody
        # invited to join a leader, by a code or from the list. This replaces
        # REQ-M.177's "no test before joining". The code is remembered, so after
        # the test it is waiting for them.
        if not passed:
            return redirect("/matazim/test/?gate=1")
        if needs_guardian_consent(member_profile(request.user)):
            # REQ-M.84 — this is the moment their data starts being shown to
            # another person, which is the moment consent is owed. Not earlier:
            # signing in and doing the test are disclosed to nobody.
            return redirect("matazim:profile")
        _attach(request, leader, "הצטרפות בקישור")
        request.session.pop(INVITE_KEY, None)
        return redirect("matazim:joined")

    return render(
        request,
        "matazim/join.html",
        shell(
            request,
            "join",
            leader=leader,
            schools=leader.classes.values_list("school_name", flat=True).distinct(),
            passed=passed,
            student=already,
            consent_blocker=(
                consent_blocker(member_profile(request.user))
                if request.user.is_authenticated
                else None
            ),
        ),
    )


def _attach(request, leader, note):
    """Make this person that leader's student, at once.

    One act for both doors, the code and the list, so they cannot drift apart:
    joining is the student's own act and needs nobody's yes (Atid, 2026-10-15:
    "הוא יכול באופן עצמאי לצרף את עצמו אחרי המבחן"). The first line of their
    history is written here (REQ-M.21).
    """
    already = student_of(request.user)
    if already is None:
        already = Student.objects.create(
            user=request.user, leader=leader, status=Student.IN_TRAINING
        )
        record_arrival(already, by=request.user, note=note)
    else:
        already.leader = leader
        already.pending_leader = None
        already.save(update_fields=["leader", "pending_leader", "updated_at"])
        set_status(already, Student.IN_TRAINING, by=request.user, note=note)
    return already


@login_required(login_url=LOGIN_URL)
def join_leader(request):
    """REQ-M.191 - after the test, choose a leader: the one thing there is to do.

    The open list, sortable by school. Replaces the application of REQ-M.16 and
    the retirement of the list in REQ-M.165 (Q22): Atid asked for the list, and
    for joining to be the student's own act.
    """
    from .access import joinable_leaders
    from .gate import JOIN, MEMBER, TEST, preview_stage, stage_for

    stage = stage_for(request)
    looking = bool(preview_stage(request))
    if stage is None:
        return redirect("matazim:home")
    if stage == TEST:
        return redirect("/matazim/test/?gate=1")
    if stage == MEMBER:
        return redirect("matazim:my_path")

    # A code they were handed before the test is waiting for them.
    waiting = Leader.objects.filter(
        join_code=request.session.get(INVITE_KEY, ""), is_active=True
    ).first()
    if waiting is not None and request.method == "GET":
        return redirect("matazim:join", code=waiting.join_code)

    error = ""
    if request.method == "POST" and looking:
        error = "זו תצוגה בלבד, ואי אפשר להצטרף ממנה."
    elif request.method == "POST":
        leader = joinable_leaders().filter(pk=request.POST.get("leader")).first()
        if leader is None:
            error = "בחרו מוביל/ה מהרשימה."
        elif needs_guardian_consent(member_profile(request.user)):
            return redirect("matazim:profile")
        else:
            _attach(request, leader, "בחירה מהרשימה")
            return redirect("matazim:joined")

    want_school = (request.GET.get("school") or "").strip()
    leaders = list(joinable_leaders().select_related("user", "user__profile").prefetch_related("classes"))
    schools = sorted({name for leader in leaders for name in leader.school_names})
    rows = [
        {"leader": leader, "name": _name_of(leader), "schools": leader.school_names}
        for leader in leaders
        if not want_school or want_school in leader.school_names
    ]
    rows.sort(key=lambda r: (r["schools"][:1] or [""], r["name"]))
    return render(
        request,
        "matazim/join_leader.html",
        shell(request, "join", rows=rows, schools=schools, want_school=want_school, error=error),
    )


@login_required(login_url=LOGIN_URL)
def joined(request):
    """Where you land the moment you are in. A state, not a flash message."""
    return render(
        request,
        "matazim/joined.html",
        shell(request, "joined", student=student_of(request.user)),
    )


# --- Journey B: no link, so pick a leader -----------------------------------


@login_required(login_url=LOGIN_URL)
def apply(request):
    """REQ-M.16 and REQ-M.10 — the row that finally makes someone a student.

    Three questions and no more. The application is not what assesses anyone,
    the entrance test is, so every extra field here is only a teenager who does
    not finish the form.
    """
    if needs_guardian_consent(member_profile(request.user)):
        # REQ-M.84 — both doors, or neither.
        return redirect("matazim:profile")

    existing = student_of(request.user)
    if existing and (existing.leader or existing.pending_leader):
        return redirect("matazim:profile")

    error = ""
    if request.method == "POST":
        leader = Leader.objects.filter(pk=request.POST.get("leader"), is_active=True).first()
        grade = (request.POST.get("grade") or "").strip()
        motivation = (request.POST.get("motivation") or "").strip()

        if leader is None:
            error = "בחרו מוביל מהרשימה."
        elif not grade or not motivation:
            error = "צריך למלא את הכיתה ואת מה שמושך אתכם לתוכנית."
        else:
            student = existing or Student(user=request.user)
            # Asking, not being accepted. The leader says yes (REQ-M.10).
            student.pending_leader = leader
            student.save()
            # REQ-M.16 — keep what they wrote. This is the whole reason the
            # three questions are on the form: the leader deciding has to be
            # able to read them. Written after the Student row exists and
            # before the status moves, so an application without an applicant
            # is not a state that can occur.
            Application.objects.create(
                student=student,
                asked=leader,
                grade=grade,
                motivation=motivation,
                built_before=(request.POST.get("built") or "").strip(),
            )
            set_status(student, Student.APPLIED, by=request.user, note="בקשה להצטרף")
            return redirect("matazim:joined")

    return render(
        request,
        "matazim/apply.html",
        shell(
            request,
            "apply",
            leaders=Leader.objects.filter(is_active=True).prefetch_related("classes"),
            error=error,
            posted=request.POST,
        ),
    )


# --- Journey D: the leader --------------------------------------------------


def leader_entrance(request):
    """REQ-M.66 — the same door, doing the right thing for the right person.

    An actual leader goes to their page. Everyone else gets told plainly that
    leader access is granted by the program team, instead of being handed the
    student registration form, which is what this door used to do.
    """
    if leader_of(request.user):
        return redirect("matazim:leader_home")

    # REQ-M.99 — a candidate is a real state (REQ-M.93) and this page did not
    # know it existed. It told them "already invited? sign in with the email
    # you gave the team and this page will take you straight to your area",
    # while they were signed in with that email, and then took them nowhere.
    # From their side the invitation appeared to have done nothing at all.
    from .access import candidate_of

    return render(
        request,
        "matazim/leader_entrance.html",
        shell(request, "leader", candidate=candidate_of(request.user)),
    )


@login_required(login_url=LOGIN_URL)
def leader_home(request):
    """REQ-M.73 — a leader has somewhere to stand.

    Their link to hand out, and the people waiting on them. The roster proper is
    a later sprint; without this the open door has no exit, because nobody can
    accept anyone.
    """
    leader = leader_of(request.user)
    if leader is None:
        # SPR-M.44 — a candidate is not a trespasser.
        #
        # A teacher whose row is still unapproved (REQ-M.93) got the same 403
        # as a stranger, and that page tells the reader to talk to "המוביל
        # שלכם בבית הספר". For a teenager that is the right sentence. For a
        # teacher waiting on the programme team it is advice to ask themselves,
        # and it says nothing about the thing they actually want to know, which
        # is whether their request has been answered yet.
        #
        # ההרשאה שלי is that screen and already exists, so this sends them to
        # it rather than refusing them. Still a refusal for everybody else:
        # `candidate_of` is the unapproved row, not a way in.
        from .access import candidate_of

        if candidate_of(request.user):
            return redirect("matazim:leader_entrance")
        raise PermissionDenied

    from .landing import leader_dashboard
    from .year import patrol_by_school, recruiting_deadline
    from .year_views import year_context

    year = year_context(request.user)
    return render(
        request,
        "matazim/leader_home.html",
        shell(
            request,
            "leader",
            leader=leader,
            leader_name=_name_of(leader),
            # REQ-M.187 - the patrol of about ten, against the deadline.
            year=year,
            patrol=patrol_by_school(Student.objects.filter(leader=leader)),
            # SPR-M.58 — the group at a glance, and the numbers the program
            # manager sees about it, on the page a leader opens every day.
            dashboard=leader_dashboard(leader),
            join_url=request.build_absolute_uri(f"/matazim/join/{leader.join_code}/"),
            waiting=_waiting_on(leader),
            # REQ-M.124 — work sitting on this leader's desk. A queue nobody is
            # told about is a queue that grows, and the member is waiting on a
            # person: nothing else in the product will tell that person.
            work_waiting=list(
                _work_waiting(leader).select_related("student__user", "student__user__profile")
            ),
            mine=Student.objects.filter(leader=leader).select_related("user", "user__profile"),
        ),
    )


def _name_of(leader):
    """A leader by the name they are called. Same reason as REQ-M.85's fix:
    a notice that says `noa@example.com` is a notice about a database row."""
    from .certification import _display_name

    return _display_name(leader.user) if leader else ""


def _name_of_student(student):
    from .certification import _display_name

    return _display_name(student.user)


def _work_waiting(leader):
    from .submission_views import waiting_for

    return waiting_for(leader)


def _waiting_on(leader):
    """The people asking this leader, each with what they actually wrote.

    REQ-M.16. Approving used to be a name, an email and two buttons, which is a
    decision taken blind. The answers travel with the person here so the leader
    reads them on the screen where they say yes, rather than on a screen they
    would have to think to go and find.

    `applications` is ordered newest first, so the first one addressed to this
    leader is the live request; earlier ones are how we can say "has asked
    before", which is the thing a leader most wants to know and the reason this
    keeps a row per asking rather than overwriting one.
    """
    rows = []
    for student in (
        Student.objects.filter(pending_leader=leader)
        .select_related("user", "user__profile")
        .prefetch_related("applications")
    ):
        theirs = [a for a in student.applications.all() if a.asked_id == leader.pk]
        rows.append(
            {
                "student": student,
                "application": theirs[0] if theirs else None,
                "asked_before": max(len(theirs) - 1, 0),
            }
        )
    return rows


@require_POST
@login_required(login_url=LOGIN_URL)
@require_POST
def leader_test_switch(request):
    """REQ-M.178 — one switch: does this leader ask their members for the test?

    Flipping it removes nobody and un-certifies nobody; it changes who counts
    as ready and what the roster says is outstanding, nothing else.
    """
    leader = leader_of(request.user)
    if leader is None:
        raise PermissionDenied
    leader.requires_entrance_test = request.POST.get("required") == "1"
    leader.save(update_fields=["requires_entrance_test"])
    return redirect("matazim:leader_home")


@login_required(login_url=LOGIN_URL)
def leader_confirm(request, student_id):
    """Say yes, or say no. Scoped to people who actually asked *you*."""
    leader = leader_of(request.user)
    if leader is None:
        raise PermissionDenied

    # The scoping from SPR-M.6, enforced on a write this time: the queryset
    # cannot reach someone who asked a different leader.
    student = Student.objects.filter(pk=student_id, pending_leader=leader).first()
    if student is None:
        raise Http404("not waiting on you")

    if request.POST.get("action") == "confirm":
        student.leader = leader
        student.pending_leader = None
        # Same moment, the other way in. מתמיינים is the selection stage, and
        # this person has just been accepted out of it.
        student.save(update_fields=["leader", "pending_leader", "updated_at"])
        set_status(student, Student.IN_TRAINING, by=request.user, note="אישור מוביל/ה")
        # REQ-M.33 — somebody has been waiting to hear this.
        from .notify import notify

        notify(
            student.user,
            Notification.JOINED,
            f"{_name_of(leader)} אישר/ה אתכם. אתם בתוכנית.",
            url=reverse("matazim:my_path"),
            actor=request.user,
        )
    else:
        student.pending_leader = None
        student.save(update_fields=["pending_leader", "updated_at"])

    return redirect("matazim:leader_home")


@login_required(login_url=LOGIN_URL)
def leader_qr(request, leader_id):
    """The invite as an image, because it gets printed and stuck on a wall.

    REQ-M.79, spec §4.10 finding P1. This had no authentication and no
    authorization at all, and `leader_id` is a sequential integer, so the
    endpoint could be walked to harvest every leader's join code.

    That is worse than it sounds. A join code is not a convenience, it is a
    bearer credential: REQ-M.9 attaches whoever holds it to that leader **with
    no confirmation**, deliberately, because the leader handed the link out. An
    open endpoint here was therefore an unauthenticated write to somebody else's
    roster, not merely a leak.
    """
    import qrcode

    # REQ-M.79 for authorisation, REQ-M.88 for which world. Taken out of the
    # scoped queryset rather than fetched and then checked: a program manager
    # asking for another institution's leader gets a 404 from the query, not a
    # permission check somebody has to remember to write.
    leader = get_object_or_404(visible_leaders(request.user), pk=leader_id)
    url = request.build_absolute_uri(f"/matazim/join/{leader.join_code}/")
    image = qrcode.make(url, box_size=8, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


# --- Journey C: the admin ---------------------------------------------------


@login_required(login_url=LOGIN_URL)
def staff_leaders(request):
    """REQ-M.25 — assigning a leader, the thing an admin exists to do."""
    if not is_program_manager(request.user):
        raise PermissionDenied

    error = ""
    notice = ""
    if request.method == "POST" and request.POST.get("action") == "add":
        email = (request.POST.get("email") or "").strip().lower()
        person = User.objects.filter(email__iexact=email).first()
        if person is None:
            # Never created here either, for the same reason as adminship: a
            # typo must not conjure an account with a role attached.
            error = f"לא נמצא חשבון עם האימייל {email}. אפשר למנות רק מי שכבר נרשם לאתר."
        else:
            from .invite_views import approve_leader, tell_them

            # SPR-M.73: the same act as approving on /staff/team/ (REQ-M.93),
            # through the same function, and the same mail after it (REQ-M.90).
            # Before, this screen made a leader in silence, and a person who had
            # already signed up through the open invite stayed a candidate here,
            # because get_or_create found their row and approved nothing.
            existing = Leader.objects.filter(user=person).first()
            mine = institution_of(request.user)
            if existing and existing.institution_id not in (None, getattr(mine, "pk", None)):
                error = "החשבון הזה כבר משויך לתוכנית אחרת."
            else:
                leader = approve_leader(person, request.user)
                notice = f"{email} מוגדר/ת כמוביל/ה. " + (
                    "נשלח אליו/ה מייל עם הקישור לאזור המובילים."
                    if tell_them(request, leader)
                    else "לא הצלחנו לשלוח מייל. אפשר לשלוח שוב מהדף של המוביל/ה."
                )

    return render(
        request,
        "matazim/staff_leaders.html",
        shell(
            request,
            "staff",
            # REQ-M.88 — her leaders, not every leader on the platform.
            leaders=visible_leaders(request.user).select_related("user", "user__profile"),
            error=error,
            notice=notice,
        ),
    )


@login_required(login_url=LOGIN_URL)
def staff_leader(request, leader_id):
    """One leader: their link, their QR, and the two switches an admin has."""
    if not is_program_manager(request.user):
        raise PermissionDenied

    # REQ-M.88 — scoped, so every write on this page (rotate, deactivate,
    # activate) is scoped too, without each one needing its own check.
    leader = get_object_or_404(visible_leaders(request.user), pk=leader_id)
    notice = ""

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "rotate":
            from .models import new_join_code

            leader.join_code = new_join_code()
            leader.save(update_fields=["join_code"])
            notice = "הקישור הוחלף. הקישור הקודם כבר לא עובד."
        elif action == "deactivate":
            # REQ-M.67 — destroys nothing. They leave the join list and take no
            # new students; everyone they already have stays theirs.
            leader.is_active = False
            leader.save(update_fields=["is_active"])
            notice = "המוביל/ה הוצא/ה משימוש. המטצים הקיימים נשארים משויכים."
        elif action == "activate":
            leader.is_active = True
            leader.save(update_fields=["is_active"])
            notice = "המוביל/ה חזר/ה לפעילות."
        elif action == "send_access" and leader.is_approved:
            # SPR-M.73: "they did not get a mail" has an answer on the screen
            # where she is looking at them, not a request to the bot.
            from .invite_views import tell_them

            notice = (
                f"נשלח מייל אל {leader.user.email}."
                if tell_them(request, leader)
                else "לא הצלחנו לשלוח מייל. אפשר להעתיק את הקישור לאזור המובילים ולשלוח בוואטסאפ."
            )
        elif action == "move":
            # REQ-M.98 — a teacher leaves, a child changes school, a pairing
            # does not work. Both ends are read through the manager's own scope,
            # so a student cannot be moved out of her world or into it: the
            # student must belong to this leader, and the destination must be a
            # leader she owns. Root's scope is everything, which is correct.
            student = Student.objects.filter(
                pk=request.POST.get("student"), leader=leader
            ).first()
            target = visible_leaders(request.user).filter(
                pk=request.POST.get("to"), is_active=True
            ).first()
            if student is None or target is None:
                notice = "לא הצלחנו להעביר. בדקו שהמטצ והמוביל/ה עדיין קיימים."
            elif target.pk == leader.pk:
                notice = "המטצ כבר משויך למוביל/ה הזה."
            else:
                record_leader_change(
                    student,
                    target,
                    by=request.user,
                    note=f"הועבר/ה מ{_name_of(leader)} ל{_name_of(target)}",
                )
                notice = f"{_name_of_student(student)} הועבר/ה ל{_name_of(target)}."

    return render(
        request,
        "matazim/staff_leader.html",
        shell(
            request,
            "staff",
            leader=leader,
            notice=notice,
            join_url=request.build_absolute_uri(f"/matazim/join/{leader.join_code}/"),
            students=Student.objects.filter(leader=leader).count(),
            waiting=Student.objects.filter(pending_leader=leader).count(),
            # REQ-M.98 — somewhere to move somebody to. Her other active
            # leaders, never the one whose page this is.
            move_targets=visible_leaders(request.user)
            .filter(is_active=True)
            .exclude(pk=leader.pk)
            .select_related("user", "user__profile"),
            # REQ-M.95 — Avi, looking at the demo: opening a leader should show
            # their students, not only a count. A number says there are three;
            # it does not say which three, which is the only question worth
            # opening the page for.
            #
            # The same two readers the roster uses, so this page and the
            # leader's own cannot come to disagree about the same teenager.
            rows=_students_of(leader),
        ),
    )


def _students_of(leader):
    """That leader's students, with the progress and eligibility a row shows.

    Deliberately the same shape the roster builds (`roster_views.roster`), so
    the template can reuse the roster row rather than growing a second one.
    """
    from .certification import eligibility_for_many
    from .content import REQUIRED_COURSE_SLUGS
    from .progress import cohort_progress, track_summary

    people = list(
        Student.objects.filter(leader=leader)
        .select_related("user", "user__profile")
        .prefetch_related("classes")
    )
    progress = cohort_progress(people, REQUIRED_COURSE_SLUGS)
    states = eligibility_for_many(people)
    return [
        {
            "student": person,
            "progress": track_summary(progress.get(person.user_id, {})),
            "eligibility": states.get(person.user_id),
        }
        for person in people
    ]
