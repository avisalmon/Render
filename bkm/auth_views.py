"""Sign in, sign up and sign out in the app's own look (REQ-B.3). Google comes
first and is encouraged; email and password is there, folded away. The
account is babook's one shared User, so signing in here is signing in to
every babook app."""

from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, SignupForm


def safe_next(request, default="/bkm/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt.startswith("/bkm/") and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return default


class LoginView(auth.LoginView):
    template_name = "bkm/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_redirect_url(self):
        return safe_next(self.request, default="")

    def get_default_redirect_url(self):
        return safe_next(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = safe_next(self.request)
        return ctx


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("bkm:wall")


def signup(request):
    if request.user.is_authenticated:
        return redirect(safe_next(request))
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(safe_next(request))
    return render(request, "bkm/signup.html", {"form": form, "next": safe_next(request)})
