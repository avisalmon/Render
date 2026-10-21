"""Books' pages: onboarding, the library, settings, my data, the staff design page."""

import json

from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import books_page, profile_for
from .auth_views import safe_next
from .forms import OnboardingForm, SettingsForm
from .middleware import LANG_SESSION_KEY, THEME_SESSION_KEY, THEMES
from .models import Profile
from .strings import LANGUAGES
from .strings import text as t


def _lang(request):
    return getattr(request, "books_lang", "he")


def onboarding(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('books:login')}?next={reverse('books:onboarding')}")
    if profile_for(request.user) is not None:
        return redirect(safe_next(request))
    if request.method == "POST":
        form = OnboardingForm(request.POST, lang=_lang(request))
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.is_adult_confirmed = True
            profile.accepted_terms_at = timezone.now()
            profile.save()
            if profile.area_name and profile.area_lat is None:
                from . import hub

                hub.area_changed(profile)
            from urllib.parse import urlencode

            return redirect(f"{reverse('books:taste')}?{urlencode({'first': 1, 'next': safe_next(request)})}")
    else:
        guess = request.user.first_name or request.user.get_username().split("@")[0]
        form = OnboardingForm(initial={"display_name": guess, "language": _lang(request)}, lang=_lang(request))
    return render(request, "books/onboarding.html", {"form": form, "next": safe_next(request, default="")})


def home(request):
    """Signed in: my shelf. A visitor: what Books is, and one way in."""
    if not request.user.is_authenticated:
        return landing(request)
    return _home(request)


DEMO_SHELF = [
    ("הנסיך הקטן", "אנטואן דה סנט-אכזופרי"), ("סיפור על אהבה וחושך", "עמוס עוז"), ("קיצור תולדות האנושות", "יובל נח הררי"),
    ("מאה שנים של בדידות", "גבריאל גרסיה מרקס"), ("מישהו לרוץ איתו", "דוד גרוסמן"), ("הארי פוטר ואבן החכמים", "ג'יי קיי רולינג"),
    ("אנה קרנינה", "לב טולסטוי"), ("שלושה בסירה אחת", "ג'רום ק. ג'רום"), ("החיים על פי אגפא", "אסף שור"),
    ("1984", "ג'ורג' אורוול"), ("חסמב\"ה", "יגאל מוסינזון"), ("הרוח בערבי הנחל", "קנת גרהם"),
]


def landing(request):
    from . import shelf

    rows = []
    for i, (title, author) in enumerate(DEMO_SHELF):
        row = {"id": -(i + 1), "title": title, "author": author, "status": "public", "rare": False, "url": ""}
        row.update(shelf.spine_for(9000 + i, title))
        rows.append(row)
    return render(request, "books/landing.html", {"books_json": json.dumps(rows, ensure_ascii=False)})


HEBREW_DAYS = ["ב", "ג", "ד", "ה", "ו", "ש", "א"]  # Monday first, as date.weekday() counts
ENGLISH_DAYS = ["M", "T", "W", "T", "F", "S", "S"]


def _streak_moment(request, profile):
    """The Duolingo-style moment after the sitting that made today count."""
    if request.GET.get("streak") != "1":
        return None
    from datetime import timedelta

    from . import play
    from .models import ReadingCheckin

    today = play.today()
    if not ReadingCheckin.objects.filter(profile=profile, day=today).exists():
        return None
    n = play.streak(profile)
    active = play._active_days(profile)
    names = HEBREW_DAYS if getattr(request, "books_lang", "he") == "he" else ENGLISH_DAYS
    week = [{"name": names[d.weekday()], "on": d in active, "today": d == today}
            for d in (today - timedelta(days=i) for i in range(6, -1, -1))]
    return {"n": n, "before": max(0, n - 1), "week": week}


def _just_finished(request, profile):
    from .models import ReadingSession

    pk = request.GET.get("finished") or ""
    if not pk.isdigit():
        return None
    return ReadingSession.objects.filter(pk=pk, profile=profile, finished_book=True).select_related("entry").first()


def _dial(profile):
    """The reading dial's ring (Avi chose it, 2026-10-21): today's reading
    toward the five minutes that count for the streak."""
    from . import play, reading

    seconds = reading.day_seconds(profile, play.today())
    goal = reading.MIN_STREAK_SECONDS
    return {"pct": min(100, round(seconds * 100 / goal)), "minutes": seconds // 60, "goal": goal // 60,
            "done": seconds >= goal}


def _dial_book(profile):
    from . import reading

    now = reading.active(profile)
    if now:
        return now.entry, now.start_page
    go_on = (reading.continue_list(profile, limit=1) or [None])[0]
    return (go_on["entry"], go_on["page"]) if go_on else (None, 0)


def _book_ring(profile, entry, page):
    """The dial's inner ring: how far into the book, when its length is known."""
    from . import reading

    if entry is None or not page:
        return None
    pages = reading.total_pages(entry)
    return {"pct": min(100, round(page * 100 / (pages or reading.ASSUMED_PAGES))), "assumed": not pages}


