from django import forms


class PatientImageInput(forms.ClearableFileInput):
    template_name = "dossier/widgets/patient_image.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget["remove_requested"] = widget["attrs"].pop("checked", False)
        return context
