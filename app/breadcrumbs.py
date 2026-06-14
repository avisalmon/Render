"""Global breadcrumb trails (REQ-7.4.1 / QA-16).

A single source of truth mapping each URL name to its place in the site
hierarchy, so every view renders a consistent "you are here" trail + back
button at the top — instead of the old per-template, mostly-missing approach.

Each trail is the chain of ancestor sections for that page, top-first, as
(label, url_name) tuples. The context processor prepends "בית" (home) and
marks the final crumb (the current page) active. Dynamic detail pages
(course / project / profile / thread …) override the trail in-template via
``{% block breadcrumb %}`` so they can show the real title; the entries here
are their static fallback.
"""

HOME = ("בית", "home")

# url_name -> ancestor/section trail (current page is the LAST tuple).
TRAILS = {
    # top-level sections
    "courses_catalog": [("הדרכות", "courses_catalog")],
    "courses_domain": [("הדרכות", "courses_catalog"), ("תחום", None)],
    "courses_track": [("הדרכות", "courses_catalog"), ("מסלול", None)],
    "courses_detail": [("הדרכות", "courses_catalog"), ("קורס", None)],
    "courses_lesson": [("הדרכות", "courses_catalog"), ("קורס", None), ("שיעור", None)],
    "course_detail": [("הדרכות", "courses_catalog"), ("קורס", None)],
    "lesson_view": [("הדרכות", "courses_catalog"), ("קורס", None), ("שיעור", None)],
    "corporate": [("לעסקים", "corporate")],
    "pricing": [("מחירים ומסלולים", "pricing")],
    "chat_page": [("צ׳אט AI", "chat_page")],
    "certificate_view": [("תעודה", None)],
    # profile / account
    "profile": [("הפרופיל שלי", "profile")],
    "delete_account": [("הפרופיל שלי", "profile"), ("מחיקת חשבון", None)],
    "resend_verification": [("הפרופיל שלי", "profile"), ("אימות אימייל", None)],
    # community
    "community": [("קהילה", "community")],
    "community_guidelines": [("קהילה", "community"), ("כללי הקהילה", None)],
    "community_leaderboard": [("קהילה", "community"), ("טבלת מובילים", None)],
    "community_notifications": [("קהילה", "community"), ("התראות", None)],
    "community_members": [("קהילה", "community"), ("חברים", None)],
    "community_profile": [("קהילה", "community"), ("חברים", "community_members"), ("פרופיל", None)],
    # events (EPIC-6.7)
    "events_page": [("קהילה", "community"), ("אירועים", "events_page")],
    "event_detail": [("קהילה", "community"), ("אירועים", "events_page"), ("אירוע", None)],
    "event_create": [("קהילה", "community"), ("אירועים", "events_page"), ("חדש", None)],
    # chat (EPIC-6.6)
    "chat_home": [("קהילה", "community"), ("צ'אט", "chat_home")],
    "channel_view": [("קהילה", "community"), ("צ'אט", "chat_home"), ("ערוץ", None)],
    # tips
    "tips_list": [("קהילה", "community"), ("טיפים", "tips_list")],
    "tip_detail": [("קהילה", "community"), ("טיפים", "tips_list"), ("טיפ", None)],
    # forum
    "forum_home": [("קהילה", "community"), ("פורום", "forum_home")],
    "forum_new": [("קהילה", "community"), ("פורום", "forum_home"), ("שאלה חדשה", None)],
    "forum_thread": [("קהילה", "community"), ("פורום", "forum_home"), ("דיון", None)],
    # showcase
    "showcase_wall": [("קהילה", "community"), ("דוכן השוויץ", "showcase_wall")],
    "showcase_stand": [("קהילה", "community"), ("דוכן השוויץ", "showcase_wall"), ("דוכן", None)],
    "showcase_feed": [("קהילה", "community"), ("דוכן השוויץ", "showcase_wall"), ("Feed", None)],
    "showcase_new": [("קהילה", "community"), ("דוכן השוויץ", "showcase_wall"), ("פרויקט חדש", None)],
    "showcase_project": [("קהילה", "community"), ("דוכן השוויץ", "showcase_wall"), ("פרויקט", None)],
    "showcase_edit": [("קהילה", "community"), ("דוכן השוויץ", "showcase_wall"), ("עריכת פרויקט", None)],
    # messages
    "messages_inbox": [("קהילה", "community"), ("הודעות", "messages_inbox")],
    "messages_thread": [("קהילה", "community"), ("הודעות", "messages_inbox"), ("שיחה", None)],
    # studio
    "studio_home": [("אולפן", "studio_home")],
    "studio_course_create": [("אולפן", "studio_home"), ("קורס חדש", None)],
    "studio_new_from_video": [("אולפן", "studio_home"), ("קורס מסרטון", None)],
    "studio_course_edit": [("אולפן", "studio_home"), ("עריכת קורס", None)],
    "studio_lesson_new": [("אולפן", "studio_home"), ("עריכת קורס", None), ("שיעור חדש", None)],
    "studio_lesson_edit": [("אולפן", "studio_home"), ("עריכת קורס", None), ("עריכת שיעור", None)],
    "studio_job": [("אולפן", "studio_home"), ("עיבוד", None)],
    # crashtech (EPIC-6.5) — folded under קהילה (REQ-6.12.9)
    "crashtech_home": [("קהילה", "community"), ("CrashTech", "crashtech_home")],
    "crashtech_create": [("קהילה", "community"), ("CrashTech", "crashtech_home"), ("האקתון חדש", None)],
    "crashtech_detail": [("קהילה", "community"), ("CrashTech", "crashtech_home"), ("האקתון", None)],
    "crashtech_manage": [("קהילה", "community"), ("CrashTech", "crashtech_home"), ("ניהול", None)],
    # apex placeholders
    "services": [("שירותים", None)],
    "workshops": [("סדנאות", None)],
    "nostalgia": [("נוסטלגיה", None)],
    "research": [("מחקר", None)],
}

# Pages that are intentionally chrome-free (no breadcrumb bar): the homepage,
# auth, and the immersive onboarding flow.
NO_BREADCRUMB = {
    "home", "login", "register", "join_wall",
    "welcome", "welcome_basics", "welcome_chat", "welcome_complete", "welcome_skip",
    "verify_email",
}


def build(request):
    """Return ``auto_breadcrumbs`` (list of {label, url_name, active}) for the
    current request, or an empty list for chrome-free / unmapped pages."""
    match = getattr(request, "resolver_match", None)
    if match is None:
        return []
    name = match.url_name
    if name in NO_BREADCRUMB:
        return []
    trail = TRAILS.get(name)
    if trail is None:
        return []
    crumbs = [HOME] + list(trail)
    out = []
    last = len(crumbs) - 1
    for i, (label, url_name) in enumerate(crumbs):
        out.append({
            "label": label,
            # current page (last) is never a link, regardless of its url_name
            "url_name": None if i == last else url_name,
            "active": i == last,
        })
    return out
