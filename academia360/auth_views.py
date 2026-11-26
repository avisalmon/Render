"""Sign in and out in the app's own frame, against the site's shared accounts
(methodology: "a lighter front door is fine"). No sign-up here: a role comes
from the admin (Epic C adds the request-to-join door)."""

from django.contrib.auth import views as auth
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme


class EmailLoginForm(AuthenticationForm):
    """People know their email, not the username the site derived from it."""

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("pk").first()
            if match:
                self.cleaned_data["username"] = match.username
        return super().clean()


class LoginView(auth.LoginView):
    template_name = "academia360/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True
    next_page = reverse_lazy("academia360:home")

    def get_success_url(self):
        """`next` may only point back inside the app: never out of it, and
        never to another host."""
        nxt = self.request.POST.get("next") or self.request.GET.get("next") or ""
        if nxt.startswith("/academia360/") and url_has_allowed_host_and_scheme(
                nxt, allowed_hosts={self.request.get_host()}):
            return nxt
        return str(self.next_page)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nxt = self.request.GET.get("next") or "/academia360/"
        if not nxt.startswith("/academia360/"):
            nxt = "/academia360/"
        context["google_url"] = "/accounts/google/login/?process=login&next=" + nxt
        context["next"] = nxt
        return context


class LogoutView(auth.LogoutView):
    next_page = reverse_lazy("academia360:home")
