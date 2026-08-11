"""Chapter 10 - the מט״צים program space at /matazim/ (SPR-10.1).

The shell, the public pages, the five-stage track and the אזור אישי.

The one law that governs this module: **it reads learning state and never
writes it** (DEC-71, REQ-10.13). Every training figure below comes from
`_catalog_progress` over the existing Enrollment / UserVideoProgress /
CourseCertificate tables. Nothing here stores a course, a lesson, or a
progress number, which is also why retroactive credit (REQ-10.12) needs no
backfill: there is nothing to fill.
"""

from django.contrib import messages
from django.core.files.base import ContentFile
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .matazim_check import available_target_ids, check, encouragement, load_target
from .matazim_models import (
    EntranceAttempt,
    Program,
    ProgramApplication,
    ProgramMembership,
    ProgramStatusLog,
    School,
    gen_join_code,
)
from .models import Course, CourseCertificate

DEFAULT_PROGRAM_SLUG = "matazim"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_program(slug=DEFAULT_PROGRAM_SLUG):
    """The program record drives branding and content (REQ-10.2) - the slug is
    the only place the string 'matazim' appears outside the seed."""
    return get_object_or_404(Program, slug=slug, is_active=True)


def get_membership(user, program):
    """This user's membership in the current cohort, or None.

    Terminal states still return a membership: an alumnus should keep seeing
    their record, they are simply not a *current* מט״צ (REQ-10.9).
    """
    if not user.is_authenticated:
        return None
    return (ProgramMembership.objects
            .filter(user=user, program=program)
            .select_related("school", "program")
            .order_by("-cohort_year")
            .first())


# ---------------------------------------------------------------------------
# Who may do what (REQ-10.7, REQ-10.17)
#
# Two authorities, and only two:
#   Program.staff  -> the matazim admins. Open schools, assign leaders, grant
#                     the מט״צ status. Site superusers count as staff.
#   School.leaders -> the teachers. Their scope is exactly the schools they
#                     appear in. Since DEC-83 they grant both levels to their
#                     own members; only staff may revoke.
#
# These are checked in the views, never only in the templates. Cross-school
# leakage is a blocking defect, so the queries below are the only sanctioned
# way to reach a roster.
# ---------------------------------------------------------------------------

def is_program_staff(user, program):
    if not user.is_authenticated:
        return False
    return user.is_superuser or program.staff.filter(pk=user.pk).exists()


def schools_led(user, program):
    """The schools this user leads. Staff lead all of them."""
    if not user.is_authenticated:
        return School.objects.none()
    qs = School.objects.filter(program=program)
    if is_program_staff(user, program):
        return qs
    return qs.filter(leaders=user)


def can_view_school(user, school):
    return (is_program_staff(user, school.program)
            or school.leaders.filter(pk=user.pk).exists())


