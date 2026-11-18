"""בוגרי מטצים: the space for last year's graduates (SPR-M.84, REQ-M.216 to REQ-M.221).

Lital, 2026-11-17: tenth-graders who finished the programme and now teach in the
schools get a button of their own, "בוגרי מטצים". In her order:

1. **Joining.** They get a link, and on the first visit give their details, choose
   their school and their leader from a list, and a parent approves with a
   signature. The leader then approves them (REQ-M.216).
2. **The welcome**, in her words (REQ-M.216).
3. **The space**: all the programme's הדרכות again for review (REQ-M.217), לומדים
   AI and איך מעבירים שיעור with the teaching kit she attached (REQ-M.218), the
   practicum towards 120 hours, each report approved by the leader (REQ-M.219),
   and the two peak days (REQ-M.220).
4. **Follow-up**: the leader sees their graduates, approves joining and hours,
   and follows their progress; the programme team sees everybody, by school and
   by leader, with the parents' approval, progress and hours (REQ-M.221).

A graduate is not a learner at a stage (`gate.learner_stage` is None for them),
so nothing here sends them to this year's entrance test.
"""

import base64
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db.models import Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from . import access
from .models import (
    Graduate,
    GraduateAttendance,
    GraduateCourseApproval,
    GraduateDate,
    GraduateMeeting,
    GraduateResource,
    Notification,
    PracticumReport,
    School,
    Student,
)
from .notify import notify
from .views import member_profile, shell

LOGIN_URL = "/matazim/login/"

TARGET_HOURS = 120

KIT_PATH = Path(__file__).resolve().parent / "files" / "good_teaching_kit.pdf"

WELCOME_TITLE = "ברוכים הבאים לנבחרת בוגרי מטצים!"
WELCOME_TEXT = (
    "סיימתם את התכנית, רכשתם ידע וכלים, ועכשיו אתם ממשיכים לשלב הבא: מדריכים "
    "ומשפיעים בבתי הספר שלכם. במרחב הזה תוכלו לחזור להדרכות, ללמוד תכנים חדשים, "
    "לקבל כלים להדרכה ולעקוב אחר שעות הפרקטיקום שלכם. שמחים להמשיך לצעוד איתכם!"
)

SIGNATURE_PREFIX = "data:image/png;base64,"
SIGNATURE_MAX = 300_000


def clean_signature(raw):
    """A drawn signature as a PNG data URL, or "" when it is not one.

    Checked here because it is put back into a page as an image source: only a
    real PNG, of a sane size, under the one prefix, is kept.
    """
    raw = (raw or "").strip()
    if not raw.startswith(SIGNATURE_PREFIX) or len(raw) > SIGNATURE_MAX:
        return ""
    try:
        data = base64.b64decode(raw[len(SIGNATURE_PREFIX):], validate=True)
    except (ValueError, TypeError):
        return ""
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 67:
        return ""
    return raw


def leaders_to_choose():
    """Approved, active leaders, with the schools they are at, for the list."""
    rows = []
    for leader in (
        access.joinable_leaders().filter(approved_at__isnull=False)
        .select_related("user", "user__profile").prefetch_related("classes")
    ):
        rows.append({
            "leader": leader,
            "name": _name(leader.user),
            "schools": access.leader_schools(leader),
        })
    rows.sort(key=lambda r: r["name"])
    return rows


def _name(user):
    from .certification import _display_name

    return _display_name(user)


def hours_of(graduate):
    """{approved, waiting, left, pct} in hours, for one graduate."""
    sums = {
        row["status"]: row["total"] or Decimal("0")
        for row in graduate.reports.values("status").annotate(total=Sum("hours"))
    }
    approved = sums.get(PracticumReport.APPROVED, Decimal("0"))
    waiting = sums.get(PracticumReport.WAITING, Decimal("0"))
    left = max(Decimal(TARGET_HOURS) - approved, Decimal("0"))
    pct = min(int(approved / TARGET_HOURS * 100), 100)
    return {"approved": _num(approved), "waiting": _num(waiting), "left": _num(left),
            "pct": pct, "target": TARGET_HOURS}


