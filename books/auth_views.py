"""Sign in, sign up, sign out and password reset, in Books' own look
(spec BK1 §1.5). The accounts underneath are the site's shared User."""

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .strings import text as t
from .forms import BooksLoginForm, BooksPasswordResetForm, BooksSetPasswordForm, BooksSignupForm


def safe_next(request, default="/books/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) and nxt.startswith("/books/"):
        return nxt
    return default


def _lang(request):
    return getattr(request, "books_lang", "he")


class _LangForm:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["lang"] = _lang(self.request)
        return kwargs


class LoginView(_LangForm, auth.LoginView):
    template_name = "books/auth/login.html"
    authentication_form = BooksLoginForm
    redirect_authenticated_user = True

    def get_redirect_url(self):
        # Django follows any same-site `next`; Books only follows one that
        # stays inside Books (Rule 3).
        return safe_next(self.request, default="")

    def get_default_redirect_url(self):
        return safe_next(self.request)

    def get_context_data(self, **kwargs):
        from . import friends

        ctx = super().get_context_data(**kwargs)
        invite = friends.pending_invite(self.request)
        ctx["inviter"] = invite.inviter if invite else None  # the way in says who is waiting (Avi, 2026-10-22)
        return ctx


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("books:login")


SIGNUPS_PER_HOUR = 10


def _signups_allowed(request):
    """At most a handful of new accounts an hour from one address."""
    import hashlib

    from django.core.cache import cache

    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or request.META.get("REMOTE_ADDR", "")).strip()
    key = "books:signups:" + hashlib.sha256(ip.encode()).hexdigest()[:16]
    n = cache.get(key, 0)
    if n >= int(getattr(settings, "BOOKS_SIGNUPS_PER_HOUR", SIGNUPS_PER_HOUR)):
        return False
    cache.set(key, n + 1, 3600)
    return True


def signup(request):
    if request.user.is_authenticated:
        return redirect(safe_next(request))
    nxt = safe_next(request, default="")
    if request.method == "POST":
        form = BooksSignupForm(request.POST, lang=_lang(request))
        if not _signups_allowed(request):  # a script making accounts (security review, 2026-10-24)
            form.add_error(None, t("signup.err.rate", _lang(request)))
        elif form.is_valid():
            user = form.save()
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect(nxt or "books:onboarding")
    else:
        form = BooksSignupForm(lang=_lang(request))
    return render(request, "books/auth/signup.html", {"form": form, "next": nxt})


class PasswordResetView(_LangForm, auth.PasswordResetView):
    form_class = BooksPasswordResetForm
    template_name = "books/auth/password_reset_form.html"
    email_template_name = "books/auth/password_reset_email.txt"
    subject_template_name = "books/auth/password_reset_subject.txt"
    success_url = reverse_lazy("books:password_reset_done")

    def get_extra_email_context(self):
        return {"books_lang": _lang(self.request)}

    def form_valid(self, form):
        self.extra_email_context = self.get_extra_email_context()
        return super().form_valid(form)


class PasswordResetDoneView(auth.PasswordResetDoneView):
    template_name = "books/auth/password_reset_done.html"


class PasswordResetConfirmView(_LangForm, auth.PasswordResetConfirmView):
    form_class = BooksSetPasswordForm
    template_name = "books/auth/password_reset_confirm.html"
    success_url = reverse_lazy("books:password_reset_complete")


class PasswordResetCompleteView(auth.PasswordResetCompleteView):
    template_name = "books/auth/password_reset_complete.html"
