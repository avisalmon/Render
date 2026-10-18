"""Books' pages. SPR-BK1.1: onboarding and the (empty) library."""

from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .access import books_page, profile_for
from .auth_views import safe_next
from .forms import OnboardingForm


def onboarding(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('books:login')}?next={reverse('books:onboarding')}")
    if profile_for(request.user) is not None:
        return redirect(safe_next(request))
    if request.method == "POST":
        form = OnboardingForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.is_adult_confirmed = True
            profile.accepted_terms_at = timezone.now()
            profile.save()
            return redirect(safe_next(request))
    else:
        guess = request.user.first_name or request.user.get_username().split("@")[0]
        form = OnboardingForm(initial={"display_name": guess, "language": "he"})
    return render(request, "books/onboarding.html", {"form": form, "next": safe_next(request, default="")})


@books_page
def home(request):
    return render(request, "books/home.html", {"profile": request.books_profile})


def terms(request):
    return render(request, "books/terms.html")


def privacy(request):
    return render(request, "books/privacy.html")