def _num(value):
    """12.0 reads as 12, 2.5 stays 2.5."""
    value = Decimal(value).normalize()
    return int(value) if value == value.to_integral_value() else float(value)


def _course_slugs():
    from .content import REQUIRED_COURSE_SLUGS

    return sorted(set(REQUIRED_COURSE_SLUGS) | access.shelvable_slugs())


def progress_rows(graduates):
    """{user_id: summary} over all the programme's הדרכות, in a fixed number of queries."""
    from .progress import track_summary

    return {uid: track_summary(rows) for uid, rows in _per_course(graduates).items()}


def _per_course(graduates):
    """{user_id: {slug: {pct, done, total}}} for these graduates, in a fixed number of queries."""
    from .progress import JustAUser, cohort_progress

    people = [JustAUser(g.user_id) for g in graduates]
    return cohort_progress(people, _course_slugs()) if people else {}


def _finished_slugs(rows):
    return {slug for slug, row in (rows or {}).items() if int(row.get("pct") or 0) >= 100}


def _approved_slugs(graduate):
    return set(graduate.course_approvals.values_list("course_slug", flat=True))


def year_track(graduate, user):
    """SPR-M.88, REQ-M.226 - the yearly track's meetings, each confirmed by the leader or not.

    `graduate` None is the team's preview: every meeting reads as not yet confirmed.
    """
    meetings = list(access.visible_graduate_meetings(user))
    confirmed = set()
    if graduate is not None:
        confirmed = set(graduate.attendance.values_list("meeting_id", flat=True))
    return [{"meeting": m, "confirmed": m.pk in confirmed} for m in meetings]


def _courses_for(user):
    """The graduate's list: every הדרכה of the programme that exists, with progress."""
    from app.models import Course

    from .progress import JustAUser, cohort_progress

    slugs = [s for s in _course_slugs() if s in access.visible_course_slugs(user)]
    per = cohort_progress([JustAUser(user.id)], slugs).get(user.id, {})
    titles = dict(Course.objects.filter(slug__in=slugs).values_list("slug", "title"))
    rows = []
    for slug in slugs:
        if slug not in titles:
            continue
        row = per.get(slug) or {}
        rows.append({"slug": slug, "title": titles[slug] or slug, "pct": row.get("pct", 0)})
    rows.sort(key=lambda r: r["title"])
    return rows


def _is_staff(user):
    return access.is_program_manager(user)


def _course_cards(user, zero=False):
    """SPR-M.87, REQ-M.224 - the הדרכות as cards (`_course_card.html`), cover and ring.

    Lital, 2026-11-17 21:05: "בוא נעשה לה גם ריבועים עם הדרכות", with all of them
    in it (spec C46). `zero` is the team's preview: every הדרכה of the programme at 0%.
    """
    from app.models import Course

    from .progress import JustAUser, cohort_progress

    slugs = _course_slugs()
    approved = set()
    if not zero:
        slugs = [s for s in slugs if s in access.visible_course_slugs(user)]
        per = cohort_progress([JustAUser(user.id)], slugs).get(user.id, {})
        graduate = access.graduate_of(user)
        if graduate is not None:
            approved = _approved_slugs(graduate)
    else:
        per = {}
    cards = []
    for c in Course.objects.filter(slug__in=slugs):
        pct = int((per.get(c.slug) or {}).get("pct") or 0)
        done = pct >= 100
        if done:
            # REQ-M.227 - a finished הדרכה counts once the leader approves it.
            word = "הושלמה ואושרה" if c.slug in approved else "הושלמה, מחכה לאישור המוביל/ה"
        else:
            word = "בתהליך" if pct else "מוכנה לחזרה"
        cards.append({
            "slug": c.slug,
            "title": c.title or c.slug,
            "thumbnail": c.thumbnail or "",
            "about": c.description or "",
            "pct": pct,
            "done": done,
            "locked": False,
            "exists": True,
            "word": word,
            "action": "לחזור ולתרגל" if done else ("להמשיך" if pct else "לפתוח"),
        })
    cards.sort(key=lambda r: r["title"])
    return cards


