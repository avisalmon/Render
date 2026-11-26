"""Sign-in and sign-up in the app's own look, against the shared accounts
(methodology: "a lighter front door is fine")."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class LoginForm(AuthenticationForm):
    """By email or user name; people know their email."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "אימייל"
        self.fields["password"].label = "סיסמה"
        self.fields["username"].widget.attrs.update(autocomplete="username", inputmode="email", dir="ltr")
        self.fields["password"].widget.attrs.update(autocomplete="current-password", dir="ltr")
        self.error_messages = {
            "invalid_login": "האימייל או הסיסמה אינם נכונים.",
            "inactive": "החשבון הזה אינו פעיל.",
        }

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("id").first()
            if match is not None:
                self.cleaned_data["username"] = match.get_username()
        return super().clean()


class SignupForm(forms.Form):
    name = forms.CharField(max_length=80, label="שם")
    email = forms.EmailField(label="אימייל")
    password1 = forms.CharField(strip=False, label="סיסמה",
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "dir": "ltr"}))
    password2 = forms.CharField(strip=False, label="סיסמה שוב",
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "dir": "ltr"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(autocomplete="email", inputmode="email", dir="ltr")
        self.fields["name"].widget.attrs.update(autocomplete="name")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("יש כבר חשבון עם האימייל הזה. היכנסו איתו.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "הסיסמאות אינן זהות.")
        elif p1:
            try:
                validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        d = self.cleaned_data
        first, _, last = d["name"].strip().partition(" ")
        return User.objects.create_user(username=d["email"], email=d["email"], password=d["password1"],
                                        first_name=first[:150], last_name=last[:150])
