"""Books' own front door onto the shared User table, onboarding, settings.

Sign-up is email plus password and works immediately, the same convention
memz uses (the username is derived from the email), written here again
rather than imported, because an app never reaches into another app
(Rule 2). Every label comes from the catalogue in the form's language.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from .middleware import PALETTES, SHELF_VIEWS, THEMES
from .models import Profile
from .strings import DEFAULT_LANGUAGE
from .strings import text as t

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


class _Localised:
    """Mixin: `lang` kwarg, `self.t(key)` for labels and errors."""

    def __init__(self, *args, lang=DEFAULT_LANGUAGE, **kwargs):
        self.lang = lang
        super().__init__(*args, **kwargs)

    def t(self, key, **kw):
        return t(key, self.lang, **kw)


class BooksLoginForm(_Localised, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_messages = {"invalid_login": self.t("login.err_invalid"), "inactive": self.t("login.err_inactive")}
        self.fields["username"].label = self.t("field.email")
        _field(self.fields["username"].widget, autocomplete="username", inputmode="email")
        self.fields["password"].label = self.t("field.password")
        _field(self.fields["password"].widget, autocomplete="current-password")

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("id").first()
            if match is not None:
                self.cleaned_data["username"] = match.get_username()
        return super().clean()


class BooksSignupForm(_Localised, forms.Form):
    email = forms.EmailField(widget=_field(forms.EmailInput(), autocomplete="email", inputmode="email"))
    password1 = forms.CharField(strip=False, widget=_field(forms.PasswordInput(), autocomplete="new-password"))
    password2 = forms.CharField(strip=False, widget=_field(forms.PasswordInput(), autocomplete="new-password"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = self.t("field.email")
        self.fields["password1"].label = self.t("field.password")
        self.fields["password2"].label = self.t("field.password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(self.t("signup.err_taken"))
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", self.t("signup.err_mismatch"))
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


class BooksPasswordResetForm(_Localised, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = self.t("field.email")
        _field(self.fields["email"].widget, autocomplete="email", inputmode="email")


class BooksSetPasswordForm(_Localised, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = self.t("field.new_password")
        self.fields["new_password2"].label = self.t("field.password2")
        for name in ("new_password1", "new_password2"):
            _field(self.fields[name].widget, autocomplete="new-password")


class OnboardingForm(_Localised, forms.ModelForm):
    """Spec BK1 §1.5: name, language, 18 or over, the terms, an area."""

    is_adult_confirmed = forms.BooleanField(required=True)
    accept_terms = forms.BooleanField(required=True)

    class Meta:
        model = Profile
        fields = ["display_name", "language", "area_name"]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "bk-input", "autocomplete": "given-name"}),
            "language": forms.Select(attrs={"class": "bk-select"}),
            "area_name": forms.TextInput(attrs={"class": "bk-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].label = self.t("onb.name")
        self.fields["language"].label = self.t("onb.language")
        self.fields["area_name"].label = self.t("onb.area")
        self.fields["area_name"].widget.attrs["placeholder"] = self.t("onb.area_placeholder")
        self.fields["is_adult_confirmed"].label = self.t("onb.adult")


class SettingsForm(_Localised, forms.ModelForm):
    """Spec BK1 §1.1b: appearance is a setting; plus the person's own facts."""

    class Meta:
        model = Profile
        fields = ["display_name", "language", "area_name", "radius_km", "phone", "theme", "palette", "shelf_view",
                  "spine_photos", "spine_text_down", "profile_public", "show_points_public", "public_library", "public_reading",
                  "public_reviews"]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "bk-input"}),
            "language": forms.RadioSelect,
            "area_name": forms.TextInput(attrs={"class": "bk-input"}),
            "radius_km": forms.NumberInput(attrs={"class": "bk-input", "min": 1, "max": 100}),
            "phone": forms.TextInput(attrs={"class": "bk-input", "inputmode": "tel", "autocomplete": "tel"}),
            "theme": forms.RadioSelect,
            "palette": forms.RadioSelect,
            "shelf_view": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["theme"].choices = [(k, self.t(f"settings.theme_{k}")) for k in THEMES]
        self.fields["palette"].choices = [(k, self.t(f"settings.palette_{k}")) for k in PALETTES]
        self.fields["shelf_view"].choices = [(k, self.t(f"settings.view_{k}")) for k in SHELF_VIEWS]
        for name in ("display_name", "language", "area_name", "radius_km", "phone", "theme", "palette", "shelf_view",
                     "spine_photos", "spine_text_down", "profile_public", "show_points_public", "public_library", "public_reading",
                     "public_reviews"):
            self.fields[name].label = self.t(f"settings.{name}")
        self.fields["radius_km"].min_value = 1
        self.fields["radius_km"].max_value = 100