def _space_reader(request):
    """Who reads a page inside the space: ("graduate", g), ("preview", None) or (None, None).

    An approved graduate reads it as theirs; the team and approved leaders read it
    as the preview (REQ-M.223), with nothing saved; anybody else goes back to the
    graduates' page.
    """
    graduate = access.graduate_of(request.user)
    if graduate is not None:
        return ("graduate", graduate) if graduate.is_approved else (None, None)
    if _may_see_as_graduate(request.user):
        return "preview", None
    return None, None


def _space_page(request, part, **ctx):
    mode, graduate = _space_reader(request)
    if mode is None:
        return redirect("matazim:graduates")
    return render(
        request,
        "matazim/graduates_part.html",
        shell(request, "graduates", part=part, graduate_preview=(mode == "preview"), **ctx),
    )


@login_required(login_url=LOGIN_URL)
def graduates_courses(request):
    """כל ההדרכות שלי: the cards, for review and practice (REQ-M.224)."""
    mode, _ = _space_reader(request)
    cards = _course_cards(request.user, zero=(mode == "preview")) if mode else []
    return _space_page(request, "courses", cards=cards)


@login_required(login_url=LOGIN_URL)
def graduates_teaching(request):
    """איך בונים הדרכה: the kit, and what the team added on the shelf (REQ-M.224)."""
    rows = [r for r in access.visible_graduate_resources(request.user) if r.section == GraduateResource.TEACHING]
    return _space_page(request, "teaching", rows=rows)


@login_required(login_url=LOGIN_URL)
def graduates_ai(request):
    """לומדים AI: the team's shelf (REQ-M.224)."""
    rows = [r for r in access.visible_graduate_resources(request.user) if r.section == GraduateResource.AI]
    return _space_page(request, "ai", rows=rows)


@login_required(login_url=LOGIN_URL)
def graduates_ask(request):
    """שואלים את ה AI: a builder for a good question about a הדרכה (REQ-M.225).

    Lital: "אשמח שאולי גם תעזור לבנות להם משהו... שאילת שאלות עם AI". The page
    puts a good question together in the browser, to copy into an AI tool. It
    sends nothing anywhere and keeps nothing: a teenager's words do not leave
    the page through us.
    """
    return _space_page(request, "ask")


# ------------------------------------------------------------------ the space


def graduates(request):
    """The button's page: the way in for a visitor, the space for a graduate."""
    user = request.user
    graduate = access.graduate_of(user)
    ctx = {"graduate": graduate, "welcome_title": WELCOME_TITLE, "welcome_text": WELCOME_TEXT}

    if graduate is None:
        ctx["is_leader_here"] = bool(access.leader_of(user))
        ctx["is_staff_here"] = _is_staff(user)
        ctx["may_see_as_graduate"] = _may_see_as_graduate(user)
        return render(request, "matazim/graduates.html", shell(request, "graduates", **ctx))

    ctx["leader_name"] = _name(graduate.leader.user) if graduate.leader_id else ""
    if graduate.is_approved:
        # REQ-M.222 - the space, dates included, opens only after the leader approves.
        ctx["dates"] = list(access.visible_graduate_dates(user))
        resources = list(access.visible_graduate_resources(user))
        courses = _courses_for(user)
        ctx.update(
            courses=courses,
            courses_done=sum(1 for c in courses if c["pct"] >= 100),
            ai=[r for r in resources if r.section == GraduateResource.AI],
            teaching=[r for r in resources if r.section == GraduateResource.TEACHING],
            hours=hours_of(graduate),
        )
    return render(request, "matazim/graduates.html", shell(request, "graduates", **ctx))


