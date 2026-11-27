"""Sign in, sign up and sign out in breakout's own look. The accounts are
the site's shared User; a new account can do everything at once."""

from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, SignupForm


def safe_next(request, default="/breakout/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt.startswith("/breakout/") and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return default


class LoginView(auth.LoginView):
    template_name = "breakout/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_redirect_url(self):
        return safe_next(self.request, default="")

    def get_default_redirect_url(self):
        return safe_next(self.request)


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("breakout:home")


def signup(request):
    if request.user.is_authenticated:
        return redirect(safe_next(request))
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("breakout:welcome")  # a new account is not a teacher yet (spec 9)
    return render(request, "breakout/signup.html", {"form": form, "next": safe_next(request, default="")})
