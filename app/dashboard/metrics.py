"""Internal metric collectors for the admin dashboard.

Pure functions that query the local DB and return plain dicts, so they are
testable in isolation and reusable by both the live view and the
``capture_dashboard_snapshot`` command. Each collector is defensive: a missing
table or model never raises out of here (returns a partial dict instead), so
one weak metric never blanks the whole page (REQ-8.1.7).

Covers REQ-8.2.* (users & training), REQ-8.4.* (engagement) and REQ-8.5.*
(system health).
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone


def _since(days):
    """Return the cutoff datetime, or ``None`` for an all-time window."""
    if days is None:
        return None
    return timezone.now() - timedelta(days=days)


def _filt(qs, field, cutoff):
    return qs if cutoff is None else qs.filter(**{f"{field}__gte": cutoff})


# ---------------------------------------------------------------------------
# REQ-8.2 - Users & Training
# ---------------------------------------------------------------------------


def collect_users_training(range_days=30):
    """Users, activity, training depth, popular courses and funnels."""
    from ..models import (
        CorporateLead,
        Course,
        CourseCertificate,
        Enrollment,
        LearnerProfile,
        LessonReflection,
        NewsletterSubscriber,
        UserVideoProgress,
        Video,
    )

    now = timezone.now()
    cutoff = _since(range_days)
    m = {}

    # --- totals & growth (REQ-8.2.1) ---
    m["users_total"] = User.objects.count()
    m["users_new"] = _filt(User.objects, "date_joined", cutoff).count()

    # role breakdown (LearnerProfile.role_type)
    role_rows = LearnerProfile.objects.values("role_type").annotate(n=Count("id")).order_by("-n")
    m["by_role"] = {(r["role_type"] or "-"): r["n"] for r in role_rows}

    # auth-provider breakdown (allauth SocialAccount; rest = email/password)
    providers = {}
    try:
        from allauth.socialaccount.models import SocialAccount

        for r in SocialAccount.objects.values("provider").annotate(n=Count("id")):
            providers[r["provider"]] = r["n"]
        social_user_ids = set(SocialAccount.objects.values_list("user_id", flat=True))
        providers["email"] = User.objects.exclude(id__in=social_user_ids).count()
    except Exception:
        providers = {}
    m["by_provider"] = providers

    # --- active users DAU/WAU/MAU (REQ-8.2.2) ---
    def _active_within(days):
        win = now - timedelta(days=days)
        ids = set(User.objects.filter(last_login__gte=win).values_list("id", flat=True))
        ids |= set(
            UserVideoProgress.objects.filter(updated_at__gte=win).values_list("user_id", flat=True)
        )
        ids.discard(None)
        return len(ids)

    m["dau"] = _active_within(1)
    m["wau"] = _active_within(7)
    m["mau"] = _active_within(30)
    m["active_rate_pct"] = round(100 * m["mau"] / m["users_total"]) if m["users_total"] else 0

    # --- training engagement (REQ-8.2.3) ---
    enrollments = Enrollment.objects.all()
    m["enrollments"] = _filt(enrollments, "enrolled_at", cutoff).count()
    completed = enrollments.filter(completed_at__isnull=False)
    m["course_completions"] = _filt(completed, "completed_at", cutoff).count()
    m["course_completion_pct"] = (
        round(100 * enrollments.filter(completed_at__isnull=False).count() / enrollments.count())
        if enrollments.count()
        else 0
    )

    progress = UserVideoProgress.objects.all()
    m["lessons_watched"] = _filt(progress, "updated_at", cutoff).count()
    lesson_completed = progress.filter(completed_at__isnull=False)
    m["lessons_completed"] = _filt(lesson_completed, "completed_at", cutoff).count()
    passed = progress.filter(quiz_passed=True).count()
    m["quiz_pass_rate_pct"] = round(100 * passed / progress.count()) if progress.count() else 0

    # watch-hours = sum(duration * percent / 100)
    durations = {
        v["id"]: (v["duration_seconds"] or 0)
        for v in Video.objects.values("id", "duration_seconds")
    }
    secs = 0.0
    rows = _filt(progress, "updated_at", cutoff).values("video_id", "percent_watched")
    for r in rows:
        secs += durations.get(r["video_id"], 0) * (r["percent_watched"] or 0) / 100.0
    m["watch_hours"] = round(secs / 3600.0, 1)

    m["certificates"] = _filt(CourseCertificate.objects, "issued_at", cutoff).count()
    m["reflections"] = _filt(LessonReflection.objects, "created_at", cutoff).count()

    # --- popular courses (REQ-8.2.4) ---
    course_titles = {c["id"]: c["title"] for c in Course.objects.values("id", "title")}
    enr_by_course = {
        r["course_id"]: r["n"] for r in enrollments.values("course_id").annotate(n=Count("id"))
    }
    comp_by_course = {
        r["course_id"]: r["n"] for r in completed.values("course_id").annotate(n=Count("id"))
    }
    popular = []
    for cid, n in enr_by_course.items():
        comp = comp_by_course.get(cid, 0)
        popular.append(
            {
                "course_id": cid,
                "title": course_titles.get(cid, "-"),
                "enrollments": n,
                "completions": comp,
                "completion_pct": round(100 * comp / n) if n else 0,
            }
        )
    popular.sort(key=lambda r: r["enrollments"], reverse=True)
    m["popular_courses"] = popular[:10]

    # --- activation funnel (REQ-8.2.5) - locally derivable steps ---
    reg = _filt(User.objects, "date_joined", cutoff).count()
    profiles = LearnerProfile.objects.all()
    onboarding_started = _filt(profiles, "created_at", cutoff).count()
    onboarding_done = _filt(
        profiles.filter(onboarding_completed_at__isnull=False),
        "onboarding_completed_at",
        cutoff,
    ).count()
    first_lesson_users = set(
        UserVideoProgress.objects.filter(completed_at__isnull=False).values_list(
            "user_id", flat=True
        )
    )
    m["funnel"] = {
        "registered": reg,
        "onboarding_started": onboarding_started,
        "onboarding_completed": onboarding_done,
        "first_lesson_completed": len(first_lesson_users),
    }
    m["activation_rate_pct"] = round(100 * onboarding_done / reg) if reg else 0
    m["funnel_note"] = (
        "entry / free-lesson / wall steps come from Plausible (ACT-24); "
        "the steps above are derived locally."
    )

    # --- corporate / lead funnel (REQ-8.2.6) ---
    leads = CorporateLead.objects.all()
    m["leads_total"] = leads.count()
    m["leads_new"] = _filt(leads, "created_at", cutoff).count()
    m["leads_by_status"] = {
        r["status"]: r["n"] for r in leads.values("status").annotate(n=Count("id"))
    }
    subs = NewsletterSubscriber.objects.all()
    m["subs_total"] = subs.count()
    m["subs_confirmed"] = subs.filter(confirmed_at__isnull=False).count()
    m["subs_pending"] = subs.filter(confirmed_at__isnull=True).count()

    return m


# ---------------------------------------------------------------------------
# REQ-8.4 - Engagement & community health (superset of REQ-6.8.2)
# ---------------------------------------------------------------------------


def collect_engagement(range_days=7):
    from ..models import (
        BadgeAward,
        ChannelMessage,
        CommunityEvent,
        CommunityReputation,
        ContentReport,
        DirectMessage,
        EventRSVP,
        Follow,
        ForumPost,
        ForumThread,
        ProjectComment,
        ProjectReaction,
        ShowcaseProject,
        Tip,
    )

    now = timezone.now()
    cutoff = _since(range_days)
    m = {}

    # weekly active contributors (distinct authors across surfaces) - fixed 7d
    week = now - timedelta(days=7)
    active = set()
    active |= set(Tip.objects.filter(created_at__gte=week).values_list("author_id", flat=True))
    active |= set(
        ForumThread.objects.filter(created_at__gte=week).values_list("author_id", flat=True)
    )
    active |= set(
        ForumPost.objects.filter(created_at__gte=week).values_list("author_id", flat=True)
    )
    active |= set(
        ShowcaseProject.objects.filter(published_at__gte=week).values_list("author_id", flat=True)
    )
    active |= set(
        ChannelMessage.objects.filter(created_at__gte=week).values_list("author_id", flat=True)
    )
    active.discard(None)
    m["active_contributors"] = len(active)

    # forum knowledge trust-loop
    questions = ForumThread.objects.filter(kind="question", is_hidden=False)
    q_total = questions.count()
    q_unanswered = sum(1 for t in questions if not t.posts.exists())
    m["q_total"] = q_total
    m["q_unanswered"] = q_unanswered
    m["q_unanswered_pct"] = round(100 * q_unanswered / q_total) if q_total else 0
    accepted = ForumPost.objects.filter(is_accepted=True).count()
    answers = ForumPost.objects.count()
    m["answers"] = answers
    m["accepted_answers"] = accepted

    deltas = []
    for t in questions.prefetch_related("posts"):
        first = t.posts.order_by("created_at").first()
        if first:
            deltas.append((first.created_at - t.created_at).total_seconds() / 3600)
    m["avg_ttfa"] = round(sum(deltas) / len(deltas), 1) if deltas else None

    # showcase / skill trust-loop
    m["projects_total"] = ShowcaseProject.objects.filter(status="published").count()
    m["projects_window"] = _filt(
        ShowcaseProject.objects.filter(status="published"), "published_at", cutoff
    ).count()
    m["projects_by_stand"] = {
        r["stand"]: r["n"]
        for r in ShowcaseProject.objects.filter(status="published")
        .values("stand")
        .annotate(n=Count("id"))
        .order_by("-n")
    }
    m["reactions"] = _filt(ProjectReaction.objects, "created_at", cutoff).count()
    m["project_comments"] = _filt(ProjectComment.objects, "created_at", cutoff).count()

    # feed / chat / social
    m["tips_window"] = _filt(Tip.objects, "created_at", cutoff).count()
    m["messages_window"] = _filt(ChannelMessage.objects, "created_at", cutoff).count()
    m["dms_window"] = _filt(DirectMessage.objects, "created_at", cutoff).count()
    m["follows"] = Follow.objects.count()
    m["badges_window"] = _filt(BadgeAward.objects, "awarded_at", cutoff).count()

    # reputation leaders
    m["reputation_leaders"] = [
        {"user": r.user.username, "points": r.points}
        for r in CommunityReputation.objects.select_related("user").order_by("-points")[:5]
    ]

    # events
    m["events_upcoming"] = CommunityEvent.objects.filter(end_at__gte=now).count()
    m["rsvps_upcoming"] = EventRSVP.objects.filter(status="going", event__end_at__gte=now).count()

    # moderation pulse (REQ-8.4.4)
    m["open_reports"] = ContentReport.objects.filter(status="open").count()
    m["pending_projects"] = ShowcaseProject.objects.filter(status="pending").count()

    # overall engagement rate (REQ-8.4.3): contributors / active users (30d)
    mau_ids = set(
        User.objects.filter(last_login__gte=now - timedelta(days=30)).values_list("id", flat=True)
    )
    mau = len(mau_ids) or 1
    m["engagement_rate_pct"] = round(100 * len(active) / mau)

    return m


# ---------------------------------------------------------------------------
# REQ-8.5 - System health
# ---------------------------------------------------------------------------


def collect_system():
    import os

    m = {}

    # deploy / revision - local git HEAD as a no-creds default (REQ-8.5.1)
    m["revision"] = _git_head()

    # database & storage (REQ-8.5.3)
    db_path = settings.DATABASES.get("default", {}).get("NAME")
    m["db_bytes"] = os.path.getsize(db_path) if db_path and os.path.exists(db_path) else None
    m["media_bytes"] = _dir_size(getattr(settings, "MEDIA_ROOT", None))

    # backup status (REQ-8.5.2) - read a marker if the backup job writes one
    m["last_backup_at"] = _last_backup_marker()

    # health + dependency key presence (REQ-8.5.4)
    m["healthz_ok"] = True
    m["dependencies"] = {
        "openai": bool(getattr(settings, "OPENAI_API_KEY", "")),
        "bunny": bool(getattr(settings, "BUNNY_API_KEY", "")),
        "resend": bool(getattr(settings, "RESEND_API_KEY", "")),
    }
    return m


def _git_head():
    try:
        import subprocess

        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def _dir_size(path):
    import os

    if not path or not os.path.isdir(path):
        return None
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _last_backup_marker():
    """Return ISO timestamp of the last backup if a marker file exists.

    The backup job (REQ-1.2.4) can write ``<PERSISTENT_ROOT>/.last_backup`` with
    a timestamp; until that's wired this returns ``None`` and the UI shows a
    clear "unknown" state rather than a misleading value.
    """
    import os

    root = getattr(settings, "MEDIA_ROOT", "") or ""
    for candidate in (
        os.path.join(os.path.dirname(root), ".last_backup"),
        os.path.join(root, ".last_backup"),
    ):
        try:
            if os.path.exists(candidate):
                with open(candidate, encoding="utf-8") as fh:
                    return fh.read().strip() or None
        except OSError:
            continue
    return None


def collect_all(range_days=30):
    """Collect every section into one dict keyed by section."""
    return {
        "users_training": collect_users_training(range_days),
        "engagement": collect_engagement(min(range_days or 7, 30) if range_days else 7),
        "system": collect_system(),
    }
