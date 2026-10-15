from django import forms
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from .matrix import blank, convert_base_values, empty_values, fingerprint, legacy_definition, normalize_definition

from .models import (
    Assignment, Case, Education, FieldDefinition, LibraryField, LibraryTemplate,
    Module, ModuleField, Patient, TeachingGroup,
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
        fields = ["title", "education", "course", "introduction", "learning_objectives"]
        labels = {
            "title": "Titel van de casus", "education": "Opleiding",
            "course": "Opleidingsonderdeel",
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
    matrix_definition = forms.JSONField(required=False, widget=forms.HiddenInput)
    revision = forms.CharField(required=False, widget=forms.HiddenInput)
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
        self.original_schema = self.instance.as_schema() if self.instance.pk else {}
        self.expected_revision = fingerprint(self.instance)
        self.fields["revision"].initial = self.expected_revision
        self.fields["matrix_definition"].initial = self.instance.matrix_definition or (
            legacy_definition(self.instance.rows, self.instance.columns)
            if self.instance.pk and self.instance.field_type == "matrix" else {}
        )
        self.converted_base = None
        if self.instance and self.instance.pk:
            self.fields["options_text"].initial = "\n".join(self.instance.options)
            self.fields["rows_text"].initial = "\n".join(self.instance.rows)
            self.fields["columns_text"].initial = "\n".join(self.instance.columns)

    def clean(self):
        cleaned = super().clean()
        self.instance.options = split_lines(cleaned.get("options_text", ""))
        self.instance.rows = split_lines(cleaned.get("rows_text", ""))
        self.instance.columns = split_lines(cleaned.get("columns_text", ""))
        field_type = cleaned.get("field_type")
        definition = cleaned.get("matrix_definition")
        if isinstance(self.instance, ModuleField) and self.instance.pk and field_type != self.original_schema.get("type"):
            old_value = self.parent.base_data.get(self.instance.key, "")
            if self.original_schema.get("type") == "matrix" and isinstance(old_value, dict):
                old_cells = old_value.get("cells", {}) if self.original_schema.get("matrix_definition") else {"legacy": old_value}
                has_base_value = not isinstance(old_cells, dict) or any(
                    not isinstance(row, dict) or any(not blank(value) for value in row.values())
                    for row in old_cells.values()
                )
            else:
                has_base_value = not blank(old_value)
            if has_base_value:
                self.add_error("field_type", "Maak de bestaande voorinvulling eerst bewust leeg voordat u het veldtype wijzigt.")
            else:
                # Clearing a matrix and changing its type also changes the empty
                # answer container; leaving the old JSON shape would invalidate it.
                if field_type == "matrix":
                    self.converted_base = empty_values() if definition else {}
                else:
                    self.converted_base = [] if field_type == "observation" else ""
        if (definition or self.original_schema.get("matrix_definition") or cleaned.get("revision")) and cleaned.get("revision") != self.expected_revision:
            self.add_error(None, "Dit veld is intussen gewijzigd. Bewaar uw invoer apart en herlaad het veld voordat u opnieuw opslaat.")
        if field_type == "matrix" and definition:
            try:
                definition = normalize_definition(definition)
                self.instance.matrix_definition = definition
                cleaned["matrix_definition"] = definition
                self.instance.rows = [row["label"] for row in definition["rows"]]
                self.instance.columns = [col["label"] for col in definition["columns"]]
                if cleaned.get("required") and not any(
                    spec.get("type") != "label" and not spec.get("read_only")
                    for row in definition["rows"] for column in definition["columns"]
                    for spec in [definition["cells"].get(row["id"], {}).get(column["id"], {})]
                ):
                    self.add_error("required", "Een verplichte matrix heeft minstens één bewerkbare antwoordcel nodig.")
                if isinstance(self.instance, ModuleField) and self.instance.pk and self.original_schema.get("type") == "matrix":
                    self.converted_base = convert_base_values(self.original_schema, definition, self.parent.base_data.get(self.instance.key, {}))
            except ValidationError as exc:
                self.add_error("matrix_definition", exc)
        elif self.original_schema.get("matrix_definition") and field_type == "matrix":
            self.add_error("matrix_definition", "De matrixindeling ontbreekt. Herlaad het veld.")
        elif field_type != "matrix":
            self.instance.matrix_definition = {}
        if field_type == FieldDefinition.FieldType.SELECT and not split_lines(cleaned.get("options_text", "")):
            self.add_error("options_text", "Voeg minstens één optie toe.")
        if field_type == FieldDefinition.FieldType.MATRIX and not definition:
            if not split_lines(cleaned.get("rows_text", "")):
                self.add_error("rows_text", "Voeg minstens één rij toe.")
            if not split_lines(cleaned.get("columns_text", "")):
                self.add_error("columns_text", "Voeg minstens één kolom toe.")
        return cleaned

    def _update_errors(self, errors):
        # Model validation uses JSON field names; the editor exposes text inputs.
        if hasattr(errors, "error_dict"):
            for name in ("options", "rows", "columns"):
                if name in errors.error_dict:
                    errors.error_dict[f"{name}_text"] = errors.error_dict.pop(name)
        super()._update_errors(errors)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.options = split_lines(self.cleaned_data["options_text"])
        if not instance.matrix_definition:
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
        fields = ["title", "description", "category", "education", "theme", "instructions", "is_fixed"]
        labels = {
            "title": "Naam", "description": "Beschrijving", "category": "Categorie",
            "education": "Opleiding", "theme": "Thema", "instructions": "Instructies",
            "is_fixed": "Automatisch toevoegen aan nieuwe casussen",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
        }


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = ["name", "slug"]
        labels = {"name": "Naam", "slug": "Korte code"}


class TeachingGroupForm(forms.ModelForm):
    class Meta:
        model = TeachingGroup
        fields = ["name", "education", "teacher"]
        labels = {"name": "Groepsnaam", "education": "Opleiding", "teacher": "Docent"}


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