def graduates_process(request):
    """SPR-M.89, REQ-M.229 - the graduates' yearly process, open to anybody.

    Lital, 18.11: the letter to the grade 10 leaders links here, so the page is
    read by people who may not have an account yet.
    """
    return render(
        request,
        "matazim/graduates_process.html",
        shell(request, "graduates", target=TARGET_HOURS,
              is_graduate=access.graduate_of(request.user) is not None),
    )


def _may_see_as_graduate(user):
    """Root, a program manager or an approved leader (SPR-M.86, REQ-M.223)."""
    from .gate import MEMBER, preview_stages

    return MEMBER in preview_stages(user)


@login_required(login_url=LOGIN_URL)
def graduates_preview(request):
    """REQ-M.223 - the team sees the space as an approved graduate sees it.

    Lital, 2026-11-17 19:42: "תשלח לי לינק איך התלמיד רואה את האתר ברגע שנכנס".
    The space is shown only to an approved graduate, so the team had no way to see
    it. Read only: no Graduate row is made, the hours are a new graduate's (0 of
    120) and the practicum button does nothing.
    """
    user = request.user
    if not _may_see_as_graduate(user):
        raise PermissionDenied
    from types import SimpleNamespace

    from app.models import Course

    resources = list(access.visible_graduate_resources(user))
    slugs = _course_slugs()
    titles = dict(Course.objects.filter(slug__in=slugs).values_list("slug", "title"))
    courses = sorted(
        ({"slug": s, "title": titles[s] or s, "pct": 0} for s in slugs if s in titles),
        key=lambda r: r["title"],
    )
    zero = {"approved": 0, "waiting": 0, "left": TARGET_HOURS, "pct": 0, "target": TARGET_HOURS}
    ctx = {
        "graduate": SimpleNamespace(is_approved=True),
        "graduate_preview": True,
        "welcome_title": WELCOME_TITLE,
        "welcome_text": WELCOME_TEXT,
        "dates": list(access.visible_graduate_dates(user)),
        "courses": courses,
        "courses_done": 0,
        "ai":[r for r in resources if r.section == GraduateResource.AI],
        "teaching": [r for r in resources if r.section == GraduateResource.TEACHING],
        "hours": zero,
    }
    return render(request, "matazim/graduates.html", shell(request, "graduates", **ctx))


