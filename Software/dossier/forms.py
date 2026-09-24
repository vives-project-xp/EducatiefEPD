from django import forms
from django.utils.text import slugify

from .models import (
    Assignment, Case, FieldDefinition, LibraryField, LibraryTemplate,
    Module, ModuleField, Patient,
)


def split_lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["name", "reference", "birth_date", "gender", "image", "context"]
        labels = {
            "name": "Naam patiënt", "reference": "Fictieve referentie",
            "birth_date": "Geboortedatum", "gender": "Geslacht",
            "image": "URL patiëntfoto", "context": "Korte context",
        }
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"})}


class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ["title", "course", "introduction", "learning_objectives"]
        labels = {
            "title": "Titel van de casus", "course": "Opleidingsonderdeel",
            "introduction": "Inleiding", "learning_objectives": "Leerdoelen",
        }
        widgets = {
            "introduction": forms.Textarea(attrs={"rows": 5}),
            "learning_objectives": forms.Textarea(attrs={"rows": 4}),
        }


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["phase", "title", "content", "position"]
        labels = {
            "phase": "Fase", "title": "Opdracht",
            "content": "Instructies", "position": "Volgorde",
        }
        widgets = {"content": forms.Textarea(attrs={"rows": 6})}


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ["title", "kind", "instructions", "position"]
        labels = {
            "title": "Naam dossieronderdeel", "kind": "Type",
            "instructions": "Instructies", "position": "Volgorde",
        }
        widgets = {"instructions": forms.Textarea(attrs={"rows": 4})}


class FieldConfigurationForm(forms.ModelForm):
    options_text = forms.CharField(
        label="Keuzeopties", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Alleen voor een keuzelijst: één optie per regel."
    )
    rows_text = forms.CharField(
        label="Matrixrijen", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Alleen voor een matrix: één rij per regel."
    )
    columns_text = forms.CharField(
        label="Matrixkolommen", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Alleen voor een matrix: één kolom per regel."
    )

    def __init__(self, *args, parent=None, **kwargs):
        self.parent = parent
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["options_text"].initial = "\n".join(self.instance.options)
            self.fields["rows_text"].initial = "\n".join(self.instance.rows)
            self.fields["columns_text"].initial = "\n".join(self.instance.columns)

    def clean(self):
        cleaned = super().clean()
        field_type = cleaned.get("field_type")
        if field_type == FieldDefinition.FieldType.SELECT and not split_lines(cleaned.get("options_text", "")):
            self.add_error("options_text", "Voeg minstens één optie toe.")
        if field_type == FieldDefinition.FieldType.MATRIX:
            if not split_lines(cleaned.get("rows_text", "")):
                self.add_error("rows_text", "Voeg minstens één rij toe.")
            if not split_lines(cleaned.get("columns_text", "")):
                self.add_error("columns_text", "Voeg minstens één kolom toe.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.options = split_lines(self.cleaned_data["options_text"])
        instance.rows = split_lines(self.cleaned_data["rows_text"])
        instance.columns = split_lines(self.cleaned_data["columns_text"])
        if not instance.key:
            base = slugify(instance.label)[:65] or "veld"
            key = base
            manager = instance.__class__.objects
            parent_field = "module" if isinstance(instance, ModuleField) else "template"
            index = 2
            while manager.filter(**{parent_field: self.parent, "key": key}).exclude(pk=instance.pk).exists():
                key = f"{base}-{index}"
                index += 1
            instance.key = key
        if commit:
            instance.save()
        return instance


class ModuleFieldForm(FieldConfigurationForm):
    class Meta:
        model = ModuleField
        fields = ["label", "field_type", "help_text", "required", "position"]
        labels = {
            "label": "Veldnaam", "field_type": "Veldtype", "help_text": "Hulptekst",
            "required": "Verplicht", "position": "Volgorde",
        }


class LibraryTemplateForm(forms.ModelForm):
    class Meta:
        model = LibraryTemplate
        fields = ["title", "description", "category", "education", "theme", "instructions"]
        labels = {
            "title": "Naam", "description": "Beschrijving", "category": "Categorie",
            "education": "Opleiding", "theme": "Thema", "instructions": "Instructies",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
        }


class LibraryFieldForm(FieldConfigurationForm):
    class Meta:
        model = LibraryField
        fields = ["label", "field_type", "help_text", "required", "position"]
        labels = ModuleFieldForm.Meta.labels


class ReviewForm(forms.Form):
    status = forms.ChoiceField(
        label="Beoordeling",
        choices=[("approved", "Goedgekeurd"), ("resubmit", "Opnieuw inleveren")],
    )
    feedback = forms.CharField(
        label="Feedback", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
