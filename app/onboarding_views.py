"""
EPIC-5 views: the context-aware registration wall (/join/) and the
post-signup onboarding flow (/welcome/ — AI interview + static fallback).
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Course, LearnerProfile
from .onboarding import (
    INTERVIEW_KEY,
    MAX_INTERVIEW_TURNS,
    ONBOARDING_NEXT_KEY,
    ONBOARDING_PENDING_KEY,
    interview_system_prompt,
    parse_interview_reply,
    recommend,
)
from .taxonomy import TRAINING_TAXONOMY


def _safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}):
        return value
    return ""


# ---------------------------------------------------------------------------
# /join/ — the context-aware wall (REQ-5.4.1, REQ-5.1.2)
# ---------------------------------------------------------------------------

def join_wall(request):
    """Registration wall for anonymous users hitting a gated action.
    Names what they wanted, offers social + email signup, preserves next."""
    if request.user.is_authenticated:
        return redirect(_safe_next(request, request.GET.get("next")) or "/")
    next_url = _safe_next(request, request.GET.get("next"))
    course = None
    slug = request.GET.get("course", "")
    if slug:
        course = Course.objects.filter(slug=slug, is_published=True).first()
    return render(request, "registration/join.html", {
        "course": course,
        "next": next_url,
    })


# ---------------------------------------------------------------------------
# /welcome/ — onboarding (REQ-5.5.*)
# ---------------------------------------------------------------------------

def _get_learner_profile(user):
    profile, _ = LearnerProfile.objects.get_or_create(user=user)
    return profile


@login_required
def welcome(request):
    """The onboarding page. Step 1 captures the basics (name, email,
    student/teacher) as a soft form; step 2 is the AI interview with the
    static fallback (REQ-5.5.7 / REQ-5.5.2)."""
    profile = _get_learner_profile(request.user)
    entry_course = None
    if profile.source_course:
        entry_course = Course.objects.filter(
            slug=profile.source_course, is_published=True
        ).first()
    domains = [
        {"key": k, "title": v["title"], "icon": v["icon"]}
        for k, v in sorted(TRAINING_TAXONOMY.items(), key=lambda kv: kv[1]["order"])
    ]
    from .ai_chat import _is_stub_mode
    return render(request, "app/welcome.html", {
        "learner": profile,
        "basics_needed": not profile.role_type,
        "prefill_name": request.user.profile.display_name or request.user.first_name,
        "prefill_email": request.user.email,
        "entry_course": entry_course,
        "domains": domains,
        "ai_available": not _is_stub_mode(),
        "next": request.session.get(ONBOARDING_NEXT_KEY, ""),
    })


@login_required
def welcome_basics(request):
    """Step 1 submit: name (saved to the user), email confirm + optional
    contact email, and student/teacher/other (REQ-5.5.7)."""
    if request.method != "POST":
        return redirect("welcome")
    profile = _get_learner_profile(request.user)
    name = request.POST.get("name", "").strip()[:150]
    if name:
        up = request.user.profile
        up.display_name = name
        up.save(update_fields=["display_name"])
        request.user.first_name = name.split()[0][:30]
    email = request.POST.get("email", "").strip()[:254]
    if email and "@" in email:
        request.user.email = email
    request.user.save(update_fields=["first_name", "email"])
    contact = request.POST.get("contact_email", "").strip()[:254]
    profile.contact_email = contact if "@" in contact else ""
    role = request.POST.get("role_type", "")
    profile.role_type = role if role in ("student", "teacher", "other") else "other"
    profile.save(update_fields=["contact_email", "role_type"])
    return redirect("welcome")


def _finish_onboarding(request, profile, completed):
    """Common completion: recommendation, timestamps, session cleanup.
    Returns the redirect target (preserved next wins, else first lesson)."""
    entry_course = None
    if profile.source_course:
        entry_course = Course.objects.filter(
            slug=profile.source_course, is_published=True
        ).first()
    track, course = recommend(profile.interests, profile.experience_level, entry_course)
    profile.recommended_track = track
    profile.recommended_course = course
    now = timezone.now()
    if completed:
        profile.onboarding_completed_at = now
    else:
        profile.onboarding_skipped_at = now
    profile.save()
    next_url = _safe_next(request, request.session.pop(ONBOARDING_NEXT_KEY, ""))
    request.session.pop(ONBOARDING_PENDING_KEY, None)
    request.session.pop(INTERVIEW_KEY, None)
    if completed:
        # The homepage shows the recommendation rail ONCE right after
        # onboarding; afterwards it lives on the profile page (REQ-5.6.3).
        from .onboarding import RECS_ONCE_KEY
        request.session[RECS_ONCE_KEY] = True
    if next_url:
        return next_url  # preserved intent always wins (REQ-5.4.2)
    # Land on the (one-time personalized) homepage - the user chooses where
    # to go, no auto-drop into a lesson (REQ-5.6.4).
    return "/"


@login_required
def welcome_chat(request):
    """One AI interview turn (REQ-5.5.2/5.5.3). History lives in the session.
    Returns {reply, done, redirect} or {fallback: true} when AI is unavailable
    or the turn budget is exhausted (REQ-5.5.4/5.5.6)."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    from .ai_chat import _is_stub_mode, call_openai
    if _is_stub_mode():
        return JsonResponse({"fallback": True})
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "bad json"}, status=400)

    history = request.session.get(INTERVIEW_KEY, [])
    user_turns = sum(1 for m in history if m["role"] == "user")
    if user_turns >= MAX_INTERVIEW_TURNS:
        return JsonResponse({"fallback": True})

    message = (data.get("message") or "").strip()[:1000]
    if message:
        history.append({"role": "user", "content": message})

    profile = _get_learner_profile(request.user)
    entry_title = ""
    if profile.source_course:
        c = Course.objects.filter(slug=profile.source_course).first()
        entry_title = c.title if c else ""
    system_prompt = interview_system_prompt(request.user, entry_title)

    result = call_openai(history or [{"role": "user", "content": "שלום"}],
                         system_prompt=system_prompt)
    visible, extracted = parse_interview_reply(result["content"])
    history.append({"role": "assistant", "content": result["content"]})
    request.session[INTERVIEW_KEY] = history

    if extracted:
        profile.interests = [
            d for d in extracted.get("interests", []) if d in TRAINING_TAXONOMY
        ]
        profile.goal = str(extracted.get("goal", ""))[:200]
        level = extracted.get("experience_level", "")
        profile.experience_level = level if level in ("beginner", "intermediate", "advanced") else ""
        profile.persona = str(extracted.get("persona", ""))[:200]
        profile.time_per_week = str(extracted.get("time_per_week", ""))[:50]
        target = _finish_onboarding(request, profile, completed=True)
        return JsonResponse({"reply": visible, "done": True, "redirect": target})

    return JsonResponse({"reply": visible, "done": False})


@login_required
def welcome_complete(request):
    """Static fallback form submit (REQ-5.5.4): 3 taps to the same profile."""
    if request.method != "POST":
        return redirect("welcome")
    profile = _get_learner_profile(request.user)
    interests = [d for d in request.POST.getlist("interests") if d in TRAINING_TAXONOMY]
    profile.interests = interests
    level = request.POST.get("experience_level", "")
    profile.experience_level = level if level in ("beginner", "intermediate", "advanced") else ""
    profile.goal = request.POST.get("goal", "").strip()[:200]
    profile.time_per_week = request.POST.get("time_per_week", "").strip()[:50]
    target = _finish_onboarding(request, profile, completed=True)
    return redirect(target)


@login_required
def welcome_skip(request):
    """Skip ('later') — resumable from the profile page (REQ-5.5.5).
    Recommendations still seed from the entry intent (REQ-5.2.3)."""
    if request.method != "POST":
        return redirect("welcome")
    profile = _get_learner_profile(request.user)
    target = _finish_onboarding(request, profile, completed=False)
    return redirect(target)
