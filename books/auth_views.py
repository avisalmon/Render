"""Sign in, sign up, sign out and password reset, in Books' own look
(spec BK1 §1.5). The accounts underneath are the site's shared User."""

from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import BooksLoginForm, BooksPasswordResetForm, BooksSetPasswordForm, BooksSignupForm


def safe_next(request, default="/books/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) and nxt.startswith("/books/"):
        return nxt
    return default


class LoginView(auth.LoginView):
    template_name = "books/auth/login.html"
    authentication_form = BooksLoginForm
    redirect_authenticated_user = True

    def get_redirect_url(self):
        # Django follows any same-site `next`; Books only follows one that
        # stays inside Books (Rule 3).
        return safe_next(self.request, default="")

    def get_default_redirect_url(self):
        return safe_next(self.request)


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("books:login")


def signup(request):
    if request.user.is_authenticated:
        return redirect(safe_next(request))
    nxt = safe_next(request, default="")
    if request.method == "POST":
        form = BooksSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect(nxt or "books:onboarding")
    else:
        form = BooksSignupForm()
    return render(request, "books/auth/signup.html", {"form": form, "next": nxt})


class PasswordResetView(auth.PasswordResetView):
    form_class = BooksPasswordResetForm
    template_name = "books/auth/password_reset_form.html"
    email_template_name = "books/auth/password_reset_email.txt"
    subject_template_name = "books/auth/password_reset_subject.txt"
    success_url = reverse_lazy("books:password_reset_done")


class PasswordResetDoneView(auth.PasswordResetDoneView):
    template_name = "books/auth/password_reset_done.html"


class PasswordResetConfirmView(auth.PasswordResetConfirmView):
    form_class = BooksSetPasswordForm
    template_name = "books/auth/password_reset_confirm.html"
    success_url = reverse_lazy("books:password_reset_complete")


class PasswordResetCompleteView(auth.PasswordResetCompleteView):
    template_name = "books/auth/password_reset_complete.html"
