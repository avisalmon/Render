"""Sign in, sign up and sign out in the gallery's own look (REQ-G.3). The
accounts are the site's shared User; a new account can do everything at once."""

from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, SignupForm
from .views import _safe_next


class LoginView(auth.LoginView):
    template_name = "gallery/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["language"] = getattr(self.request, "gallery_language", "he")
        return kwargs

    def get_redirect_url(self):
        return _safe_next(self.request, default="")

    def get_default_redirect_url(self):
        return _safe_next(self.request)


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("gallery:home")


def signup(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))
    form = SignupForm(request.POST or None, language=request.gallery_language)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(_safe_next(request))
    return render(request, "gallery/signup.html", {"form": form, "next": _safe_next(request, default="")})
