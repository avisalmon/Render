"""dentist's own sign-in screens against the site's shared accounts
(spec Rule 2.4).

No sign-up here, on purpose: a member exists because an administrator
invited them (Rule 3.2) and a patient because the clinic made them a link
(Rule 3.4). Both arrive through their own routes in later sprints. What this
file gives every persona is a door in the clinic's own chrome: email and
password, Google through the site's existing provider, sign-out, and a
password reset whose mail links back inside `/dentist/`.
"""

from django.contrib.auth import views as auth
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.urls import reverse_lazy


class EmailLoginForm(AuthenticationForm):
    """People know their email address; they do not know the username the
    site derived from it."""

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("pk").first()
            if match:
                self.cleaned_data["username"] = match.username
        return super().clean()


class LoginView(auth.LoginView):
    template_name = "dentist/auth/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True
    # Without this Django falls back to the project's LOGIN_REDIRECT_URL,
    # which is babook's front page: a dentist signing in landed outside the
    # clinic. The D.1 suite caught it.
    next_page = reverse_lazy("dentist:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # The site's Google provider, landing back inside the clinic.
        context["google_url"] = "/accounts/google/login/?process=login&next=" + (
            self.request.GET.get("next") or "/dentist/"
        )
        return context


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("dentist:home")


class PasswordResetView(auth.PasswordResetView):
    template_name = "dentist/auth/password_reset.html"
    email_template_name = "dentist/auth/password_reset_email.txt"
    subject_template_name = "dentist/auth/password_reset_subject.txt"
    success_url = reverse_lazy("dentist:password_reset_done")


class PasswordResetDoneView(auth.PasswordResetDoneView):
    template_name = "dentist/auth/password_reset_done.html"


class PasswordResetConfirmView(auth.PasswordResetConfirmView):
    template_name = "dentist/auth/password_reset_confirm.html"
    success_url = reverse_lazy("dentist:password_reset_complete")


class PasswordResetCompleteView(auth.PasswordResetCompleteView):
    template_name = "dentist/auth/password_reset_complete.html"
