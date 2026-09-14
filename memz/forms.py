"""memz's own front door onto the shared User table (spec §3.3).

Sign-up is email plus password and works immediately: no verification
mail, because memz is not the public site's open registration and a person
joining a game from a friend's phone should not be waiting on an inbox.
The username is derived from the email, the same convention babook uses,
so nobody has to invent one and the same person can sign in anywhere on
the site with the same email.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

User = get_user_model()


def username_from_email(email):
    """A unique username from the email's local part."""
    base = slugify(email.split("@")[0]) or "memz"
    base = base[:140]
    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base}{i}"
    return username


class MemzLoginForm(AuthenticationForm):
    """Django's form, accepting the email in the username box (Rule 3.3.1)."""

    error_messages = {
        "invalid_login": _("האימייל או הסיסמה לא נכונים. נסו שוב."),
        "inactive": _("החשבון הזה לא פעיל."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("אימייל")
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username", "inputmode": "email", "autofocus": True, "class": "memz-input"}
        )
        self.fields["password"].label = _("סיסמה")
        self.fields["password"].widget.attrs.update({"autocomplete": "current-password", "class": "memz-input"})

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("id").first()
            if match is not None:
                self.cleaned_data["username"] = match.get_username()
        return super().clean()


class MemzSignupForm(forms.Form):
    name = forms.CharField(
        label=_("איך קוראים לך?"), max_length=40, required=False,
        widget=forms.TextInput(attrs={"autocomplete": "given-name", "class": "memz-input"}),
    )
    email = forms.EmailField(
        label=_("אימייל"),
        widget=forms.EmailInput(attrs={"autocomplete": "email", "inputmode": "email", "class": "memz-input"}),
    )
    password1 = forms.CharField(
        label=_("סיסמה"), strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "memz-input"}),
    )
    password2 = forms.CharField(
        label=_("עוד פעם, ליתר ביטחון"), strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "memz-input"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("יש כבר חשבון עם האימייל הזה. אפשר פשוט להיכנס."))
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("הסיסמאות לא זהות."))
        elif p1:
            try:
                validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        user = User.objects.create_user(
            username=username_from_email(email), email=email, password=self.cleaned_data["password1"],
        )
        name = (self.cleaned_data.get("name") or "").strip()
        if name:
            user.first_name = name
            user.save(update_fields=["first_name"])
        return user


class MemzPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = _("אימייל")
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email", "inputmode": "email", "autofocus": True, "class": "memz-input"}
        )


class MemzSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = _("סיסמה חדשה")
        self.fields["new_password2"].label = _("עוד פעם, ליתר ביטחון")
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs.update({"autocomplete": "new-password", "class": "memz-input"})
