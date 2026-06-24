"""Chapter 9 - Teachers & Classes (Classrooms) views.

Privacy by role is enforced here: a student's progress, achievements and
reflections are visible to the class owner only (class_manage / class_student);
classmates see only shared projects and discussions (classroom).
"""

import io

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .classroom_models import (
    ClassInvite,
    ClassJoinRequest,
    ClassMembership,
    ClassMessage,
    TeacherClass,
)
from .models import Course, CourseCertificate, LessonModelSubmission, UserVideoProgress, Video


def _display_name(user):
    return user.profile.public_name if hasattr(user, "profile") else user.username


def _send_mail_safe(subject, body, to_email):
    """Send a plain-text email, never raising into the request flow."""
    if not to_email:
        return
    send_mail(
        subject, body,
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il"),
        [to_email], fail_silently=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _owned_class(request, pk):
    """Return the class if the requester owns it (or is staff), else 404."""
    klass = get_object_or_404(TeacherClass, pk=pk)
    if klass.owner_id != request.user.id and not request.user.is_superuser:
        raise Http404
    return klass


def _student_courses(student):
    """Per-course learning summary for a student, with a lesson-by-lesson breakdown
    (done state + that lesson's upload) for the teacher's detailed view. The same
    'done' rule the catalog/profile use: a lesson counts once it has progress, and
    quiz/reflection lessons also need quiz_passed. Teacher-only data."""
    from .models import Enrollment, LessonQuiz

    course_ids = set(
        UserVideoProgress.objects.filter(user=student).values_list("video__course_id", flat=True))
    course_ids |= set(Enrollment.objects.filter(user=student).values_list("course_id", flat=True))
    course_ids = [c for c in course_ids if c]
    if not course_ids:
        return []

    courses = {c.id: c for c in Course.objects.filter(id__in=course_ids)}
    videos = list(Video.objects.filter(course_id__in=course_ids).order_by("lesson_order"))
    required = set(
        LessonQuiz.objects.filter(video__course_id__in=course_ids, requires_correct=True)
        .values_list("video_id", flat=True)
    ) | set(
        Video.objects.filter(course_id__in=course_ids).exclude(reflection_prompt="")
        .values_list("id", flat=True)
    )
    prog = {p.video_id: p for p in
            UserVideoProgress.objects.filter(user=student, video__course_id__in=course_ids)}
    subs = {s.video_id: s for s in
            LessonModelSubmission.objects.filter(user=student, video__course_id__in=course_ids)
            .select_related("video")}
    certs = {cc.course_id: cc
             for cc in CourseCertificate.objects.filter(user=student, course_id__in=course_ids)}
    completed_courses = set(
        Enrollment.objects.filter(user=student, course_id__in=course_ids, completed_at__isnull=False)
        .values_list("course_id", flat=True))

    def _done(video):
        p = prog.get(video.id)
        if not p:
            return False
        return p.quiz_passed if video.id in required else True

    by_course = {}
    for v in videos:
        by_course.setdefault(v.course_id, []).append(v)

    out = []
    for cid in course_ids:
        course = courses.get(cid)
        if not course:
            continue
        lessons = [{
            "video": v,
            "done": _done(v),
            # 0/1-item list so the template can reuse the project gallery partial.
            "submissions": [subs[v.id]] if v.id in subs else [],
        } for v in by_course.get(cid, [])]
        total = len(lessons)
        done = sum(1 for ll in lessons if ll["done"])
        out.append({
            "course": course,
            "pct": round(done / total * 100) if total else 0,
            "done": done,
            "total": total,
            "completed": cid in completed_courses,
            "certificate": certs.get(cid),
            "projects": [ll["submissions"][0] for ll in lessons if ll["submissions"]],
            "lessons": lessons,
        })
    out.sort(key=lambda x: x["pct"], reverse=True)
    return out


def _student_summary(student):
    """Compact roster row for one student."""
    courses = _student_courses(student)
    return {
        "student": student,
        "name": student.profile.public_name if hasattr(student, "profile") else student.username,
        "courses_count": len(courses),
        "certs_count": sum(1 for c in courses if c["certificate"]),
        "projects_count": sum(len(c["projects"]) for c in courses),
    }


def _join_url(request, klass):
    return request.build_absolute_uri(reverse("class_join", args=[klass.join_code]))


def _send_class_invite(request, klass, invitee, inviter):
    """Invite an existing member in-system AND by email. The link is the class
    join link, so pressing it auto-joins them straight into the class."""
    from .community import notify
    path = reverse("class_join", args=[klass.join_code])
    join_url = request.build_absolute_uri(path)
    teacher_name = _display_name(inviter)
    notify(invitee, "class_invite",
           f"{teacher_name} הזמין אותך לכיתה \"{klass.name}\". לחצו כדי להצטרף.",
           url=path, actor=inviter)
    _send_mail_safe(
        f"הזמנה לכיתה {klass.name}",
        f"{teacher_name} הזמין אותך להצטרף לכיתה \"{klass.name}\" ב-babook.\n\n"
        f"להצטרפות מיידית (לחיצה אחת) היכנסו לקישור:\n{join_url}\n",
        invitee.email)


# ---------------------------------------------------------------------------
# Teacher onboarding + class list
# ---------------------------------------------------------------------------

@login_required
@require_POST
def become_teacher(request):
    profile = request.user.profile
    if not profile.is_teacher:
        profile.is_teacher = True
        profile.save(update_fields=["is_teacher"])
        messages.success(request, "פתחת מרחב מורה. אפשר ליצור כיתה ראשונה.")
    return redirect("my_classes")


@login_required
def my_classes(request):
    """Hub: classes I teach, classes I'm a member of, and pending invites."""
    profile = request.user.profile
    owned = list(TeacherClass.objects.filter(owner=request.user))
    member_of = list(
        TeacherClass.objects
        .filter(memberships__student=request.user, memberships__status="active")
        .exclude(owner=request.user).distinct())
    invites = list(
        ClassInvite.objects.filter(invitee=request.user, status="pending")
        .select_related("klass", "inviter"))
    return render(request, "app/classroom/my_classes.html", {
        "is_teacher": profile.is_teacher,
        "owned": owned,
        "member_of": member_of,
        "invites": invites,
    })


@login_required
def class_create(request):
    if not request.user.profile.is_teacher:
        return redirect("my_classes")
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        if not name:
            messages.error(request, "צריך שם לכיתה.")
            return render(request, "app/classroom/class_create.html")
        klass = TeacherClass.objects.create(
            owner=request.user, name=name[:120], description=description)
        messages.success(request, "הכיתה נוצרה.")
        return redirect("class_manage", pk=klass.pk)
    return render(request, "app/classroom/class_create.html")


# ---------------------------------------------------------------------------
# Teacher: manage, roster, per-student insight
# ---------------------------------------------------------------------------

@login_required
def class_manage(request, pk):
    klass = _owned_class(request, pk)
    roster = [_student_summary(m.student) for m in klass.active_memberships()]
    pending = list(
        klass.invites.filter(status="pending").select_related("invitee"))
    active_ids = klass.memberships.filter(status="active").values_list("student_id", flat=True)
    join_requests = list(
        klass.join_requests.filter(status="pending")
        .exclude(student_id__in=active_ids).select_related("student"))
    join_url = _join_url(request, klass)
    teacher_name = _display_name(request.user)
    # A friendly invitation message for WhatsApp (the link stays clickable).
    wa_text = (f'הוזמנתם לכיתה "{klass.name}" של {teacher_name} ב-babook.\n'
               f'להצטרפות הקליקו כאן:\n{join_url}')
    return render(request, "app/classroom/class_manage.html", {
        "klass": klass,
        "roster": roster,
        "pending": pending,
        "join_requests": join_requests,
        "join_url": join_url,
        "wa_text": wa_text,
        "members": klass.active_memberships(),
    })


@login_required
def class_student(request, pk, student_id):
    """Teacher-only deep view of one student's progress and deliverables."""
    klass = _owned_class(request, pk)
    membership = ClassMembership.objects.filter(
        klass=klass, student_id=student_id, status="active").first()
    if not membership:
        raise Http404
    student = membership.student
    return render(request, "app/classroom/class_student.html", {
        "klass": klass,
        "student": student,
        "student_name": student.profile.public_name if hasattr(student, "profile") else student.username,
        "courses": _student_courses(student),
    })


# ---------------------------------------------------------------------------
# Joining: link / QR, and invites
# ---------------------------------------------------------------------------

def class_join(request, code):
    """Join by link/QR. Logged-in joins instantly; logged-out is routed through the
    /join/ wall and lands back here to auto-join (REQ-5.4 return-to-intent)."""
    klass = get_object_or_404(TeacherClass, join_code=code)
    here = reverse("class_join", args=[code])

    if not request.user.is_authenticated:
        # Render a landing page (with Open Graph tags so the link shows a nice
        # preview card on WhatsApp) instead of bouncing straight to the wall.
        return render(request, "app/classroom/class_join_landing.html", {
            "klass": klass,
            "teacher_name": _display_name(klass.owner),
            "join_next": f"{reverse('join_wall')}?next={here}",
            "page_url": request.build_absolute_uri(here),
            "og_image": request.build_absolute_uri(static("img/training-hero.png")),
        })

    if klass.owner_id == request.user.id:
        return redirect("class_manage", pk=klass.pk)

    membership = klass.memberships.filter(student=request.user).first()
    if membership and membership.status == "active":
        return redirect("classroom", pk=klass.pk)

    if not klass.is_open and not membership:
        messages.error(request, "הכיתה סגורה להצטרפות כרגע.")
        return redirect("my_classes")

    if membership:
        membership.status = "active"
        membership.save(update_fields=["status"])
    else:
        ClassMembership.objects.create(klass=klass, student=request.user, status="active")
    # Resolve any open invite / join request for this pair so nothing lingers.
    klass.invites.filter(invitee=request.user, status="pending").update(status="accepted")
    klass.join_requests.filter(student=request.user, status="pending").update(
        status="approved", decided_at=timezone.now())
    messages.success(request, f"הצטרפת לכיתה {klass.name}.")
    return redirect("classroom", pk=klass.pk)


@login_required
def class_user_search(request, pk):
    """JSON user search for the invite box (teacher only)."""
    klass = _owned_class(request, pk)
    q = (request.GET.get("q") or "").strip()
    results = []
    if q:  # search from the very first character typed
        already = set(klass.memberships.filter(status="active").values_list("student_id", flat=True))
        already.add(klass.owner_id)
        qs = (User.objects.filter(is_active=True)
              .filter(models_q(q))
              .exclude(id__in=already)[:10])
        for u in qs:
            name = u.profile.public_name if hasattr(u, "profile") else u.username
            results.append({"id": u.id, "name": name, "username": u.username})
    return JsonResponse({"results": results})


def models_q(q):
    from django.db.models import Q
    return Q(username__icontains=q) | Q(first_name__icontains=q) | Q(email__icontains=q) | \
        Q(profile__display_name__icontains=q)


@login_required
@require_POST
def class_invite(request, pk):
    """Send an in-system invite to an existing member (teacher only)."""
    klass = _owned_class(request, pk)
    try:
        invitee = User.objects.get(pk=request.POST.get("user_id"))
    except (User.DoesNotExist, ValueError, TypeError):
        messages.error(request, "המשתמש לא נמצא.")
        return redirect("class_manage", pk=klass.pk)
    if invitee == request.user:
        return redirect("class_manage", pk=klass.pk)
    if klass.memberships.filter(student=invitee, status="active").exists():
        messages.info(request, "המשתמש כבר חבר בכיתה.")
        return redirect("class_manage", pk=klass.pk)

    ClassInvite.objects.update_or_create(
        klass=klass, invitee=invitee,
        defaults={"inviter": request.user, "status": "pending"})
    _send_class_invite(request, klass, invitee, request.user)
    messages.success(request, "ההזמנה נשלחה (במערכת ובמייל).")
    return redirect("class_manage", pk=klass.pk)


@login_required
@require_POST
def class_invite_resend(request, invite_id):
    """Owner resends a pending invite as an email + in-system reminder."""
    invite = get_object_or_404(ClassInvite, pk=invite_id)
    if invite.klass.owner_id != request.user.id and not request.user.is_superuser:
        raise Http404
    if invite.status == "pending":
        _send_class_invite(request, invite.klass, invite.invitee, request.user)
        messages.success(request, "תזכורת נשלחה.")
    return redirect("class_manage", pk=invite.klass.pk)


@login_required
@require_POST
def invite_respond(request, invite_id):
    invite = get_object_or_404(ClassInvite, pk=invite_id, invitee=request.user, status="pending")
    action = request.POST.get("action")
    if action == "accept":
        ClassMembership.objects.update_or_create(
            klass=invite.klass, student=request.user, defaults={"status": "active"})
        invite.status = "accepted"
        invite.save(update_fields=["status"])
        invite.klass.join_requests.filter(student=request.user, status="pending").update(
            status="approved", decided_at=timezone.now())
        messages.success(request, f"הצטרפת לכיתה {invite.klass.name}.")
        return redirect("classroom", pk=invite.klass.pk)
    invite.status = "declined"
    invite.save(update_fields=["status"])
    return redirect("my_classes")


# ---------------------------------------------------------------------------
# Classroom (shared space): discussions, teacher messages, project gallery
# ---------------------------------------------------------------------------

@login_required
def classroom(request, pk):
    klass = get_object_or_404(TeacherClass, pk=pk)
    is_owner = klass.owner_id == request.user.id
    membership = klass.memberships.filter(student=request.user, status="active").first()
    if not is_owner and not membership:
        messages.error(request, "אינך חבר בכיתה הזו.")
        return redirect("my_classes")

    msgs = list(klass.messages.select_related("author").all())

    # Project gallery: shared projects of active members, grouped by student.
    galleries = []
    for m in klass.active_memberships():
        if not m.share_projects:
            continue
        projects = list(
            LessonModelSubmission.objects.filter(user=m.student)
            .select_related("video", "video__course"))
        if projects:
            name = m.student.profile.public_name if hasattr(m.student, "profile") else m.student.username
            galleries.append({"name": name, "models": projects})

    return render(request, "app/classroom/classroom.html", {
        "klass": klass,
        "is_owner": is_owner,
        "membership": membership,
        "msgs": msgs,
        "galleries": galleries,
    })


@login_required
@require_POST
def class_post(request, pk):
    klass = get_object_or_404(TeacherClass, pk=pk)
    is_owner = klass.owner_id == request.user.id
    if not is_owner and not klass.is_member(request.user):
        raise Http404
    body = (request.POST.get("body") or "").strip()
    if body:
        ClassMessage.objects.create(
            klass=klass, author=request.user, body=body[:4000], is_announcement=is_owner)
    return redirect("classroom", pk=klass.pk)


@login_required
@require_POST
def class_toggle_share(request, pk):
    klass = get_object_or_404(TeacherClass, pk=pk)
    membership = ClassMembership.objects.filter(
        klass=klass, student=request.user, status="active").first()
    if not membership:
        raise Http404
    membership.share_projects = not membership.share_projects
    membership.save(update_fields=["share_projects"])
    state = "משותפים" if membership.share_projects else "מוסתרים"
    messages.success(request, f"הפרויקטים שלך {state} בכיתה.")
    return redirect("classroom", pk=klass.pk)


@login_required
@require_POST
def class_leave(request, pk):
    klass = get_object_or_404(TeacherClass, pk=pk)
    klass.memberships.filter(student=request.user).update(status="removed")
    messages.success(request, "יצאת מהכיתה.")
    return redirect("my_classes")


# ---------------------------------------------------------------------------
# Teacher controls
# ---------------------------------------------------------------------------

@login_required
@require_POST
def class_remove(request, pk, student_id):
    klass = _owned_class(request, pk)
    klass.memberships.filter(student_id=student_id).update(status="removed")
    messages.success(request, "התלמיד הוסר מהכיתה.")
    return redirect("class_manage", pk=klass.pk)


@login_required
@require_POST
def class_toggle_open(request, pk):
    klass = _owned_class(request, pk)
    klass.is_open = not klass.is_open
    klass.save(update_fields=["is_open"])
    return redirect("class_manage", pk=klass.pk)


@login_required
@require_POST
def class_rotate_code(request, pk):
    from .classroom_models import gen_join_code
    klass = _owned_class(request, pk)
    klass.join_code = gen_join_code()
    klass.save(update_fields=["join_code"])
    messages.success(request, "נוצר קישור הצטרפות חדש. הקישור הישן בוטל.")
    return redirect("class_manage", pk=klass.pk)


@login_required
@require_POST
def class_delete(request, pk):
    klass = _owned_class(request, pk)
    klass.delete()
    messages.success(request, "הכיתה נמחקה.")
    return redirect("my_classes")


@login_required
def class_qr(request, pk):
    """QR PNG of the class join link (teacher only)."""
    import qrcode

    klass = _owned_class(request, pk)
    img = qrcode.make(_join_url(request, klass), box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


# ---------------------------------------------------------------------------
# Public directory + request-to-join (teacher approval)
# ---------------------------------------------------------------------------

def class_directory(request):
    """Public page to FIND a class by search - not a full list, so people don't
    just wander into random classes. Matches load via class_search as you type."""
    return render(request, "app/classroom/class_directory.html")


def class_search(request):
    """JSON: classes matching the query (by class name or teacher), with the
    searcher's per-class state so the right action shows. No student data exposed."""
    from django.db.models import Count, Q

    q = (request.GET.get("q") or "").strip()
    results = []
    if q:
        qs = (TeacherClass.objects
              .select_related("owner", "owner__profile")
              .annotate(active_count=Count("memberships", filter=Q(memberships__status="active")))
              .filter(Q(name__icontains=q)
                      | Q(owner__first_name__icontains=q)
                      | Q(owner__profile__display_name__icontains=q))[:12])
        member_ids, request_ids = set(), set()
        if request.user.is_authenticated:
            member_ids = set(
                ClassMembership.objects.filter(student=request.user, status="active")
                .values_list("klass_id", flat=True))
            request_ids = set(
                ClassJoinRequest.objects.filter(student=request.user, status="pending")
                .values_list("klass_id", flat=True))
        for c in qs:
            results.append({
                "id": c.id,
                "name": c.name,
                "teacher": _display_name(c.owner),
                "member_count": c.active_count,
                "is_open": c.is_open,
                "is_owner": request.user.is_authenticated and c.owner_id == request.user.id,
                "is_member": c.id in member_ids,
                "requested": c.id in request_ids,
            })
    return JsonResponse({"results": results})


@login_required
@require_POST
def class_request_join(request, pk):
    """A member asks the teacher to join. Notifies the teacher in-system + by email."""
    klass = get_object_or_404(TeacherClass, pk=pk)
    if klass.owner_id == request.user.id:
        return redirect("class_manage", pk=klass.pk)
    if klass.memberships.filter(student=request.user, status="active").exists():
        return redirect("classroom", pk=klass.pk)
    if not klass.is_open:
        messages.error(request, "הכיתה סגורה להצטרפות כרגע.")
        return redirect("class_directory")

    # Idempotent: a request already pending must not re-spam the teacher. Only
    # notify when the request is newly created or genuinely reopened (was not pending).
    existing = ClassJoinRequest.objects.filter(klass=klass, student=request.user).first()
    was_pending = bool(existing and existing.status == "pending")
    req, _created = ClassJoinRequest.objects.update_or_create(
        klass=klass, student=request.user,
        defaults={"status": "pending", "decided_at": None,
                  "message": (request.POST.get("message") or "").strip()[:300]})

    if not was_pending:
        student_name = _display_name(request.user)
        from .community import notify
        approve_url = request.build_absolute_uri(reverse("class_request_approve", args=[req.id]))
        notify(klass.owner, "class_join_request",
               f"{student_name} ביקש להצטרף לכיתה \"{klass.name}\".",
               url=reverse("class_request_approve", args=[req.id]), actor=request.user)
        _send_mail_safe(
            f"בקשה להצטרף לכיתה {klass.name}",
            f"{student_name} ביקש להצטרף לכיתה \"{klass.name}\".\n\n"
            f"לאישור או דחייה היכנסו לקישור:\n{approve_url}\n",
            klass.owner.email)
    messages.success(request, "הבקשה נשלחה למורה. תקבלו הודעה כשתאושר.")
    return redirect("class_directory")


@login_required
def class_request_approve(request, req_id):
    """Owner approves a join request. GET shows a confirm page (so the emailed link
    never mutates state); POST does the approval and notifies the student."""
    req = get_object_or_404(ClassJoinRequest, pk=req_id)
    if req.klass.owner_id != request.user.id and not request.user.is_superuser:
        raise Http404

    if request.method != "POST":
        # If it was already decided, just go to manage rather than re-approving.
        if req.status != "pending":
            messages.info(request, "הבקשה כבר טופלה.")
            return redirect("class_manage", pk=req.klass.pk)
        # Tell the teacher if this student was removed from the class before.
        was_removed = req.klass.memberships.filter(
            student=req.student, status="removed").exists()
        return render(request, "app/classroom/request_confirm.html", {
            "req": req, "student_name": _display_name(req.student),
            "was_removed": was_removed})

    if req.status == "pending":
        ClassMembership.objects.update_or_create(
            klass=req.klass, student=req.student, defaults={"status": "active"})
        req.status = "approved"
        req.decided_at = timezone.now()
        req.save(update_fields=["status", "decided_at"])

        from .community import notify
        class_url = request.build_absolute_uri(reverse("classroom", args=[req.klass.pk]))
        notify(req.student, "class_request_approved",
               f"אושרת לכיתה \"{req.klass.name}\". אפשר להיכנס.",
               url=reverse("classroom", args=[req.klass.pk]), actor=request.user)
        _send_mail_safe(
            f"אושרת לכיתה {req.klass.name}",
            f"שלום {_display_name(req.student)},\n\n"
            f"בקשתך להצטרף לכיתה \"{req.klass.name}\" אושרה.\n\n"
            f"היכנסו לכיתה כאן:\n{class_url}\n",
            req.student.email)
        messages.success(request, f"{_display_name(req.student)} צורף לכיתה.")
    else:
        messages.info(request, "הבקשה כבר טופלה.")
    return redirect("class_manage", pk=req.klass.pk)


@login_required
@require_POST
def class_request_decline(request, req_id):
    req = get_object_or_404(ClassJoinRequest, pk=req_id)
    if req.klass.owner_id != request.user.id and not request.user.is_superuser:
        raise Http404
    if req.status == "pending":
        req.status = "declined"
        req.decided_at = timezone.now()
        req.save(update_fields=["status", "decided_at"])
        from .community import notify
        notify(req.student, "class_request_declined",
               f"הבקשה להצטרף לכיתה \"{req.klass.name}\" לא אושרה.", actor=request.user)
        messages.success(request, "הבקשה נדחתה.")
    else:
        messages.info(request, "הבקשה כבר טופלה.")
    return redirect("class_manage", pk=req.klass.pk)
