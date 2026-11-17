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
    GraduateDate,
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
    from .progress import JustAUser, cohort_progress, track_summary

    people = [JustAUser(g.user_id) for g in graduates]
    per_user = cohort_progress(people, _course_slugs()) if people else {}
    return {uid: track_summary(rows) for uid, rows in per_user.items()}


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


# ------------------------------------------------------------------ the space


def graduates(request):
    """The button's page: the way in for a visitor, the space for a graduate."""
    user = request.user
    graduate = access.graduate_of(user)
    ctx = {"graduate": graduate, "welcome_title": WELCOME_TITLE, "welcome_text": WELCOME_TEXT}

    if graduate is None:
        ctx["is_leader_here"] = bool(access.leader_of(user))
        ctx["is_staff_here"] = _is_staff(user)
        return render(request, "matazim/graduates.html", shell(request, "graduates", **ctx))

    ctx["dates"] = list(access.visible_graduate_dates(user))
    ctx["leader_name"] = _name(graduate.leader.user) if graduate.leader_id else ""
    if graduate.is_approved:
        resources = list(access.visible_graduate_resources(user))
        ctx.update(
            courses=_courses_for(user),
            ai=[r for r in resources if r.section == GraduateResource.AI],
            teaching=[r for r in resources if r.section == GraduateResource.TEACHING],
            hours=hours_of(graduate),
        )
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
            today=timezone.localdate(),
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


def _graduate_cards(graduates):
    graduates = list(graduates)
    progress = progress_rows(graduates)
    cards = []
    for g in graduates:
        cards.append({
            "g": g,
            "hours": hours_of(g),
            "progress": progress.get(g.user_id, {"done": 0, "total": 0, "pct": 0}),
            "leader_name": _name(g.leader.user) if g.leader_id else "",
            "waiting_reports": [r for r in g.reports.all() if r.status == PracticumReport.WAITING],
        })
    return cards


@login_required(login_url=LOGIN_URL)
def leader_graduates(request):
    """הבוגרים שלי: approve who joined, approve hours, follow progress (REQ-M.221)."""
    leader = access.leader_of(request.user)
    if leader is None:
        raise PermissionDenied
    rows = (
        Graduate.objects.filter(leader=leader)
        .select_related("school", "leader__user").prefetch_related("reports")
    )
    cards = _graduate_cards(rows)
    waiting = [c for c in cards if not c["g"].is_approved]
    approved = [c for c in cards if c["g"].is_approved]
    return render(
        request,
        "matazim/leader_graduates.html",
        shell(request, "leader", waiting=waiting, approved=approved),
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
        .prefetch_related("reports")
    )
    cards = _graduate_cards(rows)
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
            target=TARGET_HOURS,
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
    if do == "delete_resource":
        get_object_or_404(access.visible_graduate_resources(user), pk=request.POST.get("id")).delete()
        return ""
    raise PermissionDenied
