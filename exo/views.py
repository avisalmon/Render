"""exo's pages.

The public half (landing, learn, museum) never asks anyone to sign in — the
one exception is the single "build" button, which is the only door into the
gated half (spec §1).
"""

from django.http import Http404
from django.shortcuts import redirect, render

from .middleware import SESSION_KEY
from .models import ExoAttribute, LearnResource
from .strings import LANGUAGES


def home(request):
    """The landing page: the framing, the formula, and the one way in."""
    attributes = list(ExoAttribute.objects.all())
    return render(request, "exo/home.html", {
        "mtp": next((a for a in attributes if a.category == ExoAttribute.Category.MTP), None),
        "scale": [a for a in attributes if a.category == ExoAttribute.Category.SCALE],
        "ideas": [a for a in attributes if a.category == ExoAttribute.Category.IDEAS],
    })


def learn(request):
    """All eleven attributes, plus the two extra blocks and the handout pages."""
    attributes = list(ExoAttribute.objects.all())
    pages = list(
        LearnResource.objects.filter(is_published=True, attribute__isnull=True)
    )
    return render(request, "exo/learn.html", {
        "mtp": next((a for a in attributes if a.category == ExoAttribute.Category.MTP), None),
        "scale": [a for a in attributes if a.category == ExoAttribute.Category.SCALE],
        "ideas": [a for a in attributes if a.category == ExoAttribute.Category.IDEAS],
        "extra": [a for a in attributes if a.category == ExoAttribute.Category.EXTRA],
        "pages": pages,
    })


def learn_attribute(request, key):
    """One principle: its summary, its book pointer, its videos."""
    attribute = ExoAttribute.objects.filter(key=key).first()
    if attribute is None:
        raise Http404
    resources = list(
        attribute.resources.filter(is_published=True)
    )
    return render(request, "exo/learn_attribute.html", {
        "attribute": attribute,
        "resources": resources,
    })


def learn_page(request, key):
    """One standalone handout page."""
    page = LearnResource.objects.filter(
        key=key, is_published=True, attribute__isnull=True,
    ).first()
    if page is None:
        raise Http404
    return render(request, "exo/learn_page.html", {"page": page})


def set_language(request, code):
    """The switch in the header (spec §0.3).

    A plain link rather than script, so it works for a visitor who has not
    signed in — the request-access page itself has to be readable in both
    languages, or the switch would only exist for people already inside.
    Saves to the profile when there is one, so the choice follows the person
    to another device; never *creates* a membership (see middleware).
    """
    if code not in LANGUAGES:
        raise Http404
    request.session[SESSION_KEY] = code
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        membership = getattr(user, "exo_membership", None)
        if membership is not None:
            membership.language = code
            membership.save(update_fields=["language"])

    nxt = request.GET.get("next") or ""
    # Only ever bounce back inside this app — an open redirect here would be a
    # gift to anyone who can get a link in front of a member.
    if nxt.startswith("/exo/"):
        return redirect(nxt)
    return redirect("exo:home")
