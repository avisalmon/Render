"""See it, take it, or have it deleted.

REQ-M.85, spec §4.10 finding P5. Until now nothing in this product could answer
"what do you hold about me" or "stop holding it", which are the two questions a
data subject is entitled to ask and the two a fourteen-year-old is least likely
to know how to chase by email.

Avi, 2026-09-11: reuse babook's infrastructure. So deletion here is not a second
deletion path. It is the same mechanism babook's `app.views.delete_account`
relies on, `User.delete()` cascading through every related table, reached from a
screen inside our own walls because RULE-1 means a member cannot be sent to
babook's. Shared plumbing, our own door.

The confirm-by-typing-your-email pattern is borrowed from there too, for the
same reason it exists there: this is irreversible and a stray double-tap must
not do it.
"""

import json

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .certification import _display_name
from .consent import age_now, has_guardian_consent, is_minor
from .models import EntranceAttempt, Student
from .views import member_profile, shell

LOGIN_URL = "/matazim/login/"


def _everything_about(user):
    """One dictionary holding every מט״צים fact about one person.

    Built by reading the tables rather than by remembering what they are, so a
    field added later shows up here instead of being quietly omitted from the
    answer we give someone who asked what we hold.
    """
    profile = member_profile(user)

    out = {
        "account": {
            "name": getattr(getattr(user, "profile", None), "display_name", "") or "",
            "email": user.email or user.username,
            "joined": user.date_joined.isoformat() if user.date_joined else None,
        },
        "matazim_profile": {},
        "entrance_attempts": [],
        "program": [],
        "learning": [],
    }

    if profile:
        out["matazim_profile"] = {
            "entered_via_matazim": profile.entered_via_matazim,
            "first_seen": profile.first_seen_at.isoformat() if profile.first_seen_at else None,
            "entrance_test_passed": (
                profile.entrance_test_passed_at.isoformat()
                if profile.entrance_test_passed_at
                else None
            ),
            "is_program_manager": profile.is_program_manager,
            "birth_year": profile.birth_year,
            "guardian_name": profile.guardian_name,
            "guardian_email": profile.guardian_email,
            "guardian_consent": (
                profile.guardian_consent_at.isoformat() if profile.guardian_consent_at else None
            ),
        }
        out["entrance_attempts"] = [
            {
                "number": a.number,
                "target": a.target_id,
                "passed": a.passed,
                "submitted": a.submitted_at.isoformat() if a.submitted_at else None,
                # The measurements, because they are the reason we said no and
                # a person is entitled to the reasoning, not only the verdict.
                "measured": a.measured,
                "issues": a.issues,
                "file_held": bool(a.model_file),
            }
            for a in EntranceAttempt.objects.filter(member=profile).order_by("number")
        ]

    for student in (
        Student.objects.filter(user=user)
        .select_related("leader__user")
        .prefetch_related("applications__asked__user")
    ):
        out["program"].append(
            {
                "cohort_year": student.cohort_year,
                "status": student.get_status_display(),
                # The leader by the name they are called, not by their inbox.
                # This said `leader@example.com` on a screen a 14-year-old reads
                # and in a file they download, which is both wrong and a
                # disclosure of a member of staff's address to a minor.
                "leader": (_display_name(student.leader.user) if student.leader else None),
                "classes": [
                    {"name": c.name, "school": c.school_name} for c in student.classes.all()
                ],
                "certified_at": (
                    student.certified_at.isoformat() if student.certified_at else None
                ),
                # REQ-M.85, REQ-M.16 — their own words about themselves are
                # among the most personal things we hold, so they belong in the
                # answer to "what do you have about me" rather than being
                # visible only to staff.
                "applications": [
                    {
                        "asked": _display_name(a.asked.user) if a.asked else None,
                        "grade": a.grade,
                        "motivation": a.motivation,
                        "built_before": a.built_before,
                        "sent": a.created_at.isoformat() if a.created_at else None,
                    }
                    for a in student.applications.all()
                ],
            }
        )

    # The learning itself is babook's, and RULE-3 says there is one version of
    # it. Named here rather than copied, so the export is honest about where it
    # lives without this file inventing a second account of it.
    from app.models import Course, CourseCertificate, Enrollment

    # Counted from what somebody actually watched as well as from what they
    # enrolled in. Reading `Enrollment` alone made this page say "0 courses
    # started, 1 certificate", which cannot be true and which a person asking
    # what we hold about them is entitled not to be told.
    enrolments = {
        e.course_id: e for e in Enrollment.objects.filter(user=user).select_related("course")
    }
    watched = dict(
        Course.objects.filter(videos__user_progress__user=user)
        .distinct()
        .values_list("id", "slug")
    )
    for course_id in dict.fromkeys(list(enrolments) + list(watched)):
        e = enrolments.get(course_id)
        out["learning"].append(
            {
                "course": e.course.slug if e else watched[course_id],
                "enrolled": (e.enrolled_at.isoformat() if e and e.enrolled_at else None),
                "completed": (e.completed_at.isoformat() if e and e.completed_at else None),
            }
        )
    out["certificates"] = [
        {"course": c.course.slug, "issued": c.issued_at.isoformat()}
        for c in CourseCertificate.objects.filter(user=user).select_related("course")
    ]
    return out


@login_required(login_url=LOGIN_URL)
def my_data(request):
    """REQ-M.85 — everything we hold, on one screen."""
    profile = member_profile(request.user)
    return render(
        request,
        "matazim/my_data.html",
        shell(
            request,
            "profile",
            data=_everything_about(request.user),
            attempts=(
                EntranceAttempt.objects.filter(member=profile).order_by("number") if profile else []
            ),
            # The attempt rows are the detail; the profile field is the fact.
            # Showing "you have not sat it yet" to somebody the rest of the site
            # treats as having passed is the two of them disagreeing in public.
            passed_at=getattr(profile, "entrance_test_passed_at", None),
            age=age_now(profile),
            minor=is_minor(profile),
            consented=has_guardian_consent(profile),
        ),
    )


@login_required(login_url=LOGIN_URL)
def my_data_export(request):
    """REQ-M.85 — a copy they can keep.

    Built from `request.user` and never from anything in the URL, so there is no
    identifier here to tamper with and nothing to walk.
    """
    payload = json.dumps(_everything_about(request.user), ensure_ascii=False, indent=2)
    response = HttpResponse(payload, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="matazim-my-data.json"'
    return response


@login_required(login_url=LOGIN_URL)
def delete_me(request):
    """REQ-M.85 — the same mechanism babook uses, behind our own door.

    `User.delete()` cascades into `MemberProfile`, `Student` and
    `EntranceAttempt`, and the `post_delete` receiver added in SPR-M.9 takes the
    uploaded file off the disk with the row. Nothing about מט״צים needs its own
    deletion logic, and a second one would only be a second thing to keep in
    step with the first.
    """
    user = request.user
    error = ""

    if request.method == "POST":
        typed = (request.POST.get("confirm_email") or "").strip().lower()
        if typed != (user.email or user.username or "").strip().lower():
            error = "האימייל לא תואם. הקלידו את הכתובת של החשבון כדי לאשר."
        else:
            logout(request)
            user.delete()
            return redirect("matazim:home")

    return render(
        request,
        "matazim/delete_me.html",
        shell(request, "profile", error=error, email=user.email or user.username),
    )
