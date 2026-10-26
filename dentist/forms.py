"""The forms with more than two fields. Everything renders with the app's
own classes; a field under 16px makes an iPhone zoom and slide (mistake 52),
so the stylesheet sets the size and the widgets only carry the class."""

from django import forms

from .models import Clinic, HistoryItem, Patient


class _Styled(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "dn-input")


class PatientForm(_Styled):
    """Everything on the record a member may fill in later (Rule 4.1).
    Nothing the spec forbids has a field here (Rule 4.7)."""

    class Meta:
        model = Patient
        fields = ["first_name", "last_name", "preferred_language", "needs_interpreter", "phone", "whatsapp",
                  "birth_year", "sex", "id_kind", "id_number", "front_desk_notes"]
        labels = {
            "first_name": "First name", "last_name": "Last name (optional)",
            "preferred_language": "Language they read", "needs_interpreter": "Needs an interpreter",
            "phone": "Phone", "whatsapp": "WhatsApp", "birth_year": "Year of birth", "sex": "Sex",
            "id_kind": "Identification", "id_number": "Identification number",
            "front_desk_notes": "Notes for the front desk",
        }
        widgets = {"front_desk_notes": forms.Textarea(attrs={"rows": 3}),
                   "birth_year": forms.NumberInput(attrs={"min": 1900, "max": 2100, "inputmode": "numeric"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["needs_interpreter"].widget.attrs["class"] = ""


class HistoryForm(_Styled):
    class Meta:
        model = HistoryItem
        fields = ["kind", "what", "detail"]
        labels = {"kind": "Kind", "what": "What", "detail": "Detail (optional)"}


class ClinicForm(_Styled):
    class Meta:
        model = Clinic
        fields = ["name", "address", "opening_notes"]
        labels = {"name": "The clinic's name", "address": "Address, as it appears in reminders",
                  "opening_notes": "Opening hours and notes"}
        widgets = {"opening_notes": forms.Textarea(attrs={"rows": 4})}
