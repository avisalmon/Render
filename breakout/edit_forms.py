"""The editor's forms (spec 5). Every person-typed text goes through
`text.tidy`; every file through a check that opens it (an image is decoded,
turned upright and re-saved; a PDF is read for its header and page count)
before it is stored under the private folder.
"""

import io
import re

from django import forms

from . import text
from .models import (
    Experience,
    FinalLock,
    Hint,
    Material,
    MaterialRequest,
    Printable,
    Station,
    StationMaterial,
    Subject,
    hebrew_grade,
)

GRADE_CHOICES = [(n, f"כיתה {hebrew_grade(n)}") for n in range(1, 13)]
IMAGE_TYPES = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG"}
MAX_UPLOAD = 8 * 1024 * 1024
MAX_PIXELS = 25_000_000


class TidyMixin:
    """Tidies every CharField on the way in, title-like ones to one line."""

    one_line = ()

    def clean(self):
        cleaned = super().clean()
        for name, field in self.fields.items():
            if isinstance(field, forms.CharField) and not isinstance(field.widget, forms.FileInput):
                if name in cleaned and isinstance(cleaned[name], str):
                    cleaned[name] = text.tidy(cleaned[name], one_line=name in self.one_line)
        return cleaned


def _style(form, **extra):
    for name, field in form.fields.items():
        attrs = field.widget.attrs
        if isinstance(field.widget, forms.Textarea):
            attrs.setdefault("rows", 5)
        if isinstance(field, forms.CharField) and not isinstance(field.widget, forms.FileInput):
            attrs.setdefault("dir", "auto")
        if isinstance(field, forms.IntegerField):
            attrs.setdefault("inputmode", "numeric")
        attrs.update(extra.get(name, {}))


def checked_image(uploaded, field_name="file"):
    """Opens the image for real, turns it upright (mistake 68), caps its
    size, and returns (content_bytes, extension, width, height)."""
    from PIL import Image, ImageOps

    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
    if ext not in IMAGE_TYPES:
        raise forms.ValidationError("תמונה היא PNG או JPG בלבד.")
    if uploaded.size > MAX_UPLOAD:
        raise forms.ValidationError("הקובץ גדול מדי (עד 8MB).")
    try:
        img = Image.open(uploaded)
        img.verify()
        uploaded.seek(0)
        img = Image.open(uploaded)
        if img.format != IMAGE_TYPES[ext]:
            raise forms.ValidationError("הסיומת לא מתאימה לתוכן הקובץ.")
        if img.width * img.height > MAX_PIXELS:
            raise forms.ValidationError("התמונה גדולה מדי (עד 25 מגה-פיקסל).")
        img = ImageOps.exif_transpose(img)
        if img.format is None or ext in ("jpg", "jpeg"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, IMAGE_TYPES[ext], quality=90)
    except forms.ValidationError:
        raise
    except Exception:
        raise forms.ValidationError("הקובץ אינו תמונה תקינה.") from None
    return out.getvalue(), ext, img.width, img.height


def checked_pdf(uploaded):
    """A PDF by its header, with a page count read from its objects."""
    if uploaded.size > MAX_UPLOAD:
        raise forms.ValidationError("הקובץ גדול מדי (עד 8MB).")
    data = uploaded.read()
    uploaded.seek(0)
    if not data.startswith(b"%PDF-"):
        raise forms.ValidationError("הקובץ אינו PDF תקין.")
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data)) or 1
    return data, "pdf", pages


# ----------------------------------------------------------------- forms


