from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from .models import Exhibit, Person, Topic, Training
from .strings import text

User = get_user_model()


def _http(url, language):
    if url and not url.lower().startswith(("http://", "https://")):
        raise forms.ValidationError(text("form.need_http", language))
    return url


class LoginForm(AuthenticationForm):
    """Sign in with the shared babook account, by email or user name."""

    def __init__(self, *args, language="he", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = text("auth.email", language)
        self.fields["password"].label = text("auth.password", language)
        self.fields["username"].widget.attrs.update(autocomplete="username", inputmode="email", dir="ltr")
        self.fields["password"].widget.attrs.update(autocomplete="current-password", dir="ltr")
        self.error_messages = {
            "invalid_login": text("auth.invalid", language),
            "inactive": text("auth.inactive", language),
        }

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("id").first()
            if match is not None:
                self.cleaned_data["username"] = match.get_username()
        return super().clean()


class SignupForm(forms.Form):
    name = forms.CharField(max_length=80)
    email = forms.EmailField()
    password1 = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "dir": "ltr"}))
    password2 = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "dir": "ltr"}))

    def __init__(self, *args, language="he", **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        for name, key in (("name", "auth.name"), ("email", "auth.email"),
                          ("password1", "auth.password"), ("password2", "auth.password_again")):
            self.fields[name].label = text(key, language)
        self.fields["email"].widget.attrs.update(autocomplete="email", inputmode="email", dir="ltr")
        self.fields["name"].widget.attrs.update(autocomplete="name")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(text("auth.email_taken", self.language))
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", text("auth.mismatch", self.language))
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


class TopicChoices(forms.ModelMultipleChoiceField):
    def __init__(self, *args, language="he", **kwargs):
        self.language = language
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return obj.tr("name", self.language)


class ExhibitForm(forms.ModelForm):
    """A page (REQ-G.10). Skills come in through the skill chat; BKMs are
    not cards here (REQ-G.80)."""

    class Meta:
        model = Exhibit
        fields = ["kind", "title", "url", "blurb", "topics"]
        widgets = {"url": forms.URLInput(attrs={"dir": "ltr", "inputmode": "url", "placeholder": "https://"}),
                   "blurb": forms.Textarea(attrs={"rows": 3, "maxlength": 400})}

    def __init__(self, *args, language="he", admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        self.fields["topics"] = TopicChoices(queryset=Topic.objects.all(), required=False, language=language,
                                             widget=forms.CheckboxSelectMultiple)
        labels = {"kind": "form.kind", "title": "form.title", "url": "form.url", "blurb": "form.blurb", "topics": "form.topics"}
        for name, key in labels.items():
            self.fields[name].label = text(key, language)
        is_skill = self.instance.pk and self.instance.kind == Exhibit.SKILL
        if is_skill:
            del self.fields["url"]  # a skill has files, not a link
        else:
            self.fields["url"].required = True
        # Only pages are made here: skills come through the skill chat, and BKMs
        # live in Avi's bkm app, which the menu links to (Avi, 2026-11-10).
        del self.fields["kind"]

    def clean_url(self):
        return _http(self.cleaned_data.get("url", ""), self.language)


class ShotUploadForm(forms.Form):
    picture = forms.ImageField()

    def __init__(self, *args, language="he", **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        self.fields["picture"].label = text("form.picture", language)

    def clean_picture(self):
        pic = self.cleaned_data["picture"]
        if pic.size > 5 * 1024 * 1024:
            raise forms.ValidationError(text("form.picture_big", self.language))
        return pic


def _training_choices(language, include=None):
    rows = list(Training.objects.filter(is_open=True))
    if include is not None and include not in rows:
        rows.append(include)
    return rows


class TrainingForm(forms.Form):
    """REQ-G.4: Avi's open trainings, then "other" with an optional line."""

    training = forms.ChoiceField(widget=forms.RadioSelect)
    other = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, language="he", **kwargs):
        super().__init__(*args, **kwargs)
        self.language = language
        self.rows = {str(t.pk): t for t in _training_choices(language)}
        self.fields["training"].choices = [(k, t.tr("name", language)) for k, t in self.rows.items()] + [
            ("other", text("training.other", language))]
        self.fields["training"].label = text("training.question", language)
        self.fields["training"].error_messages["required"] = text("training.pick_one", language)
        self.fields["other"].label = text("training.other_line", language)
        self.chosen = None

    def clean(self):
        cleaned = super().clean()
        self.chosen = self.rows.get(cleaned.get("training") or "")
        return cleaned


class SettingsForm(forms.ModelForm):
    """REQ-G.31. The training is the person's own and Avi's, nobody else's."""

    class Meta:
        model = Person
        fields = ["display_name", "language", "training", "training_other"]

    def __init__(self, *args, language="he", **kwargs):
        super().__init__(*args, **kwargs)
        rows = _training_choices(language, include=self.instance.training)
        self.fields["training"].queryset = Training.objects.filter(pk__in=[t.pk for t in rows])
        self.fields["training"].label_from_instance = lambda t: t.tr("name", language)
        self.fields["training"].empty_label = text("training.other", language)
        self.fields["training"].required = False
        self.fields["language"].widget = forms.RadioSelect(choices=Person.LANGUAGES)
        for name, key in (("display_name", "settings.name"), ("language", "settings.language"),
                          ("training", "settings.training"), ("training_other", "training.other_line")):
            self.fields[name].label = text(key, language)
