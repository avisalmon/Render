"""ustrip's own signup form (spec §3 sprint note).

Deliberately plain: username + email + password, Django's own password
validators, no email-verification step — unlike babook's public
`app.views.register`, ustrip is a five-person invite-by-Avi app, so a new
account works immediately and Avi grants `family` afterward. Still the same
shared `User` model as the rest of the site (spec §2.1) — just a lighter
front door onto it.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class UstripSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")
