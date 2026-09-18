"""Auth forms in SensorLab's own voice, in whichever language the page is.

**Why the copy is set here at all.** This project is Hebrew-first
(`LANGUAGE_CODE = "he"`), so Django's `AuthenticationForm` and
`UserCreationForm` render their built-in labels through the *site's*
catalogue — which is how "שם משתמש" ended up inside a page whose
`<html lang>` said `en` (SL-A2).

**Why it takes a language (SL-A5).** Owning the copy fixed the English page
and broke the Hebrew one: the labels were then English on every page,
including the Hebrew sign-in. Found by looking at it. So the copy lives in
`strings.py` beside the rest of the interface, and the form is told which
language the request is running under.

Django's *validation* messages are a different thing and need no help here:
they are raised inside Django, and `SensorLabLanguageMiddleware` runs the
whole request under the right language, so they follow on their own.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .strings import DEFAULT_LANGUAGE
from .strings import text as _


def _language_of(request):
    return getattr(request, "sensorlab_language", DEFAULT_LANGUAGE)


def _dress(field, label, placeholder="", help_text=""):
    field.label = label
    field.help_text = help_text
    field.widget.attrs.setdefault("class", "sl-input")
    if placeholder:
        field.widget.attrs.setdefault("placeholder", placeholder)


class SensorLabLoginForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        # AuthenticationForm is handed the request by Django's LoginView, so
        # the language is already here — nothing extra to wire.
        lang = _language_of(request)
        _dress(self.fields["username"], _("form.username", lang), _("form.username_hint", lang))
        _dress(self.fields["password"], _("form.password", lang), _("form.password_hint", lang))


class SensorLabSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, language=DEFAULT_LANGUAGE, **kwargs):
        super().__init__(*args, **kwargs)
        _dress(self.fields["username"], _("form.username", language), _("form.username_pick", language))
        _dress(self.fields["email"], _("form.email", language), _("form.email_hint", language))
        _dress(
            self.fields["password1"],
            _("form.password", language),
            _("form.password_pick_hint", language),
            _("form.password_help", language),
        )
        _dress(
            self.fields["password2"],
            _("form.password_again", language),
            _("form.password_again_hint", language),
        )
