"""CrashTech's own authentication screens (spec Rule 2.2.2).

The `User` table is shared with the rest of the site, and nothing else is.
These are CrashTech's own pages in CrashTech's own chrome, so a visitor
never meets another product's branding mid-flow: somebody signing up for a
Technion hackathon should have no reason to learn that babook exists.

Sign-up sends no verification mail. The audience is people who were given
a link to an event, and the gate that matters is the organiser accepting
their registration (Rule 5.1), not an inbox round-trip.
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.contrib.auth.views import (
    PasswordResetCompleteView as DjangoPasswordResetCompleteView,
)
from django.contrib.auth.views import (
    PasswordResetConfirmView as DjangoPasswordResetConfirmView,
)
from django.contrib.auth.views import PasswordResetDoneView as DjangoPasswordResetDoneView
from django.contrib.auth.views import PasswordResetView as DjangoPasswordResetView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy


class LoginView(DjangoLoginView):
    template_name = "crashtech/auth/login.html"
    redirect_authenticated_user = True

    def get_form(self, form_class=None):
        """People know their email address; they do not know the username
        Django derived from it."""
        form = super().get_form(form_class)
        form.fields["username"].label = "Email"
        return form


class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy("crashtech:home")


class PasswordResetView(DjangoPasswordResetView):
    template_name = "crashtech/auth/password_reset.html"
    email_template_name = "crashtech/auth/password_reset_email.txt"
    subject_template_name = "crashtech/auth/password_reset_subject.txt"
    success_url = reverse_lazy("crashtech:password_reset_done")


class PasswordResetDoneView(DjangoPasswordResetDoneView):
    template_name = "crashtech/auth/password_reset_done.html"


class PasswordResetConfirmView(DjangoPasswordResetConfirmView):
    template_name = "crashtech/auth/password_reset_confirm.html"
    success_url = reverse_lazy("crashtech:password_reset_complete")


class PasswordResetCompleteView(DjangoPasswordResetCompleteView):
    template_name = "crashtech/auth/password_reset_complete.html"


def signup(request):
    """Email and password, working immediately, no verification mail.

    The username is derived rather than asked for: one fewer field, and
    nobody has ever enjoyed being told their chosen username is taken.
    """
    errors = {}
    email = ""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""

        if not email or "@" not in email:
            errors["email"] = "Enter an email address."
        elif User.objects.filter(email__iexact=email).exists():
            errors["email"] = "There is already an account with this email. Sign in instead."
        if len(password) < 8:
            errors["password"] = "Use at least 8 characters."

        if not errors:
            base = email.split("@")[0][:140] or "user"
            username, i = base, 2
            while User.objects.filter(username=username).exists():
                username, i = f"{base}{i}", i + 1
            user = User.objects.create_user(username=username, email=email, password=password)
            # The backend has to be named: this site configures more than
            # one (allauth sits alongside the model backend), and `login()`
            # refuses to guess. Without it every single sign-up 500s, which
            # is what the C.1 suite caught.
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Welcome to CrashTech.")
            # An invitation redeems itself here, so somebody invited as a
            # judge lands already holding the role rather than on a page
            # wondering what they are looking at (Rule 4.3).
            from .invitations import redeem_for

            redeem_for(user)
            return redirect(request.GET.get("next") or "crashtech:home")

    return render(request, "crashtech/auth/signup.html", {"errors": errors, "email": email})