class AboutForm(TidyMixin, forms.ModelForm):
    one_line = ("title", "tagline")
    audience_from = forms.TypedChoiceField(choices=GRADE_CHOICES, coerce=int, label="מכיתה")
    audience_to = forms.TypedChoiceField(choices=GRADE_CHOICES, coerce=int, label="עד כיתה")
    subjects = forms.ModelMultipleChoiceField(queryset=Subject.objects.all(), required=False, label="תחומים",
                                              widget=forms.CheckboxSelectMultiple)
    cover = forms.ImageField(required=False, label="תמונת שער (לא חובה)")
    remove_cover = forms.BooleanField(required=False, label="להסיר את תמונת השער")

    class Meta:
        model = Experience
        fields = ["title", "tagline", "audience_from", "audience_to", "group_size_min", "group_size_max",
                  "duration_minutes", "prep_minutes", "difficulty", "subjects"]
        labels = {
            "title": "שם האתגר", "tagline": "משפט אחד שמסביר אותו", "group_size_min": "קבוצה מינימלית",
            "group_size_max": "קבוצה מקסימלית", "duration_minutes": "דקות משחק", "prep_minutes": "דקות הכנה",
            "difficulty": "רמה",
        }
        widgets = {"difficulty": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, title={"autofocus": True, "maxlength": 120}, tagline={"maxlength": 200})
        self.fields["difficulty"].choices = Experience.DIFFICULTIES
        for name in ("group_size_min", "group_size_max", "duration_minutes", "prep_minutes"):
            self.fields[name].widget.attrs.update(min=1, max=600)
        self._cover = None

    def clean_cover(self):
        uploaded = self.cleaned_data.get("cover")
        if not uploaded or not hasattr(uploaded, "read"):
            return uploaded
        content, ext, _w, _h = checked_image(uploaded)
        self._cover = (content, ext)
        return uploaded

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("audience_from") and cleaned.get("audience_to") and cleaned["audience_from"] > cleaned["audience_to"]:
            self.add_error("audience_to", "הכיתה העליונה קטנה מהתחתונה.")
        if cleaned.get("group_size_min") and cleaned.get("group_size_max") and cleaned["group_size_min"] > cleaned["group_size_max"]:
            self.add_error("group_size_max", "הקבוצה המקסימלית קטנה מהמינימלית.")
        return cleaned

    def save(self, commit=True):
        from django.core.files.base import ContentFile

        exp = super().save(commit=False)
        if self.cleaned_data.get("remove_cover") and exp.cover:
            exp.cover.delete(save=False)
        if self._cover:
            content, ext = self._cover
            if exp.cover:
                exp.cover.delete(save=False)
            exp.cover.save(f"cover.{ext}", ContentFile(content), save=False)
        if commit:
            exp.save()
            self.save_m2m()
        return exp


