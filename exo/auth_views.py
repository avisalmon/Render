"""Signing in and asking for access, inside exo's own walls.

A visitor never sees babook's branded login mid-flow (building_an_app.md
Rule 3) — but the account underneath is the site's one shared `User`, and
Google sign-in goes through the site's existing allauth flow with a `next`
that lands back inside /exo/.
"""

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .access import is_exo_member, membership_for
from .forms import JoinForm
from .models import Membership


class LoginView(auth_views.LoginView):
    template_name = "exo/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("exo:concepts")


def logout_view(request):
    auth_logout(request)
    return redirect("exo:home")


def join(request):
    """Request access: create the account if needed, then queue for approval.

    Already a member? Straight to the builder — a member who clicks the public
    "build" button should not be shown a request form for something they
    already have.
    """
    if is_exo_member(request.user):
        return redirect("exo:concepts")
    if request.user.is_authenticated:
        membership = membership_for(request.user, create=True)
        if membership.status == Membership.Status.DENIED:
            return render(request, "exo/denied.html", status=403)
        return redirect("exo:waiting")

    form = JoinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        membership_for(user, create=True)
        return redirect("exo:waiting")

    return render(request, "exo/join.html", {"form": form})


def waiting(request):
    """The waiting room. Calm, and honest that nothing else is open yet."""
    if not request.user.is_authenticated:
        return redirect("exo:join")
    if is_exo_member(request.user):
        return redirect("exo:concepts")
    membership = membership_for(request.user)
    if membership is not None and membership.status == Membership.Status.DENIED:
        return render(request, "exo/denied.html", status=403)
    return render(request, "exo/waiting.html")
