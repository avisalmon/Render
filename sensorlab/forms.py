"""Auth forms in SensorLab's own voice. The accounts underneath are the
site's shared `User` (Rule 2).

**Why every label and help string is set explicitly here.** This project is
Hebrew-first (`LANGUAGE_CODE = "he"`), so Django's own `AuthenticationForm`
and `UserCreationForm` render their built-in labels through the site's
translation catalogue — which put "שם משתמש" and "סיסמה" inside a page
whose `<html lang>` said `en`. SensorLab's language is neither the site's
setting nor the browser's guess: it is the person's own choice, stored on
their profile. So SensorLab owns this copy outright, and SL-A5 translates
it from SensorLab's own catalogue.

What this does NOT cover: Django's *validation* messages ("This field is
required") still come from the site's catalogue, because they are raised
deep inside Django rather than declared here. Fixing those properly means
activating the profile's language for the request — which is SL-A5's job,
and is why that sprint's scope now says so explicitly.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


def _dress(field, label, placeholder="", help_text=""):
    field.label = label
    field.help_text = help_text
    field.widget.attrs.setdefault("class", "sl-input")
    if placeholder:
        field.widget.attrs.setdefault("placeholder", placeholder)


class SensorLabLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _dress(self.fields["username"], "Username", "your username")
        _dress(self.fields["password"], "Password", "your password")


class SensorLabSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _dress(self.fields["username"], "Username", "pick a username")
        _dress(self.fields["email"], "Email", "you@example.com")
        _dress(
            self.fields["password1"],
            "Password",
            "at least 8 characters",
            "At least 8 characters, and not something a stranger would guess.",
        )
        _dress(self.fields["password2"], "Password again", "type it once more")
