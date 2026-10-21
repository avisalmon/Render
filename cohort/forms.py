from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from .models import Comment, Exhibit, Material, Track

User = get_user_model()


def _http(url):
    if url and not url.lower().startswith(("http://", "https://")):
        raise forms.ValidationError("צריך קישור שמתחיל ב-http:// או https://")
    return url


class LoginForm(AuthenticationForm):
    """Sign in with the shared babook account, by email or user name."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "אימייל"
        self.fields["password"].label = "סיסמה"
        self.fields["username"].widget.attrs.update(autocomplete="username", inputmode="email", dir="ltr")
        self.fields["password"].widget.attrs.update(autocomplete="current-password", dir="ltr")
        self.error_messages = {
            "invalid_login": "האימייל או הסיסמה לא נכונים.",
            "inactive": "החשבון הזה לא פעיל.",
        }

    def clean(self):
        typed = (self.cleaned_data.get("username") or "").strip()
        if "@" in typed:
            match = User.objects.filter(email__iexact=typed).order_by("id").first()
            if match is not None:
                self.cleaned_data["username"] = match.get_username()
        return super().clean()


class SignupForm(forms.Form):
    name = forms.CharField(label="שם מלא", max_length=80)
    email = forms.EmailField(label="אימייל")
    password1 = forms.CharField(label="סיסמה", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "dir": "ltr"}))
    password2 = forms.CharField(label="סיסמה שוב", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "dir": "ltr"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(autocomplete="email", inputmode="email", dir="ltr")
        self.fields["name"].widget.attrs.update(autocomplete="name")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("כבר יש חשבון עם האימייל הזה. אפשר להתחבר איתו.")
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
        d = self.cleaned_data
        first, _, last = d["name"].strip().partition(" ")
        user = User.objects.create_user(username=d["email"], email=d["email"], password=d["password1"],
                                        first_name=first[:150], last_name=last[:150])
        return user


class ExhibitForm(forms.ModelForm):
    class Meta:
        model = Exhibit
        fields = ["title", "url", "blurb"]
        labels = {"title": "שם האתר", "url": "קישור לאתר", "blurb": "שורה קצרה על האתר (לא חובה)"}
        widgets = {"url": forms.URLInput(attrs={"dir": "ltr", "inputmode": "url", "placeholder": "https://"})}

    def clean_url(self):
        return _http(self.cleaned_data["url"])


class ShotUploadForm(forms.Form):
    picture = forms.ImageField(label="תמונה של האתר")

    def clean_picture(self):
        pic = self.cleaned_data["picture"]
        if pic.size > 5 * 1024 * 1024:
            raise forms.ValidationError("התמונה גדולה מ-5MB.")
        return pic


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        labels = {"body": "תגובה"}
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "maxlength": 2000})}


class TrackLinksForm(forms.ModelForm):
    class Meta:
        model = Track
        fields = ["vision_url", "graduate_url", "project_url"]
        labels = {"vision_url": "קישור למסמך החזון", "graduate_url": "קישור לדמות הבוגר", "project_url": "קישור להגדרת הפרויקט"}
        widgets = {f: forms.URLInput(attrs={"dir": "ltr", "inputmode": "url", "placeholder": "https://"})
                   for f in ("vision_url", "graduate_url", "project_url")}

    def clean(self):
        cleaned = super().clean()
        for f in ("vision_url", "graduate_url", "project_url"):
            _http(cleaned.get(f) or "")
        return cleaned


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["kind", "title", "line", "url", "file"]
        labels = {"kind": "סוג", "title": "כותרת", "line": "שורת הסבר", "url": "קישור (סרטון יוטיוב, הדרכה ב-babook, או כל קישור אחר)", "file": "קובץ"}
        widgets = {"url": forms.URLInput(attrs={"dir": "ltr", "inputmode": "url", "placeholder": "https://"})}

    def clean(self):
        cleaned = super().clean()
        kind, url, file = cleaned.get("kind"), cleaned.get("url"), cleaned.get("file")
        if url:
            _http(url)
        if kind == Material.FILE and not file and not (self.instance and self.instance.file):
            self.add_error("file", "צריך לצרף קובץ.")
        if kind in (Material.VIDEO, Material.COURSE, Material.LINK) and not url:
            self.add_error("url", "צריך קישור.")
        if kind == Material.VIDEO and url:
            from .models import youtube_id

            if not youtube_id(url):
                self.add_error("url", "זה לא נראה כמו קישור לסרטון ביוטיוב.")
        if file and file.size > 25 * 1024 * 1024:
            self.add_error("file", "הקובץ גדול מ-25MB.")
        return cleaned