class StoryForm(TidyMixin, forms.ModelForm):
    class Meta:
        model = Experience
        fields = ["story", "teacher_notes"]
        labels = {"story": "הסיפור (מה שהמורה מקריא לקבוצה)", "teacher_notes": "הערות הכנה למורה"}
        widgets = {"story": forms.Textarea(attrs={"rows": 10}), "teacher_notes": forms.Textarea(attrs={"rows": 8})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class StationQuickForm(TidyMixin, forms.ModelForm):
    """Adding a station asks for its name only; the rest is on its own page."""

    one_line = ("name",)

    class Meta:
        model = Station
        fields = ["name"]
        labels = {"name": "שם התחנה"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, name={"maxlength": 80, "placeholder": "למשל: הזיכרון"})


class StationForm(TidyMixin, forms.ModelForm):
    one_line = ("name", "contribution")

    class Meta:
        model = Station
        fields = ["name", "mechanic", "estimated_minutes", "story_text", "puzzle_text", "solution", "solution_explained",
                  "contribution", "setup_notes"]
        labels = {
            "name": "שם התחנה", "mechanic": "סוג החידה", "estimated_minutes": "דקות משוערות",
            "story_text": "מה הקבוצה קוראת (מודפס לשחקנים)", "puzzle_text": "החידה (מודפסת לשחקנים)",
            "solution": "הפתרון (למורה בלבד)", "solution_explained": "הסבר הפתרון (למורה)",
            "contribution": "מה התחנה תורמת למנעול (למשל: הספרה 3)", "setup_notes": "איך מכינים את התחנה",
        }
        widgets = {
            "story_text": forms.Textarea(attrs={"rows": 4}), "puzzle_text": forms.Textarea(attrs={"rows": 8}),
            "solution": forms.Textarea(attrs={"rows": 2}), "solution_explained": forms.Textarea(attrs={"rows": 4}),
            "setup_notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, name={"maxlength": 80}, contribution={"maxlength": 200})
        self.fields["estimated_minutes"].widget.attrs.update(min=1, max=180)


class HintForm(TidyMixin, forms.ModelForm):
    one_line = ("text",)

    class Meta:
        model = Hint
        fields = ["text"]
        labels = {"text": "רמז"}
        widgets = {"text": forms.TextInput}  # a hint is one line

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, text={"maxlength": 300, "placeholder": "מהעדין לברור: רמז ראשון רק מכוון"})


class StationMaterialForm(TidyMixin, forms.ModelForm):
    one_line = ("note",)
    material = forms.ModelChoiceField(queryset=Material.objects.filter(is_active=True), label="חומר מהקטלוג", empty_label="בחרו חומר")

    class Meta:
        model = StationMaterial
        fields = ["material", "quantity", "note"]
        labels = {"quantity": "כמות לקבוצה", "note": "הערה (לא חובה)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, note={"maxlength": 200, "placeholder": "למשל: רצף ביטים על כל כרטיסייה"})
        self.fields["quantity"].widget.attrs.update(min="0.25", step="0.25", inputmode="decimal")

    def clean_quantity(self):
        q = self.cleaned_data["quantity"]
        if q is None or q <= 0:
            raise forms.ValidationError("כמות חיובית.")
        return q


class MaterialRequestForm(TidyMixin, forms.ModelForm):
    one_line = ("name",)

    class Meta:
        model = MaterialRequest
        fields = ["name", "why"]
        labels = {"name": "שם החומר החסר", "why": "למה הוא עומד בגבול הז'אנר (זול, משרדי, בלי מסכים)"}
        widgets = {"why": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, name={"maxlength": 80})


class PrintableForm(TidyMixin, forms.ModelForm):
    """Upload through a checking form: the file is opened before it is kept."""

    one_line = ("title",)
    file = forms.FileField(label="קובץ (PNG, JPG או PDF)")

    class Meta:
        model = Printable
        fields = ["title", "kind", "file"]
        labels = {"title": "מה זה (למשל: שמונה החבילות לגזירה)", "kind": "סוג הדף"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, title={"maxlength": 120})
        self.fields["file"].widget.attrs.update(accept=".png,.jpg,.jpeg,.pdf")
        self._checked = None

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
        if ext == "pdf":
            data, ext, pages = checked_pdf(uploaded)
            self._checked = (data, ext, pages, None, None)
        elif ext in IMAGE_TYPES:
            data, ext, w, h = checked_image(uploaded)
            self._checked = (data, ext, 1, w, h)
        else:
            raise forms.ValidationError("מצורפים הם PNG, JPG או PDF בלבד.")
        return uploaded

    def save(self, commit=True):
        from django.core.files.base import ContentFile

        p = super().save(commit=False)
        data, ext, pages, w, h = self._checked
        p.page_count, p.width_px, p.height_px = pages, w, h
        p.file.save(f"printable.{ext}", ContentFile(data), save=False)
        if commit:
            p.save()
        return p


class FinalLockForm(TidyMixin, forms.ModelForm):
    one_line = ("final_code",)

    class Meta:
        model = FinalLock
        fields = ["description", "code_rule", "final_code", "final_message", "setup_notes"]
        labels = {
            "description": "המנעול: מה הקבוצה רואה ופותחת", "code_rule": "איך הקוד מתחבר מהתחנות",
            "final_code": "הקוד", "final_message": "ההודעה שבפנים", "setup_notes": "איך מכינים את המנעול",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}), "code_rule": forms.Textarea(attrs={"rows": 2}),
            "final_message": forms.Textarea(attrs={"rows": 5}), "setup_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, final_code={"maxlength": 40, "dir": "ltr", "autocomplete": "off"})