@books_page
def _home(request):
    from . import shelf

    profile = request.books_profile
    rows = shelf.shelf_books(profile)
    from . import play

    return render(request, "books/home.html", {
        "profile": profile, "books_json": json.dumps(rows, ensure_ascii=False), "count": len(rows),
        "play": play.summary(profile),
        "reading_now": __import__("books.reading", fromlist=["active"]).active(profile),
        "reading_today": __import__("books.reading", fromlist=["stats"]).stats(profile)["today_minutes"],
        "go_on": (__import__("books.reading", fromlist=["continue_list"]).continue_list(profile, limit=1) or [None])[0],
        "dial": _dial(profile),
        "just_finished": _just_finished(request, profile),
        "streak_moment": _streak_moment(request, profile),
        "book_pct": _book_ring(profile, *_dial_book(profile)),
    })


@books_page
def settings_page(request):
    profile = request.books_profile
    saved = False
    if request.method == "POST":
        before = profile.area_name
        form = SettingsForm(request.POST, instance=profile, lang=_lang(request))
        if form.is_valid():
            saved = form.save()
            if saved.area_name != before:
                from . import hub

                hub.area_changed(saved)
            # The language may have just changed: come back in the new one.
            return redirect(f"{reverse('books:settings')}?saved=1")
    else:
        form = SettingsForm(instance=profile, lang=_lang(request))
        saved = request.GET.get("saved") == "1"
    return render(request, "books/settings.html", {"form": form, "profile": profile, "saved": saved})


@require_POST
def set_language(request, code):
    """The header switch. Saves on the Profile when there is one, in the
    session otherwise, so a visitor's choice survives to onboarding."""
    if code not in LANGUAGES:
        raise Http404
    profile = profile_for(request.user)
    if profile is not None:
        profile.language = code
        profile.save(update_fields=["language"])
    request.session[LANG_SESSION_KEY] = code
    return redirect(safe_next(request))


@require_POST
def set_theme(request, theme):
    if theme not in THEMES:
        raise Http404
    profile = profile_for(request.user)
    if profile is not None:
        profile.theme = theme
        profile.save(update_fields=["theme"])
    request.session[THEME_SESSION_KEY] = theme
    return redirect(safe_next(request))


def terms(request):
    return render(request, "books/terms.html")


def privacy(request):
    return render(request, "books/privacy.html")


# ---- my data: download everything, delete everything (spec BK1 §1.7) --------

def owned_models():
    """Every Books model that points at a Profile, with the field that does.
    The export walks this list, so a new model is exported the day it exists
    (a test pins that nothing is left out)."""
    from django.apps import apps
    from django.db.models import ForeignKey, OneToOneField

    out = []
    for model in apps.get_app_config("books").get_models():
        if model is Profile:
            continue
        for f in model._meta.get_fields():
            if isinstance(f, (ForeignKey, OneToOneField)) and f.related_model is Profile:
                out.append((model, f.name))
                break
    return out


def export_payload(profile):
    """Everything Books holds about one person, as plain data."""
    payload = {
        "exported_at": timezone.now().isoformat(),
        "profile": {
            "display_name": profile.display_name, "language": profile.language, "tier": profile.tier,
            "area_name": profile.area_name,
            "area_lat": str(profile.area_lat) if profile.area_lat is not None else None,
            "area_lng": str(profile.area_lng) if profile.area_lng is not None else None,
            "radius_km": profile.radius_km, "is_adult_confirmed": profile.is_adult_confirmed,
            "accepted_terms_at": profile.accepted_terms_at.isoformat() if profile.accepted_terms_at else None,
            "profile_public": profile.profile_public, "show_points_public": profile.show_points_public,
            "theme": profile.theme, "palette": profile.palette, "shelf_view": profile.shelf_view,
            "created_at": profile.created_at.isoformat(),
        },
    }
    for model, field in owned_models():
        rows = model.objects.filter(**{field: profile}).values()
        payload[model._meta.model_name] = [
            {k: (v.isoformat() if hasattr(v, "isoformat") else (str(v) if hasattr(v, "quantize") else v)) for k, v in row.items()}
            for row in rows
        ]
    return payload


@books_page
def my_data(request):
    deleted_word = t("data.delete_word", _lang(request))
    error = None
    if request.method == "POST":
        if request.POST.get("confirm", "").strip().lower() == deleted_word.lower():
            request.books_profile.delete()
            return render(request, "books/my_data_deleted.html")
        error = t("data.delete_type", _lang(request))
    return render(request, "books/my_data.html", {"profile": request.books_profile, "error": error})


@books_page
def my_data_export(request):
    body = json.dumps(export_payload(request.books_profile), ensure_ascii=False, indent=2)
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="books-my-data.json"'
    return response


# ---- the design page (staff only, linked from nowhere) ----------------------

