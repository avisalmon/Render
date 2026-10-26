"""Sign in and sign up, in English, against the one shared babook User."""

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User


class LoginForm(AuthenticationForm):
    """Sign in with the babook account, by email or user name."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["password"].label = "Password"
        self.fields["username"].widget.attrs.update(autocomplete="username", inputmode="email")
        self.fields["password"].widget.attrs.update(autocomplete="current-password")
        self.error_messages = {
            "invalid_login": "That email and password do not match an account.",
            "inactive": "This account is not active.",
        }

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("id").first()
            if match is not None:
                self.cleaned_data["username"] = match.get_username()
        return super().clean()


class SignupForm(forms.Form):
    name = forms.CharField(label="Your name", max_length=80)
    email = forms.EmailField(label="Email")
    password1 = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Password again", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(autocomplete="email", inputmode="email")
        self.fields["name"].widget.attrs.update(autocomplete="name")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("There is already an account with this email. Sign in with it.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The passwords do not match.")
        elif p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        d = self.cleaned_data
        first, _, last = d["name"].strip().partition(" ")
        return User.objects.create_user(username=d["email"], email=d["email"], password=d["password1"],
                                        first_name=first[:150], last_name=last[:150])


class CommentForm(forms.Form):
    body = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Ask a question or share how it went"}))
    reply_to = forms.IntegerField(required=False, widget=forms.HiddenInput)
