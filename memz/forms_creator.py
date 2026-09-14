"""The solo creator's own form (spec §7): pick a bank image, type a
caption, same 140-char / 3-line rule as the game (spec §5.2)."""

from django import forms
from django.utils.translation import gettext_lazy as _

from . import conf
from .bank import images_for
from .models import MemeImage


class CreatorForm(forms.Form):
    image = forms.ModelChoiceField(
        queryset=MemeImage.objects.none(), empty_label=None,
        error_messages={"required": _("צריך לבחור תמונה."), "invalid_choice": _("התמונה הזאת לא זמינה.")},
    )
    caption_text = forms.CharField(
        label=_("הכיתוב"), required=True, strip=True,
        max_length=conf.get("CAPTION_MAX_CHARS"),
        widget=forms.Textarea(attrs={"class": "memz-input memz-textarea", "rows": 3, "maxlength": conf.get("CAPTION_MAX_CHARS")}),
        error_messages={"required": _("אי אפשר בלי כיתוב.")},
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].queryset = images_for(user)