@login_required(login_url=LOGIN_URL)
def graduates_join(request):
    """First visit: details, school, leader, and a parent's signature (REQ-M.216)."""
    user = request.user
    if access.graduate_of(user) is not None:
        return redirect("matazim:graduates")
    if access.leader_of(user) or access.candidate_of(user) or _is_staff(user):
        return redirect("matazim:graduates")

    profile = member_profile(user)
    error = ""
    posted = request.POST if request.method == "POST" else None

    if Student.objects.filter(user=user).exists():
        error = "החשבון הזה רשום לתכנית השנה. בוגרים נרשמים עם חשבון משלהם."
    elif request.method == "POST":
        full_name = (posted.get("full_name") or "").strip()[:150]
        raw_school = posted.get("school") or ""
        school = School.objects.filter(pk=raw_school, is_active=True).first() if raw_school.isdigit() else None
        raw_leader = posted.get("leader") or ""
        leader = (
            access.joinable_leaders().filter(approved_at__isnull=False, pk=raw_leader).first()
            if raw_leader.isdigit() else None
        )
        guardian_name = (posted.get("guardian_name") or "").strip()[:150]
        guardian_email = (posted.get("guardian_email") or "").strip()
        signature = clean_signature(posted.get("signature"))
        try:
            validate_email(guardian_email)
            email_ok = True
        except ValidationError:
            email_ok = False

        if not full_name:
            error = "צריך שם מלא."
        elif school is None:
            error = "צריך לבחור בית ספר מהרשימה."
        elif leader is None:
            error = "צריך לבחור מורה מוביל/ה מהרשימה."
        elif not guardian_name or not email_ok:
            error = "צריך שם מלא ואימייל של ההורה."
        elif posted.get("guardian_consent") != "on":
            error = "צריך את אישור ההורה."
        elif not signature:
            error = "צריך חתימה של ההורה במסגרת."
        else:
            graduate = Graduate.objects.create(
                user=user, full_name=full_name, school=school, leader=leader,
                guardian_name=guardian_name, guardian_email=guardian_email,
                guardian_signature=signature, guardian_signed_at=timezone.now(),
            )
            notify(
                leader.user, Notification.GRADUATE_WAITING,
                # Mailed, so no name: a mail is a pointer (notify._mail).
                "בוגר/ת נרשם/ה לבוגרי מטצים ומחכה לאישור שלך.",
                url="/matazim/leader/graduates/", actor=user,
            )
            return redirect("matazim:graduates")

    return render(
        request,
        "matazim/graduates_join.html",
        shell(
            request, "graduates", error=error, posted=posted,
            schools=School.objects.filter(is_active=True),
            leaders=leaders_to_choose(),
            default_name=(getattr(getattr(user, "profile", None), "display_name", "") or ""),
            default_school=profile.school_id if profile else None,
            default_guardian_name=profile.guardian_name if profile else "",
            default_guardian_email=profile.guardian_email if profile else "",
        ),
    )