def program_staff_required(view):
    """Only the matazim admins. A non-staff user gets a 404 rather than a 403,
    so the console does not even advertise its existence."""
    def wrapped(request, *args, **kwargs):
        program = get_program()
        if not request.user.is_authenticated:
            return redirect(f"{reverse('join_wall')}?next={request.path}")
        if not is_program_staff(request.user, program):
            raise Http404("Not program staff")
        return view(request, program, *args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


def program_member_required(view):
    """Member gate for the non-public pages (REQ-10.1)."""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Reuses the existing access wall + return-to-intent (REQ-5.4).
            return redirect(f"{reverse('join_wall')}?next={request.path}")
        program = get_program()
        membership = get_membership(request.user, program)
        if membership is None:
            raise Http404("Not a member of this program")
        return view(request, program, membership, *args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


def shell_ctx(request, program, section):
    """Everything `_shell.html` needs: which nav entry is active, and which
    consoles this person may reach. Computed once, from the authorities above,
    so the nav can never advertise a page the view would refuse."""
    my_schools = schools_led(request.user, program)
    return {
        "section": section,
        "program": program,
        "membership": get_membership(request.user, program),
        "is_staff": is_program_staff(request.user, program),
        "my_schools": my_schools,
        # For marking "this one is mine" in a list without a query per row.
        "my_school_ids": set(my_schools.values_list("pk", flat=True)),
    }


def program_courses(program):
    """The הדרכות that make up this program's training.

    Reuses the existing `Course.domain` tagging rather than inventing a second
    way to say "this course belongs to מט״צים".
    """
    return (Course.objects.filter(domain=program.slug, is_published=True)
            .order_by("title"))


def training_record(user, program):
    """The derived half of a מט״צ's record (REQ-10.15): what they took, what
    they finished, what they earned. Computed live, never stored."""
    from .views import _catalog_progress

    courses = list(program_courses(program))
    progress = _catalog_progress(user, [c.id for c in courses]) if courses else {}
    certs = set(CourseCertificate.objects.filter(user=user)
                .values_list("course_id", flat=True))
    rows, started, completed = [], 0, 0
    for c in courses:
        p = progress.get(c.id, {"pct": 0, "done": 0, "total": 0,
                                "started": False, "completed": False})
        if p["started"]:
            started += 1
        if p["completed"]:
            completed += 1
        rows.append({"course": c, "p": p, "has_cert": c.id in certs})
    return {
        "rows": rows,
        "total_courses": len(courses),
        "started": started,
        "completed": completed,
        "certificates": sum(1 for r in rows if r["has_cert"]),
        # Split so the personal area can lead with what they are in the middle
        # of, rather than presenting eleven identical zero-progress cards - which
        # is what a new member used to see, and it reads as a wall of failure.
        "in_progress": [r for r in rows if r["p"]["started"] and not r["p"]["completed"]],
        "done_rows": [r for r in rows if r["p"]["completed"]],
        "not_started": [r for r in rows if not r["p"]["started"]],
    }


def next_step(membership, record):
    """The single most important line on the personal area (REQ-10.14): what do
    I do next. Returns {label, hint, url} or None when nothing is pending."""
    status = membership.status
    if status == ProgramMembership.APPLIED:
        # An applicant's next action changes three times before they are in, and
        # each transition has to be visible the moment it happens. Avi walked
        # this as a student on 2026-08-08, finished the Tinkercad course, and was
        # never told a test existed - because this branch used to return the same
        # line whatever they had done.
        tinkercad = next((r for r in record["rows"]
                          if r["course"].slug == "tinkercad"), None)
        last = membership.entrance_attempts.first()

        if last and last.is_submitted and last.passed:
            return {"label": "עברתם את מבחן הכניסה",
                    "hint": "המוביל של בית הספר יאשר אתכם לתוכנית", "url": None}
        if last and last.is_submitted:
            return {"label": "לנסות שוב את מבחן הכניסה",
                    "hint": "קיבלתם משוב מפורט. אפשר לנסות שוב כמה פעמים שרוצים",
                    "url": reverse("matazim_test")}
        if last:
            return {"label": "להגיש את מבחן הכניסה",
                    "hint": "כבר קיבלתם דגם לבנות. נשאר להעלות אותו",
                    "url": reverse("matazim_test")}
        if tinkercad and tinkercad["p"]["completed"]:
            return {"label": "מוכנים למבחן הכניסה",
                    "hint": "סיימתם טינקרקאד. עכשיו תקבלו דגם לבנות",
                    "url": reverse("matazim_test")}
        if tinkercad:
            done, total = tinkercad["p"]["done"], tinkercad["p"]["total"]
            return {
                "label": "ללמוד טינקרקאד",
                "hint": (f"{done} מתוך {total} שיעורים. בסיום תקבלו את משימת "
                         f"מבחן הכניסה"),
                "url": reverse("courses_detail", args=[tinkercad["course"].slug]),
            }
        return {"label": "מבחן הכניסה", "hint": "משימת בנייה בטינקרקאד",
                "url": reverse("matazim_test")}
    if status == ProgramMembership.IN_TRAINING:
        pending = record["in_progress"] or record["not_started"]
        if pending:
            c = pending[0]["course"]
            return {
                "label": f"להמשיך: {c.title}",
                "hint": f"{pending[0]['p']['done']} מתוך {pending[0]['p']['total']} שיעורים",
                "url": reverse("courses_detail", args=[c.slug]),
            }
        return {"label": "להגיש תוצר",
                "hint": "סיימתם את ההדרכות. הגיע הזמן לבנות משהו משלכם", "url": None}
    if status == ProgramMembership.PROJECT_SUBMITTED:
        return {"label": "התוצר שלכם בבדיקה", "hint": "המוביל של בית הספר יחזור אליכם", "url": None}
    if status == ProgramMembership.CERTIFIED:
        return {"label": "להדריך", "hint": "בחרו פלייליסט והתחילו קבוצה", "url": None}
    return None


# ---------------------------------------------------------------------------
# Public pages (REQ-10.3)
# ---------------------------------------------------------------------------

def matazim_home(request):
    program = get_program()
    return render(request, "app/matazim/home.html", {
        **shell_ctx(request, program, "home"),
        "schools": School.objects.filter(program=program, is_active=True)[:8],
        "school_count": School.objects.filter(program=program, is_active=True).count(),
        "course_count": program_courses(program).count(),
        "stages": [
            {"key": "applied", "label": "מתמיינים",
             "text": "נרשמים, לומדים טינקרקאד, ובונים דגם במבחן הכניסה. "
                     "המבחן בודק רצינות, לא כישרון."},
            {"key": "in_training", "label": "לומדים",
             "text": "הדרכות טכנולוגיות באתר, בקצב שלכם, עם מעקב התקדמות."},
            {"key": "project_submitted", "label": "יוצרים",
             "text": "בונים פרויקט משלכם ומגישים אותו למוביל בית הספר."},
            {"key": "certified", "label": "מדריכים",
             "text": "מקבלים הסמכה, פותחים קבוצה ומלמדים ילדים צעירים מכם."},
            {"key": "impact", "label": "משפיעים",
             "text": "הידע שלכם עובר הלאה. זו כל המטרה."},
        ],
    })


def matazim_track(request):
    """המסלול השנתי. Public as a recruitment page; shows your own position on the
    path when you are a member (REQ-10.3 + REQ-10.4)."""
    program = get_program()
    membership = get_membership(request.user, program)
    return render(request, "app/matazim/track.html", {
        **shell_ctx(request, program, "track"),
        "steps": membership.track_steps() if membership else [
            {"key": k, "label": lbl, "done": False, "current": False}
            for k, lbl in ProgramMembership.STAGE_LABELS.items()
        ],
        "courses": program_courses(program),
    })


def matazim_help(request):
    """REQ-10.20a - what is expected of a student, and of a school leader.

    Public: a teenager opening their teacher's invite link should be able to
    read what they are signing up for before signing up, and a newly assigned
    school leader gets their whole onboarding here, since nobody is going to
    train forty teachers one at a time.
    """
    program = get_program()
    return render(request, "app/matazim/help.html",
                  shell_ctx(request, program, "help"))


def matazim_schools(request):
    program = get_program()
    return render(request, "app/matazim/schools.html", {
        **shell_ctx(request, program, "schools"),
        "schools": School.objects.filter(program=program, is_active=True).order_by("city", "name"),
    })


# ---------------------------------------------------------------------------
# Members only (REQ-10.14)
# ---------------------------------------------------------------------------

@program_member_required
def matazim_me(request, program, membership):
    """אזור אישי - the only daily reason to open /matazim, so it answers the
    four questions at a glance and nothing else competes for attention."""
    record = training_record(request.user, program)
    return render(request, "app/matazim/me.html", {
        **shell_ctx(request, program, "me"),
        "steps": membership.track_steps(),
        "record": record,
        "next_step": next_step(membership, record),
    })


# ---------------------------------------------------------------------------
# Consoles: one school view, two audiences (REQ-10.16 / REQ-10.17)
# ---------------------------------------------------------------------------

def roster(program, school):
    """Every מט״צ attached to a school, with their derived training record.

    Cohort-sized (a handful per school), so a per-member query is fine and no
    aggregation machinery is warranted.
    """
    rows = []
    memberships = (ProgramMembership.objects
                   .filter(program=program, school=school)
                   .select_related("user", "user__profile", "school")
                   .order_by("school_join_status", "status"))
    for m in memberships:
        rec = training_record(m.user, program)
        rows.append({"m": m, "record": rec})
    return rows


def school_stats(program, school):
    """Aggregate-only figures for a school: **numbers, never people**.

    This is what anyone gets to see (Avi, 2026-08-08). Names, statuses and
    per-person progress are for that school's leader and for program staff.
    Computed with aggregate queries rather than by walking the roster, so the
    public page cannot be used to time how many members a school has, and so it
    stays cheap on a page anyone can hit.
    """
    from django.db.models import Count

    from .models import CourseCertificate, Enrollment

    member_ids = list(
        ProgramMembership.objects
        .filter(program=program, school=school,
                school_join_status=ProgramMembership.SCHOOL_CONFIRMED)
        .values_list("user_id", flat=True))
    course_ids = list(program_courses(program).values_list("id", flat=True))
    certified = (ProgramMembership.objects
                 .filter(program=program, school=school,
                         status=ProgramMembership.CERTIFIED).count())
    completed = (Enrollment.objects
                 .filter(user_id__in=member_ids, course_id__in=course_ids,
                         completed_at__isnull=False).count()) if member_ids else 0
    certs = (CourseCertificate.objects
             .filter(user_id__in=member_ids, course_id__in=course_ids)
             .aggregate(n=Count("id"))["n"]) if member_ids else 0
    return {
        "members": len(member_ids),
        "certified": certified,
        "courses_completed": completed,
        "certificates": certs,
        "leaders": school.leaders.count(),
    }


def _log_status(membership, to_status, actor, note=""):
    """Append-only audit (REQ-10.8). Every status change goes through here."""
    from_status = membership.status
    membership.status = to_status
    membership.save(update_fields=["status", "updated_at"])
    ProgramStatusLog.objects.create(
        membership=membership, from_status=from_status, to_status=to_status,
        actor=actor, note=note)


@program_staff_required
def matazim_admin(request, program):
    """The matazim admin console: all schools, who leads them, and oversight of
    the grants the school owners have made (DEC-83)."""
    schools = list(School.objects.filter(program=program)
                   .prefetch_related("leaders", "memberships"))
    school_rows = []
    for s in schools:
        ms = list(s.memberships.all())
        school_rows.append({
            "school": s,
            "leaders": list(s.leaders.all()),
            "total": len(ms),
            "certified": sum(1 for m in ms if m.status == ProgramMembership.CERTIFIED),
            "pending_join": sum(1 for m in ms
                                if m.school_join_status == ProgramMembership.SCHOOL_PENDING),
        })
    # Oversight, not a queue: the grants happen in the schools now (DEC-83), so
    # what staff need here is visibility over what was granted and by whom, plus
    # the power to undo it.
    recent = (ProgramMembership.objects
              .filter(program=program, status=ProgramMembership.CERTIFIED)
              .select_related("user", "user__profile", "school", "certified_by")
              .order_by("-certified_at")[:20])
    return render(request, "app/matazim/admin.html", {
        **shell_ctx(request, program, "admin"),
        "school_rows": school_rows,
        "recent_certifications": recent,
        "unassigned": ProgramMembership.objects.filter(program=program, school__isnull=True)
                      .select_related("user", "user__profile"),
    })


def matazim_school(request, school_id):
    """A school page with **two levels of detail**, chosen by who is asking.

    Anyone may open any school and see its numbers: how many מט״צים, how many
    certified, how much has been learned. Nobody's name, status or progress
    appears (Avi, 2026-08-08).

    That school's leader, and program staff, additionally get the roster and the
    controls. `can_manage` gates the whole difference, and every write endpoint
    re-checks it independently: this view widening does not widen those.
    """
    program = get_program()
    school = get_object_or_404(School, pk=school_id, program=program)
    can_manage = (request.user.is_authenticated
                  and can_view_school(request.user, school))
    ctx = {
        **shell_ctx(request, program, "school"),
        "school": school,
        "can_manage": can_manage,
        "stats": school_stats(program, school),
    }
    if can_manage:
        ctx["join_url"] = school_join_url(request, school)
        rows = roster(program, school)
        ctx["rows"] = [r for r in rows
                       if r["m"].school_join_status == ProgramMembership.SCHOOL_CONFIRMED]
        ctx["pending"] = [r for r in rows
                          if r["m"].school_join_status == ProgramMembership.SCHOOL_PENDING]
    return render(request, "app/matazim/school.html", ctx)


@program_staff_required
def matazim_user_search(request, program):
    """Find any babook member, so program staff never need the Django admin to
    look somebody up before making them a school leader.

    Program staff only. Deliberately narrow: it matches on email so a teacher
    can hand over their address, but it **never returns one**, so this cannot be
    turned into an export of the site's email list. Name and username are enough
    to identify a person you are about to hand a school to.
    """
    from django.contrib.auth.models import User
    from django.db.models import Q
    from django.http import JsonResponse

    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    users = (User.objects.filter(is_active=True)
             .filter(Q(username__icontains=q)
                     | Q(email__iexact=q)
                     | Q(first_name__icontains=q)
                     | Q(last_name__icontains=q)
                     | Q(profile__display_name__icontains=q))
             .select_related("profile")
             .distinct()[:15])
    led = {s.pk: s.name for s in School.objects.filter(program=program)}
    return JsonResponse({"results": [
        {
            "id": u.pk,
            "username": u.username,
            "name": u.profile.public_name if hasattr(u, "profile") else u.username,
            "leads": [led[s.pk] for s in u.schools_led.all() if s.pk in led],
        }
        for u in users
    ]})


@require_POST
@program_staff_required
def matazim_school_create(request, program):
    """Opening a school is a **staff-only** action (Avi, 2026-08-08)."""
    name = (request.POST.get("name") or "").strip()
    city = (request.POST.get("city") or "").strip()
    if not name:
        messages.error(request, "צריך שם לבית הספר.")
        return redirect("matazim_admin")
    school, created = School.objects.get_or_create(
        program=program, name=name, defaults={"city": city})
    messages.success(request, f"בית הספר {school.name} " + ("נפתח." if created else "כבר קיים."))
    return redirect("matazim_school", school_id=school.pk)


@require_POST
@program_staff_required
def matazim_leader_assign(request, program, school_id):
    """Assign or remove a teacher as this school's leader. Staff only."""
    from django.contrib.auth.models import User

    school = get_object_or_404(School, pk=school_id, program=program)
    remove_id = request.POST.get("remove")
    if remove_id:
        school.leaders.remove(get_object_or_404(User, pk=remove_id))
        messages.success(request, "המוביל הוסר מבית הספר.")
        return redirect("matazim_school", school_id=school.pk)
    # `user_id` comes from the picker; `identifier` is the typed fallback, so the
    # form still works with JS off.
    user = None
    if request.POST.get("user_id"):
        user = User.objects.filter(pk=request.POST["user_id"], is_active=True).first()
    if user is None:
        ident = (request.POST.get("identifier") or "").strip()
        user = (User.objects.filter(email__iexact=ident).first()
                or User.objects.filter(username__iexact=ident).first())
    if not user:
        messages.error(request, "לא נמצא משתמש.")
    else:
        school.leaders.add(user)
        messages.success(
            request, f"{user.profile.public_name} מוביל עכשיו את {school.name}.")
    return redirect("matazim_school", school_id=school.pk)


@require_POST
def matazim_confirm_member(request, membership_id):
    """The leader confirms a teen onto their school's roster.

    The member picked the school; it only counts once the leader says yes
    (closes ACT-33).
    """
    program = get_program()
    m = get_object_or_404(ProgramMembership.objects.select_related("school"),
                          pk=membership_id, program=program)
    if not m.school or not can_view_school(request.user, m.school):
        raise Http404("Not a leader of this school")
    if request.POST.get("decline"):
        m.school = None
        m.school_join_status = ProgramMembership.SCHOOL_PENDING
        m.save(update_fields=["school", "school_join_status", "updated_at"])
        messages.success(request, "הבקשה נדחתה.")
        return redirect("matazim_admin" if is_program_staff(request.user, program)
                        else "matazim_home")
    m.school_join_status = ProgramMembership.SCHOOL_CONFIRMED
    m.save(update_fields=["school_join_status", "updated_at"])
    messages.success(request, f"{m.user.profile.public_name} נוסף לרשימה.")
    return redirect("matazim_school", school_id=m.school_id)


# ---------------------------------------------------------------------------
# Applying (REQ-10.4) — two doors into the program
#
#   1. the school's own invite link, handed out by its teacher. The teen lands
#      already attached to that school; the teacher gave them the link, so the
#      school assignment is settled and needs no second confirmation (DEC-84).
#   2. the open form, where they pick a school from the list and its leader
#      confirms them onto the roster (DEC-77).
#
# Both end at status APPLIED. Getting *in* is still level 1, and still the
# school owner's to grant (DEC-83).
#
# New-vs-existing user is not handled here at all: a logged-out visitor is sent
# through the existing `/join/` wall with `?next=` pointing back, and REQ-5.4's
# return-to-intent drops them back on this exact page afterwards, freshly
# registered or freshly logged in. Same machinery Chapter 9 joins run on.
# ---------------------------------------------------------------------------

def school_join_url(request, school):
    return request.build_absolute_uri(
        reverse("matazim_join", args=[school.join_code]))


def matazim_join(request, code):
    """Land on a school's invite link and apply to the program."""
    program = get_program()
    school = get_object_or_404(School, join_code=code, program=program)
    here = reverse("matazim_join", args=[code])

    if not request.user.is_authenticated:
        # A landing page rather than a bounce, so the link previews nicely when
        # a teacher drops it in a WhatsApp group (same reason Chapter 9 does it).
        return render(request, "app/matazim/join_landing.html", {
            "program": program, "school": school,
            "join_next": f"{reverse('join_wall')}?next={here}",
            "page_url": request.build_absolute_uri(here),
        })

    existing = get_membership(request.user, program)
    if existing:
        messages.info(request, "אתם כבר רשומים לתוכנית.")
        return redirect("matazim_me")
    if not school.is_open:
        messages.error(request, "בית הספר סגור להרשמה כרגע.")
        return redirect("matazim_home")

    if request.method == "POST":
        m = ProgramMembership.objects.create(
            user=request.user, program=program, school=school,
            cohort_year=program.current_cohort_year,
            status=ProgramMembership.APPLIED,
            # Arrived through the school's own door: no confirmation needed.
            school_join_status=ProgramMembership.SCHOOL_CONFIRMED)
        ProgramApplication.objects.create(
            membership=m,
            grade=(request.POST.get("grade") or "").strip()[:40],
            motivation=(request.POST.get("motivation") or "").strip(),
            built_before=(request.POST.get("built_before") or "").strip(),
            via_invite_link=True)
        _log_status(m, ProgramMembership.APPLIED, request.user,
                    f"נרשם דרך הקישור של {school.name}")
        messages.success(request, f"נרשמתם! {school.name} יאשרו אתכם בקרוב.")
        return redirect("matazim_me")

    return render(request, "app/matazim/apply.html", {
        **shell_ctx(request, program, "apply"),
        "school": school, "via_link": True,
    })


def matazim_apply(request):
    """The open door: pick a school, its leader confirms you onto the roster."""
    program = get_program()
    if not request.user.is_authenticated:
        return redirect(f"{reverse('join_wall')}?next={reverse('matazim_apply')}")
    if get_membership(request.user, program):
        return redirect("matazim_me")

    schools = School.objects.filter(program=program, is_active=True, is_open=True)
    if request.method == "POST":
        school = schools.filter(pk=request.POST.get("school_id")).first()
        if not school:
            messages.error(request, "צריך לבחור בית ספר.")
            return redirect("matazim_apply")
        m = ProgramMembership.objects.create(
            user=request.user, program=program, school=school,
            cohort_year=program.current_cohort_year,
            status=ProgramMembership.APPLIED,
            # Chose the school themselves, so its leader confirms (DEC-77).
            school_join_status=ProgramMembership.SCHOOL_PENDING)
        ProgramApplication.objects.create(
            membership=m,
            grade=(request.POST.get("grade") or "").strip()[:40],
            motivation=(request.POST.get("motivation") or "").strip(),
            built_before=(request.POST.get("built_before") or "").strip())
        _log_status(m, ProgramMembership.APPLIED, request.user,
                    f"נרשם ובחר את {school.name}")
        messages.success(request, f"נרשמתם! {school.name} יאשרו אתכם בקרוב.")
        return redirect("matazim_me")

    return render(request, "app/matazim/apply.html", {
        **shell_ctx(request, program, "apply"),
        "schools": schools, "via_link": False,
    })


# ---------------------------------------------------------------------------
# מבחן הכניסה (§10.7)
# ---------------------------------------------------------------------------

def _assign_target(membership):
    """Hand out a target, avoiding any this applicant has already been given so
    a retry is a fresh build rather than another go at the same object."""
    ids = available_target_ids()
    if not ids:
        return None
    used = set(membership.entrance_attempts.values_list("target_id", flat=True))
    pool = [i for i in ids if i not in used] or ids
    # Deterministic per applicant and attempt: reload the page and you get the
    # same object back, rather than a new one every refresh.
    n = membership.entrance_attempts.count()
    idx = (membership.pk * 7919 + n * 104729) % len(pool)
    return pool[idx]


def current_attempt(membership, create=True):
    """The attempt in play: the latest unsubmitted one, or a new one."""
    open_attempt = membership.entrance_attempts.filter(
        submitted_at__isnull=True).first()
    if open_attempt or not create:
        return open_attempt
    target_id = _assign_target(membership)
    if not target_id:
        return None
    return EntranceAttempt.objects.create(
        membership=membership, target_id=target_id,
        number=membership.entrance_attempts.count() + 1)


@program_member_required
def matazim_test(request, program, membership):
    """Show the assigned target and take the upload.

    Deliberately reachable at any point after applying, so nobody has to
    discover that a test exists.
    """
    if membership.status != ProgramMembership.APPLIED:
        messages.info(request, "כבר עברתם את שלב מבחן הכניסה.")
        return redirect("matazim_me")

    attempt = current_attempt(membership)
    if attempt is None:
        messages.error(request, "משימות המבחן עוד לא הוגדרו. פנו לצוות התוכנית.")
        return redirect("matazim_me")
    target = load_target(attempt.target_id)

    if request.method == "POST" and request.FILES.get("model"):
        upload = request.FILES["model"]
        if upload.size > 20 * 1024 * 1024:
            messages.error(request, "הקובץ גדול מדי. עד 20MB.")
            return redirect("matazim_test")
        data = upload.read()
        passed, issues, measured = check(data, target)

        attempt.model_file.save(f"{membership.pk}_{attempt.number}.stl",
                                ContentFile(data), save=False)
        attempt.measured, attempt.issues, attempt.passed = measured, issues, passed
        attempt.submitted_at = timezone.now()
        attempt.save()
        return redirect("matazim_test_result", attempt_id=attempt.pk)

    return render(request, "app/matazim/test.html", {
        **shell_ctx(request, program, "test"),
        "attempt": attempt,
        "target": target,
        "history": membership.entrance_attempts.filter(submitted_at__isnull=False),
    })


@program_member_required
def matazim_test_result(request, program, membership, attempt_id):
    attempt = get_object_or_404(EntranceAttempt, pk=attempt_id, membership=membership)
    return render(request, "app/matazim/test_result.html", {
        **shell_ctx(request, program, "test"),
        "attempt": attempt,
        "target": load_target(attempt.target_id),
        "headline": encouragement(attempt.issues, attempt.number),
    })


@require_POST
@program_member_required
def matazim_test_retry(request, program, membership):
    """A fresh target, and no limit on how often (REQ-10.28)."""
    if membership.entrance_attempts.filter(submitted_at__isnull=True).exists():
        return redirect("matazim_test")
    target_id = _assign_target(membership)
    if target_id:
        EntranceAttempt.objects.create(
            membership=membership, target_id=target_id,
            number=membership.entrance_attempts.count() + 1)
    return redirect("matazim_test")


@require_POST
@program_staff_required
def matazim_rotate_code(request, program, school_id):
    """Rotate a school's invite link. Staff only, because it invalidates every
    copy of the old link already out in the world."""
    school = get_object_or_404(School, pk=school_id, program=program)
    school.join_code = gen_join_code()
    school.save(update_fields=["join_code"])
    messages.success(request, "נוצר קישור חדש. הקישור הקודם כבר לא עובד.")
    return redirect("matazim_school", school_id=school.pk)


def matazim_school_qr(request, school_id):
    """QR PNG of a school's invite link, for handing out in class."""
    import io

    import qrcode
    from django.http import HttpResponse

    program = get_program()
    school = get_object_or_404(School, pk=school_id, program=program)
    if not request.user.is_authenticated or not can_view_school(request.user, school):
        raise Http404("Not a leader of this school")
    img = qrcode.make(school_join_url(request, school), box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


def _grantable(request, membership_id):
    """A membership this user may grant a level to: they must lead that person's
    school (program staff lead every school).

    The scope check is on the **member's own school**, so a leader of school A
    can never touch a member of school B even by posting their id directly.
    """
    program = get_program()
    m = get_object_or_404(
        ProgramMembership.objects.select_related("school", "user", "user__profile"),
        pk=membership_id, program=program)
    if not m.school or not can_view_school(request.user, m.school):
        raise Http404("Not a leader of this member's school")
    return program, m


@require_POST
def matazim_accept(request, membership_id):
    """**Level 1** - accept an applicant into the program (DEC-83).

    Granted by the school owner. This is the gate the entrance test feeds: once
    §10.7 is built, passing it is what puts the applicant in front of this
    button. Until then the owner decides on their own judgement, which is why
    the note is worth recording.
    """
    program, m = _grantable(request, membership_id)
    note = (request.POST.get("note") or "").strip()[:300]
    if request.POST.get("reject"):
        _log_status(m, ProgramMembership.REJECTED, request.user, note)
        messages.success(request, f"{m.user.profile.public_name} לא התקבל לתוכנית.")
        return redirect("matazim_school", school_id=m.school_id)
    if not m.can_be_accepted:
        messages.error(request, "המט״צ כבר התקבל לתוכנית.")
        return redirect("matazim_school", school_id=m.school_id)
    _log_status(m, ProgramMembership.IN_TRAINING, request.user, note)
    m.accepted_at = timezone.now()
    m.accepted_by = request.user
    m.acceptance_note = note
    m.save(update_fields=["accepted_at", "accepted_by", "acceptance_note", "updated_at"])
    messages.success(request, f"{m.user.profile.public_name} התקבל לתוכנית.")
    return redirect("matazim_school", school_id=m.school_id)


@require_POST
def matazim_certify(request, membership_id):
    """**Level 2** - grant the מט״צ status (DEC-83).

    Granted by the school owner, by hand, with a required note. Program staff can
    do it too, since they lead every school.

    Note what this does NOT do: it touches no permission, no `is_teacher` flag,
    nothing on babook (DEC-69). Certification is a status, not a capability.
    """
    program, m = _grantable(request, membership_id)
    note = (request.POST.get("note") or "").strip()
    if not m.can_be_certified:
        messages.error(request, "לא ניתן להסמיך בשלב הזה.")
        return redirect("matazim_school", school_id=m.school_id)
    if not note:
        messages.error(request, "הסמכה מחייבת נימוק. זו הסיבה שהיא נדירה.")
        return redirect("matazim_school", school_id=m.school_id)
    _log_status(m, ProgramMembership.CERTIFIED, request.user, note)
    m.certified_at = timezone.now()
    m.certified_by = request.user
    m.certification_note = note
    m.save(update_fields=["certified_at", "certified_by", "certification_note",
                          "updated_at"])
    messages.success(request, f"{m.user.profile.public_name} הוסמך כמט״צ.")
    return redirect("matazim_school", school_id=m.school_id)


@require_POST
@program_staff_required
def matazim_revoke(request, program, membership_id):
    """Undo a grant. **Program staff only** - this is the oversight that stays
    with Avi and Litala now that the grants themselves have moved to the schools
    (DEC-83). A note is required, and the original grant is never erased: the
    trail of who gave it survives revocation (REQ-10.9)."""
    m = get_object_or_404(
        ProgramMembership.objects.select_related("user", "user__profile"),
        pk=membership_id, program=program)
    note = (request.POST.get("note") or "").strip()
    if not note:
        messages.error(request, "ביטול הסמכה מחייב נימוק.")
        return redirect("matazim_admin")
    _log_status(m, ProgramMembership.REVOKED, request.user, note)
    messages.success(request, f"ההסמכה של {m.user.profile.public_name} בוטלה.")
    return redirect("matazim_admin")
