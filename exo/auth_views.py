"""Signing in and asking for access, inside exo's own walls.

A visitor never sees babook's branded login mid-flow (building_an_app.md
Rule 3) — but the account underneath is the site's one shared `User`, and
Google sign-in goes through the site's existing allauth flow with a `next`
that lands back inside /exo/.
"""

from urllib.parse import quote

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy

from .access import is_exo_member, membership_for
from .concept_views import where_you_were
from .forms import JoinForm
from .models import Membership
from .views import safe_next


class LoginView(auth_views.LoginView):
    template_name = "exo/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        """Back to where they were, in order of how much it is worth.

        The page they were trying to reach first, then whatever they last
        worked on, and only then the list. Landing on a list after signing in
        mid-idea is how an app that lost nothing still feels like it forgot
        you.
        """
        wanted = safe_next(self.request.GET.get("next")
                           or self.request.POST.get("next"))
        if wanted:
            return wanted
        concept = where_you_were(self.request.user)
        if concept is not None:
            return reverse("exo:concept_resume", args=[concept.pk])
        return str(reverse_lazy("exo:concepts"))


def logout_view(request):
    auth_logout(request)
    return redirect("exo:home")


def join(request):
    """Request access: create the account if needed, then queue for approval.

    Already a member? Straight to the builder — a member who clicks the public
    "build" button should not be shown a request form for something they
    already have.
    """
    wanted = safe_next(request.GET.get("next") or request.POST.get("next"))
    if is_exo_member(request.user):
        return redirect(wanted or reverse("exo:concepts"))
    if request.user.is_authenticated:
        membership = membership_for(request.user, create=True)
        if membership.status == Membership.Status.DENIED:
            return render(request, "exo/denied.html", status=403)
        return redirect(reverse("exo:waiting") + (f"?next={quote(wanted)}" if wanted else ""))

    form = JoinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        membership_for(user, create=True)
        return redirect(reverse("exo:waiting") + (f"?next={quote(wanted)}" if wanted else ""))

    return render(request, "exo/join.html", {"form": form, "next": wanted})


def waiting(request):
    """The waiting room. Calm, and honest that nothing else is open yet."""
    wanted = safe_next(request.GET.get("next"))
    if not request.user.is_authenticated:
        return redirect("exo:join")
    if is_exo_member(request.user):
        # Approved while they were waiting: send them where they were going.
        return redirect(wanted or reverse("exo:concepts"))
    membership = membership_for(request.user)
    if membership is not None and membership.status == Membership.Status.DENIED:
        return render(request, "exo/denied.html", status=403)
    return render(request, "exo/waiting.html", {"next": wanted})