@login_required(login_url=LOGIN_URL)
def graduates_practicum(request):
    """הפרקטיקום שלי: report a session, see approved hours and what is left (REQ-M.219)."""
    graduate = access.graduate_of(request.user)
    if graduate is None:
        return redirect("matazim:graduates")
    if not graduate.is_approved:
        return redirect("matazim:graduates")

    error = ""
    posted = request.POST if request.method == "POST" else None
    if request.method == "POST":
        happened_on = parse_date(posted.get("happened_on") or "")
        place = (posted.get("place") or "").strip()[:200]
        topic = (posted.get("topic") or "").strip()[:200]
        insight = (posted.get("insight") or "").strip()
        try:
            hours = Decimal((posted.get("hours") or "").strip())
        except InvalidOperation:
            hours = None
        today = timezone.localdate()

        if happened_on is None:
            error = "צריך תאריך."
        elif happened_on > today:
            error = "אפשר לדווח רק על פעילות שכבר הייתה."
        elif not place or not topic:
            error = "צריך את מקום ההדרכה ואת הנושא."
        elif hours is None or hours <= 0 or hours > 12 or (hours * 2) != (hours * 2).to_integral_value():
            error = "מספר השעות הוא בין חצי שעה ל-12, בחצאי שעה."
        else:
            report = PracticumReport.objects.create(
                graduate=graduate, happened_on=happened_on, place=place, topic=topic,
                hours=hours, insight=insight,
            )
            if graduate.leader_id:
                notify(
                    graduate.leader.user, Notification.PRACTICUM_WAITING,
                    f"{graduate.full_name} דיווח/ה על {_num(report.hours)} שעות פרקטיקום.",
                    url="/matazim/leader/graduates/", actor=request.user,
                )
            return redirect("matazim:graduates_practicum")

    return render(
        request,
        "matazim/graduates_practicum.html",
        shell(
            request, "graduates", graduate=graduate, hours=hours_of(graduate),
            reports=list(graduate.reports.all()), error=error, posted=posted,
            today=timezone.localdate(), track=year_track(graduate, request.user),
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def practicum_delete(request, report_id):
    """A graduate takes back a report that was not approved yet."""
    graduate = access.graduate_of(request.user)
    if graduate is None:
        raise Http404
    report = get_object_or_404(PracticumReport, pk=report_id, graduate=graduate)
    if report.status == PracticumReport.APPROVED:
        raise PermissionDenied("דיווח שאושר נשאר.")
    report.delete()
    return redirect("matazim:graduates_practicum")


@login_required(login_url=LOGIN_URL)
def teaching_kit(request):
    """להדרכה טובה, לחצו כאן: the kit Lital attached, opened in the browser."""
    user = request.user
    if not (access.graduate_of(user) or access.leader_of(user) or _is_staff(user)):
        raise PermissionDenied
    if not KIT_PATH.exists():
        raise Http404
    response = FileResponse(open(KIT_PATH, "rb"), content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="good_teaching_kit.pdf"'
    return response


# ------------------------------------------------------------ the leader's view


def _graduate_cards(graduates, meetings=()):
    from app.models import Course
    from .progress import track_summary

    graduates = list(graduates)
    per = _per_course(graduates)
    titles = dict(Course.objects.filter(slug__in=_course_slugs()).values_list("slug", "title"))
    meeting_ids = {m.pk for m in meetings}
    cards = []
    for g in graduates:
        rows = per.get(g.user_id, {})
        approved = {a.course_slug for a in g.course_approvals.all()}
        to_approve = sorted(
            ({"slug": s, "title": titles.get(s) or s} for s in _finished_slugs(rows) - approved if s in titles),
            key=lambda r: r["title"],
        )
        cards.append({
            "g": g,
            "hours": hours_of(g),
            "progress": track_summary(rows) if rows else {"done": 0, "total": 0, "pct": 0},
            "leader_name": _name(g.leader.user) if g.leader_id else "",
            "waiting_reports": [r for r in g.reports.all() if r.status == PracticumReport.WAITING],
            # REQ-M.227 - finished הדרכות the leader has not approved yet.
            "courses_to_approve": to_approve,
            "courses_approved": len(approved),
            # REQ-M.226 - meetings of the yearly track the leader confirmed.
            "meetings_confirmed": sum(1 for a in g.attendance.all() if a.meeting_id in meeting_ids),
            "meetings_total": len(meeting_ids),
        })
    return cards


def _meeting_rows(meetings, cards):
    """For the leader's form: each meeting with the approved graduates, confirmed or not."""
    rows = []
    for m in meetings:
        people = []
        for card in cards:
            g = card["g"]
            if not g.is_approved:
                continue
            done = any(a.meeting_id == m.pk for a in g.attendance.all())
            people.append({"g": g, "confirmed": done})
        rows.append({
            "meeting": m,
            "people": people,
            "all_confirmed": bool(people) and all(p["confirmed"] for p in people),
            "confirmed": sum(1 for p in people if p["confirmed"]),
        })
    return rows


@login_required(login_url=LOGIN_URL)
def leader_graduates(request):
    """הבוגרים שלי: approve who joined, approve hours, follow progress (REQ-M.221)."""
    leader = access.leader_of(request.user)
    if leader is None:
        raise PermissionDenied
    rows = (
        Graduate.objects.filter(leader=leader)
        .select_related("school", "leader__user")
        .prefetch_related("reports", "attendance", "course_approvals")
    )
    meetings = list(access.visible_graduate_meetings(request.user))
    cards = _graduate_cards(rows, meetings)
    waiting = [c for c in cards if not c["g"].is_approved]
    approved = [c for c in cards if c["g"].is_approved]
    return render(
        request,
        "matazim/leader_graduates.html",
        shell(
            request, "leader", waiting=waiting, approved=approved,
            meeting_rows=_meeting_rows(meetings, cards),
        ),
    )


def _may_decide(user, graduate):
    """The graduate's own leader, or the programme team over their world."""
    leader = access.leader_of(user)
    if leader is not None and graduate.leader_id == leader.pk:
        return True
    return _is_staff(user) and access.visible_graduates(user).filter(pk=graduate.pk).exists()


def _back(request, default):
    nxt = request.POST.get("next") or ""
    return redirect(nxt if nxt in ("/matazim/staff/graduates/", "/matazim/leader/graduates/") else default)


@require_POST
@login_required(login_url=LOGIN_URL)
def graduate_approve(request, graduate_id):
    graduate = get_object_or_404(Graduate, pk=graduate_id)
    if not _may_decide(request.user, graduate):
        raise PermissionDenied
    if graduate.approved_at is None:
        graduate.approved_at = timezone.now()
        graduate.approved_by = request.user
        graduate.save(update_fields=["approved_at", "approved_by"])
        notify(
            graduate.user, Notification.GRADUATE_APPROVED,
            "ההצטרפות שלך לבוגרי מטצים אושרה. המרחב פתוח.",
            url="/matazim/graduates/", actor=request.user,
        )
    return _back(request, "matazim:leader_graduates")


@require_POST
@login_required(login_url=LOGIN_URL)
def report_decide(request, report_id):
    report = get_object_or_404(PracticumReport.objects.select_related("graduate"), pk=report_id)
    if not _may_decide(request.user, report.graduate):
        raise PermissionDenied
    action = request.POST.get("action")
    if action not in ("approve", "return"):
        raise PermissionDenied
    report.status = PracticumReport.APPROVED if action == "approve" else PracticumReport.RETURNED  # not-a-student-status: PracticumReport, a report's review
    report.decision_note = (request.POST.get("note") or "").strip()[:300] if action == "return" else ""
    report.decided_by = request.user
    report.decided_at = timezone.now()
    report.save(update_fields=["status", "decision_note", "decided_by", "decided_at"])
    word = "אושר" if action == "approve" else "הוחזר לתיקון"
    notify(
        report.graduate.user, Notification.PRACTICUM_DECIDED,
        f"הדיווח על {report.topic} ({_num(report.hours)} שעות) {word}.",
        url="/matazim/graduates/practicum/", actor=request.user,
    )
    return _back(request, "matazim:leader_graduates")


@require_POST
@login_required(login_url=LOGIN_URL)
def meeting_confirm(request, meeting_id):
    """REQ-M.226 - the leader confirms who took part in a meeting of the yearly track.

    `graduate` carries the ticked graduates; `undo` takes one confirmation back.
    Only approved graduates this person may decide on are touched; the rest of
    the posted ids are ignored.
    """
    meeting = get_object_or_404(access.visible_graduate_meetings(request.user), pk=meeting_id)
    undo = request.POST.get("undo") or ""
    if undo.isdigit():
        graduate = get_object_or_404(Graduate, pk=int(undo))
        if not _may_decide(request.user, graduate):
            raise PermissionDenied
        GraduateAttendance.objects.filter(meeting=meeting, graduate=graduate).delete()
        return _back(request, "matazim:leader_graduates")
    ids = [int(x) for x in request.POST.getlist("graduate") if x.isdigit()]
    for graduate in Graduate.objects.filter(pk__in=ids, approved_at__isnull=False):
        if _may_decide(request.user, graduate):
            GraduateAttendance.objects.get_or_create(
                meeting=meeting, graduate=graduate, defaults={"confirmed_by": request.user},
            )
    return _back(request, "matazim:leader_graduates")


@require_POST
@login_required(login_url=LOGIN_URL)
def course_approve(request, graduate_id):
    """REQ-M.227 - the leader approves a הדרכה the graduate finished."""
    graduate = get_object_or_404(Graduate, pk=graduate_id)
    if not _may_decide(request.user, graduate) or not graduate.is_approved:
        raise PermissionDenied
    slug = request.POST.get("slug") or ""
    if slug not in _finished_slugs(_per_course([graduate]).get(graduate.user_id)):
        raise PermissionDenied("אפשר לאשר רק הדרכה שהושלמה.")
    GraduateCourseApproval.objects.get_or_create(
        graduate=graduate, course_slug=slug, defaults={"approved_by": request.user},
    )
    return _back(request, "matazim:leader_graduates")


# ------------------------------------------------------------- the team's view


@login_required(login_url=LOGIN_URL)
def staff_graduates(request):
    """All graduates by school and leader, and the space's content (REQ-M.221)."""
    user = request.user
    if not _is_staff(user):
        raise PermissionDenied

    error = ""
    if request.method == "POST":
        error = _staff_edit(request)
        if not error:
            return redirect("matazim:staff_graduates")

    rows = (
        access.visible_graduates(user)
        .select_related("school", "leader__user", "leader__user__profile")
        .prefetch_related("reports", "attendance", "course_approvals")
    )
    meetings = list(access.visible_graduate_meetings(user))
    cards = _graduate_cards(rows, meetings)
    groups = {}
    for card in cards:
        g = card["g"]
        key = (g.school.name if g.school_id else "בלי בית ספר", card["leader_name"] or "בלי מוביל/ה")
        groups.setdefault(key, []).append(card)
    grouped = [
        {"school": school, "leader": leader, "cards": groups[(school, leader)]}
        for school, leader in sorted(groups)
    ]
    return render(
        request,
        "matazim/staff_graduates.html",
        shell(
            request, "staff", grouped=grouped, total=len(cards),
            approved=sum(1 for c in cards if c["g"].is_approved),
            dates=list(access.visible_graduate_dates(user)),
            resources=list(access.visible_graduate_resources(user)),
            sections=GraduateResource.SECTION_CHOICES, error=error,
            target=TARGET_HOURS, meeting_rows=_meeting_rows(meetings, cards),
            next_number=max((m.number for m in meetings), default=0) + 1,
        ),
    )


def _staff_edit(request):
    """One door for the team's edits on this screen. Returns an error, or ""."""
    user = request.user
    do = request.POST.get("do")
    world = access.institution_of(user)

    if do in ("add_date", "edit_date"):
        title = (request.POST.get("title") or "").strip()[:120]
        on = parse_date(request.POST.get("on") or "")
        if not title or on is None:
            return "ליום שיא צריך שם ותאריך."
        if do == "add_date":
            GraduateDate.objects.create(institution=world, title=title, on=on)
        else:
            row = get_object_or_404(access.visible_graduate_dates(user), pk=request.POST.get("id"))
            row.title, row.on = title, on
            row.save(update_fields=["title", "on"])
        return ""
    if do == "delete_date":
        get_object_or_404(access.visible_graduate_dates(user), pk=request.POST.get("id")).delete()
        return ""
    if do == "add_resource":
        section = request.POST.get("section")
        title = (request.POST.get("title") or "").strip()[:160]
        link = (request.POST.get("link") or "").strip()
        if section not in dict(GraduateResource.SECTION_CHOICES) or not title:
            return "לתוכן צריך כותרת ומקום."
        if link and not link.startswith(("https://", "http://")):
            return "קישור מתחיל ב-https://"
        GraduateResource.objects.create(
            institution=world, section=section, title=title, link=link[:200],
            about=(request.POST.get("about") or "").strip(), added_by=user,
        )
        return ""
    if do == "add_meeting":
        # REQ-M.226 - the next meeting of the graduates' yearly track.
        title = (request.POST.get("title") or "").strip()[:120]
        raw = (request.POST.get("number") or "").strip()
        if not title or not raw.isdigit() or not 0 < int(raw) < 1000:
            return "למפגש צריך מספר ונושא."
        GraduateMeeting.objects.create(
            institution=world, number=int(raw), title=title,
            on=parse_date(request.POST.get("on") or ""),
        )
        return ""
    if do == "delete_meeting":
        get_object_or_404(access.visible_graduate_meetings(user), pk=request.POST.get("id")).delete()
        return ""
    if do == "delete_resource":
        get_object_or_404(access.visible_graduate_resources(user), pk=request.POST.get("id")).delete()
        return ""
    raise PermissionDenied