SAMPLE_BOOKS = {
    "he": [
        {"id": "s1", "title": "מיכאל שלי", "author": "עמוס עוז", "status": "lend", "color": "#6B2320", "ink": "#EFD9A8", "w": 30, "h": 176},
        {"id": "s2", "title": "החיים שלפנינו", "author": "רומן גארי", "status": "exchange", "color": "#24384A", "ink": "#E8DDC7", "w": 36, "h": 192, "lean": -0.8},
        {"id": "s3", "title": "זכרון דברים", "author": "יעקב שבתאי", "status": "lend", "color": "#2E4A3B", "ink": "#E8DDC7", "w": 34, "h": 186},
        {"id": "s4", "title": "אלטנוילנד", "author": "בנימין זאב הרצל", "status": "public", "color": "#5A1E1A", "ink": "#D8B46A", "w": 40, "h": 200, "rare": True},
        {"id": "s5", "title": "הנסיך הקטן", "author": "סנט-אכזופרי", "status": "private", "color": "#A68240", "ink": "#1A140E", "w": 26, "h": 150, "lean": 10},
        {"id": "s6", "title": "1984", "author": "ג׳ורג׳ אורוול", "status": "sell", "color": "#3C3C3C", "ink": "#EFE6D2", "w": 28, "h": 168, "lean": 0.6},
        {"id": "s7", "title": "סיפור פשוט", "author": "ש״י עגנון", "status": "private", "color": "#4A3B5C", "ink": "#E8DDC7", "w": 32, "h": 182},
        {"id": "s8", "title": "תמול שלשום", "author": "ש״י עגנון", "status": "exchange", "color": "#3D2A1E", "ink": "#D8B46A", "w": 42, "h": 196},
        {"id": "s9", "title": "כנרת", "author": "רחל", "status": "lend", "color": "#2B3442", "ink": "#E8DDC7", "w": 22, "h": 150, "lean": -1},
        {"id": "s10", "title": "הכפר", "author": "מאיר שלו", "status": "lend", "color": "#2E4A3B", "ink": "#E8DDC7", "w": 32, "h": 180, "lean": 0.5},
        {"id": "s11", "title": "אהבה בזמן פרעות", "author": "מאיר שלו", "status": "private", "color": "#6B2320", "ink": "#EFD9A8", "w": 28, "h": 160, "lean": 12},
    ],
    "en": [
        {"id": "s1", "title": "Middlemarch", "author": "George Eliot", "status": "lend", "color": "#2E4A3B", "ink": "#E8DDC7", "w": 38, "h": 192},
        {"id": "s2", "title": "Moby-Dick", "author": "Herman Melville", "status": "exchange", "color": "#24384A", "ink": "#E8DDC7", "w": 34, "h": 184, "lean": -0.8},
        {"id": "s3", "title": "Jane Eyre", "author": "Charlotte Brontë", "status": "private", "color": "#6B2320", "ink": "#EFD9A8", "w": 28, "h": 170},
        {"id": "s4", "title": "Ulysses", "author": "James Joyce", "status": "public", "color": "#5A1E1A", "ink": "#D8B46A", "w": 42, "h": 200, "rare": True},
        {"id": "s5", "title": "The Little Prince", "author": "Saint-Exupéry", "status": "private", "color": "#A68240", "ink": "#1A140E", "w": 24, "h": 150, "lean": 10},
        {"id": "s6", "title": "1984", "author": "George Orwell", "status": "sell", "color": "#3C3C3C", "ink": "#EFE6D2", "w": 28, "h": 168, "lean": 0.6},
        {"id": "s7", "title": "Walden", "author": "H. D. Thoreau", "status": "lend", "color": "#4A3B5C", "ink": "#E8DDC7", "w": 26, "h": 160},
        {"id": "s8", "title": "The Odyssey", "author": "Homer", "status": "exchange", "color": "#3D2A1E", "ink": "#D8B46A", "w": 40, "h": 196},
        {"id": "s9", "title": "Emma", "author": "Jane Austen", "status": "lend", "color": "#2B3442", "ink": "#E8DDC7", "w": 24, "h": 156, "lean": -1},
        {"id": "s10", "title": "Hamlet", "author": "Shakespeare", "status": "lend", "color": "#B08A48", "ink": "#1A140E", "w": 22, "h": 150, "lean": 12},
    ],
}


def design_entry(request):
    """Staff only. Anyone else sees Books' own 404, not a login bounce."""
    if not (request.user.is_authenticated and request.user.is_staff):
        raise Http404
    lang = _lang(request)
    return render(request, "books/design.html", {
        "sample_json": json.dumps(SAMPLE_BOOKS[lang], ensure_ascii=False),
        "sample_kicker": t("home.shelf_of", lang, name=t("design.sample_author", lang)),
        "sample_lifted": "s4",
        "sample_plate1": "1", "sample_plate2": "2",
    })
