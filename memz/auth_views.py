"""Sign in, sign up, sign out, and password reset, all in memz's own chrome
(spec Rule 3.3.2). The accounts underneath are the site's shared `User`."""

from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import MemzLoginForm, MemzPasswordResetForm, MemzSetPasswordForm, MemzSignupForm
from .tiers import profile_for


class LoginView(auth.LoginView):
    template_name = "memz/auth/login.html"
    authentication_form = MemzLoginForm
    redirect_authenticated_user = True
    next_page = reverse_lazy("memz:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        profile_for(self.request.user)   # Rule 3.3.4: on first use
        return response


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("memz:home")


def signup(request):
    if request.user.is_authenticated:
        return redirect("memz:home")
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = ""
    if request.method == "POST":
        form = MemzSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            profile_for(user)
            return redirect(next_url or "memz:home")
    else:
        form = MemzSignupForm()
    return render(request, "memz/auth/signup.html", {"form": form, "next": next_url})


class PasswordResetView(auth.PasswordResetView):
    form_class = MemzPasswordResetForm
    template_name = "memz/auth/password_reset_form.html"
    email_template_name = "memz/auth/password_reset_email.txt"
    subject_template_name = "memz/auth/password_reset_subject.txt"
    success_url = reverse_lazy("memz:password_reset_done")


class PasswordResetDoneView(auth.PasswordResetDoneView):
    template_name = "memz/auth/password_reset_done.html"


class PasswordResetConfirmView(auth.PasswordResetConfirmView):
    form_class = MemzSetPasswordForm
    template_name = "memz/auth/password_reset_confirm.html"
    success_url = reverse_lazy("memz:password_reset_complete")


class PasswordResetCompleteView(auth.PasswordResetCompleteView):
    template_name = "memz/auth/password_reset_complete.html"
