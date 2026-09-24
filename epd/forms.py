import json

from django import forms

from .models import StudentUitwerkingData


class StudentDataForm(forms.ModelForm):
    class Meta:
        model = StudentUitwerkingData
        fields = ["waarde"]
        widgets = {
            "waarde": forms.Textarea(attrs={"rows": 8, "class": "form-control font-monospace"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["waarde"].initial = json.dumps(self.instance.waarde, indent=2, ensure_ascii=False)

    def clean_waarde(self):
        raw_value = self.cleaned_data["waarde"]
        if isinstance(raw_value, (dict, list, int, float, bool)) or raw_value is None:
            return raw_value
        try:
            return json.loads(raw_value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise forms.ValidationError("Gebruik geldige JSON, bijvoorbeeld {\"waarde\": 120}.") from exc
