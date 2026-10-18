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
            return redirect(safe_next(request))
    else:
        guess = request.user.first_name or request.user.get_username().split("@")[0]
        form = OnboardingForm(initial={"display_name": guess, "language": _lang(request)}, lang=_lang(request))
    return render(request, "books/onboarding.html", {"form": form, "next": safe_next(request, default="")})


@books_page
def home(request):
    # The shelf draws from the person's copies (BK3). Until then it is empty.
    return render(request, "books/home.html", {"profile": request.books_profile, "books_json": "[]"})


@books_page
def settings_page(request):
    profile = request.books_profile
    saved = False
    if request.method == "POST":
        form = SettingsForm(request.POST, instance=profile, lang=_lang(request))
        if form.is_valid():
            form.save()
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
        {"id": "s5", "title": "הנסיך הקטן", "author": "סנט-אכזופרי", "status": "private", "color": "#8A6A2E", "ink": "#1A140E", "w": 26, "h": 150, "lean": 10},
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
        {"id": "s5", "title": "The Little Prince", "author": "Saint-Exupéry", "status": "private", "color": "#8A6A2E", "ink": "#1A140E", "w": 24, "h": 150, "lean": 10},
        {"id": "s6", "title": "1984", "author": "George Orwell", "status": "sell", "color": "#3C3C3C", "ink": "#EFE6D2", "w": 28, "h": 168, "lean": 0.6},
        {"id": "s7", "title": "Walden", "author": "H. D. Thoreau", "status": "lend", "color": "#4A3B5C", "ink": "#E8DDC7", "w": 26, "h": 160},
        {"id": "s8", "title": "The Odyssey", "author": "Homer", "status": "exchange", "color": "#3D2A1E", "ink": "#D8B46A", "w": 40, "h": 196},
        {"id": "s9", "title": "Emma", "author": "Jane Austen", "status": "lend", "color": "#2B3442", "ink": "#E8DDC7", "w": 24, "h": 156, "lean": -1},
        {"id": "s10", "title": "Hamlet", "author": "Shakespeare", "status": "lend", "color": "#7A5A24", "ink": "#1A140E", "w": 22, "h": 150, "lean": 12},
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
