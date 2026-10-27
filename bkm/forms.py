"""Sign in and sign up, in English, against the one shared babook User."""

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

from .models import Bkm, Project, youtube_id


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


class ProjectForm(forms.ModelForm):
    """Pin a project (REQ-B.31). One of three kinds, and a little about it so
    others can find it (REQ-B.35)."""

    image = forms.ImageField(label="Photo", required=False,
                             help_text="For a photo project. For a site, an optional picture instead of the automatic screenshot.")

    class Meta:
        model = Project
        fields = ["kind", "title", "url", "image", "description", "bkm", "topic", "purpose", "level", "tags"]
        labels = {
            "kind": "What is it?", "title": "Title", "url": "Link", "description": "In a sentence or two",
            "bkm": "Made with a BKM?", "topic": "Topic", "purpose": "Why you made it", "level": "Your level",
            "tags": "Tags",
        }
        widgets = {
            "kind": forms.RadioSelect,
            "description": forms.Textarea(attrs={"rows": 3, "maxlength": 400}),
            "url": forms.URLInput(attrs={"placeholder": "https://"}),
            "tags": forms.TextInput(attrs={"placeholder": "e.g. esp32, oled, game"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["bkm"].queryset = Bkm.objects.filter(is_published=True)
        self.fields["bkm"].empty_label = "No, or not one of these"
        self.fields["purpose"].choices = [("", "Choose (optional)")] + list(self.fields["purpose"].choices)[1:]
        self.fields["level"].choices = [("", "Choose (optional)")] + list(self.fields["level"].choices)[1:]
        self.fields["kind"].choices = [c for c in self.fields["kind"].choices if c[0]]

    def clean(self):
        from . import images

        cleaned = super().clean()
        kind, url = cleaned.get("kind"), (cleaned.get("url") or "").strip()
        upload = self.files.get("image")
        if url and not url.lower().startswith(("http://", "https://")):
            self.add_error("url", "A link starts with http:// or https://")
        elif kind == Project.VIDEO and not youtube_id(url):
            self.add_error("url", "Paste the YouTube link of the video.")
        elif kind == Project.SITE and not url:
            self.add_error("url", "Paste the link to the site.")
        if kind == Project.IMAGE and not upload and not (self.instance.pk and self.instance.image):
            self.add_error("image", "Choose the photo.")
        if upload and not self.errors:
            try:
                cleaned["image"] = images.prepare(upload, self.user)
            except forms.ValidationError as exc:
                self.add_error("image", exc)
        tags = [t.strip().lower()[:24] for t in (cleaned.get("tags") or "").split(",") if t.strip()]
        cleaned["tags"] = ", ".join(dict.fromkeys(tags))[:120]
        return cleaned


class CommentForm(forms.Form):
    body = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Ask a question or share how it went"}))
    reply_to = forms.IntegerField(required=False, widget=forms.HiddenInput)
