"""Books' own front door onto the shared User table, and onboarding.

Sign-up is email plus password and works immediately, the same convention
memz uses (the username is derived from the email), written here again
rather than imported, because an app never reaches into another app
(Rule 2).
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from .models import Profile

User = get_user_model()


def username_from_email(email):
    base = (slugify(email.split("@")[0]) or "reader")[:140]
    username, i = base, 1
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base}{i}"
    return username


def _field(widget, **attrs):
    widget.attrs.update({"class": "bk-input", **attrs})
    return widget


class BooksLoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "האימייל או הסיסמה לא נכונים. נסו שוב.",
        "inactive": "החשבון הזה לא פעיל.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "אימייל"
        _field(self.fields["username"].widget, autocomplete="username", inputmode="email")
        self.fields["password"].label = "סיסמה"
        _field(self.fields["password"].widget, autocomplete="current-password")

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("id").first()
            if match is not None:
                self.cleaned_data["username"] = match.get_username()
        return super().clean()


class BooksSignupForm(forms.Form):
    email = forms.EmailField(label="אימייל", widget=_field(forms.EmailInput(), autocomplete="email", inputmode="email"))
    password1 = forms.CharField(label="סיסמה", strip=False, widget=_field(forms.PasswordInput(), autocomplete="new-password"))
    password2 = forms.CharField(label="עוד פעם, ליתר ביטחון", strip=False,
                                widget=_field(forms.PasswordInput(), autocomplete="new-password"))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("יש כבר חשבון עם האימייל הזה. אפשר פשוט להיכנס.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "הסיסמאות לא זהות.")
        elif p1:
            try:
                validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        return User.objects.create_user(username=username_from_email(email), email=email,
                                        password=self.cleaned_data["password1"])


class BooksPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "אימייל"
        _field(self.fields["email"].widget, autocomplete="email", inputmode="email")


class BooksSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "סיסמה חדשה"
        self.fields["new_password2"].label = "עוד פעם, ליתר ביטחון"
        for name in ("new_password1", "new_password2"):
            _field(self.fields[name].widget, autocomplete="new-password")


class OnboardingForm(forms.ModelForm):
    """Spec BK1 §1.5: name, language, 18 or over, the terms, an area."""

    is_adult_confirmed = forms.BooleanField(label="אני בן או בת 18 ומעלה", required=True)
    accept_terms = forms.BooleanField(label="קראתי ואני מסכימ/ה לתנאי השימוש ולמדיניות הפרטיות", required=True)

    class Meta:
        model = Profile
        fields = ["display_name", "language", "area_name"]
        labels = {"display_name": "איך לקרוא לך?", "language": "שפה", "area_name": "שכונה או עיר"}
        help_texts = {"area_name": "רק שכונה או עיר, לעולם לא כתובת. כך נמצא ספרים קרובים אליך."}
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "bk-input", "autocomplete": "given-name"}),
            "language": forms.Select(attrs={"class": "bk-input"}),
            "area_name": forms.TextInput(attrs={"class": "bk-input", "placeholder": "למשל: כרמל, חיפה"}),
        }
