"""Sign in, sign up and sign out in the app's own look (REQ-C.6). The accounts
are the site's shared User; nothing about access is decided here."""

from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, SignupForm


def safe_next(request, default="/cohort/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and nxt.startswith("/cohort/") and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return default


class LoginView(auth.LoginView):
    template_name = "cohort/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_redirect_url(self):
        return safe_next(self.request, default="")

    def get_default_redirect_url(self):
        return safe_next(self.request)


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("cohort:door")


def signup(request):
    if request.user.is_authenticated:
        return redirect(safe_next(request))
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(safe_next(request))
    return render(request, "cohort/signup.html", {"form": form, "next": safe_next(request, default="")})
