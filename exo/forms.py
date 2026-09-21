"""exo's own forms, in exo's own chrome.

The accounts are the site's shared `User` — a new app never gets its own
account database (building_an_app.md, "Auth: reuse the User model"). What is
allowed to be lighter is the *flow* around it: the main site's public signup
sends a verification email because it is open to the whole internet; this is an
invite-only builder whose real gate is Avi's approval, so the account is
created immediately and the approval does the gatekeeping.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class JoinForm(forms.Form):
    """Create the shared account and ask for builder access in one step."""

    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    def clean_username(self):
        username = (self.cleaned_data["username"] or "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "שם המשתמש הזה כבר תפוס. / That username is taken."
            )
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email") or "",
            password=self.cleaned_data["password"],
        )
