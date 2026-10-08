import json

from django import forms
from django.utils.text import slugify

from .models import (
    Assignment, Case, Education, FieldDefinition, LibraryField, LibraryTemplate,
    LibraryDossier, Module, ModuleField, Patient, TeachingGroup,
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
        self.instance.options = split_lines(cleaned.get("options_text", ""))
        self.instance.rows = split_lines(cleaned.get("rows_text", ""))
        self.instance.columns = split_lines(cleaned.get("columns_text", ""))
        field_type = cleaned.get("field_type")
        if field_type == FieldDefinition.FieldType.SELECT and not split_lines(cleaned.get("options_text", "")):
            self.add_error("options_text", "Voeg minstens één optie toe.")
        if field_type == FieldDefinition.FieldType.MATRIX:
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


class LibraryDossierForm(forms.ModelForm):
    existing_modules = forms.ModelMultipleChoiceField(
        label="Bestaande bibliotheekonderdelen",
        queryset=LibraryTemplate.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "dossier-existing-modules-select"}),
    )
    new_modules = forms.CharField(
        label="Nieuwe modules",
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = LibraryDossier
        fields = ["title", "description", "education"]
        labels = {
            "title": "Naam van het dossier", "description": "Beschrijving",
            "education": "Opleiding",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(
        self, *args, education_queryset=None, module_queryset=None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        if education_queryset is not None:
            self.fields["education"].queryset = education_queryset
        self.fields["existing_modules"].queryset = (
            module_queryset
            if module_queryset is not None
            else LibraryTemplate.objects.filter(status=LibraryTemplate.Status.ACTIVE)
        )
        if self.instance.pk:
            self.fields["existing_modules"].initial = self.instance.modules.filter(
                status=LibraryTemplate.Status.ACTIVE
            )
        if not self.is_bound:
            self.initial["new_modules"] = "[]"

    def clean(self):
        cleaned = super().clean()
        raw_modules = cleaned.get("new_modules", "[]")
        try:
            new_modules = json.loads(raw_modules or "[]")
        except json.JSONDecodeError:
            self.add_error("new_modules", "De ingevoerde nieuwe modules zijn ongeldig.")
            new_modules = []
        if not isinstance(new_modules, list):
            self.add_error("new_modules", "De nieuwe modules moeten een lijst vormen.")
            new_modules = []
        existing_modules = cleaned.get("existing_modules", [])
        existing_titles = {module.title.casefold() for module in existing_modules}
        education = cleaned.get("education")
        for module in existing_modules:
            if module.education_id and (
                education is None or module.education_id != education.id
            ):
                self.add_error(
                    "existing_modules",
                    f"'{module.title}' hoort bij een andere opleiding dan dit dossier.",
                )
                break
        validated_modules = []
        titles = set()
        for index, module in enumerate(new_modules):
            if not isinstance(module, dict):
                self.add_error("new_modules", f"Module {index + 1} is ongeldig.")
                continue
            title = module.get("title", "").strip() if isinstance(module.get("title"), str) else ""
            category = module.get("category")
            if not title or len(title) > 180:
                self.add_error(
                    "new_modules", f"Geef module {index + 1} een naam van maximaal 180 tekens."
                )
                continue
            if title.casefold() in titles:
                self.add_error("new_modules", f"De modulenaam '{title}' komt meerdere keren voor.")
                continue
            titles.add(title.casefold())
            if title.casefold() in existing_titles:
                self.add_error(
                    "new_modules",
                    f"'{title}' is al geselecteerd als bibliotheekonderdeel.",
                )
                continue
            if category not in LibraryTemplate.Category.values:
                self.add_error("new_modules", f"Module '{title}' heeft een ongeldig type.")
                continue
            fields = module.get("fields", [])
            if not isinstance(fields, list):
                self.add_error("new_modules", f"De velden van '{title}' zijn ongeldig.")
                continue
            validated_fields = []
            invalid_module = False
            for field_index, field in enumerate(fields):
                if not isinstance(field, dict):
                    self.add_error(
                        "new_modules",
                        f"Veld {field_index + 1} in '{title}' is ongeldig.",
                    )
                    invalid_module = True
                    break
                label = field.get("label", "").strip() if isinstance(field.get("label"), str) else ""
                field_type = field.get("type")
                if not label or len(label) > 180:
                    self.add_error(
                        "new_modules",
                        f"Geef elk veld in '{title}' een naam van maximaal 180 tekens.",
                    )
                    invalid_module = True
                    break
                if field_type not in FieldDefinition.FieldType.values:
                    self.add_error("new_modules", f"Veld '{label}' heeft een ongeldig veldtype.")
                    invalid_module = True
                    break
                options = field.get("options", [])
                rows = field.get("rows", [])
                columns = field.get("columns", [])
                if not all(isinstance(values, list) for values in (options, rows, columns)):
                    self.add_error("new_modules", f"Keuzeopties of matrix van '{label}' is ongeldig.")
                    invalid_module = True
                    break
                if field_type == FieldDefinition.FieldType.SELECT and not options:
                    self.add_error("new_modules", f"Voeg keuzeopties toe aan '{label}'.")
                    invalid_module = True
                    break
                if field_type == FieldDefinition.FieldType.MATRIX and (not rows or not columns):
                    self.add_error(
                        "new_modules", f"Vul rijen en kolommen in voor matrixveld '{label}'."
                    )
                    invalid_module = True
                    break
                validated_fields.append({
                    "label": label,
                    "type": field_type,
                    "help_text": field.get("help_text", "")[:280]
                    if isinstance(field.get("help_text", ""), str) else "",
                    "required": field.get("required") is True,
                    "options": [value.strip() for value in options if isinstance(value, str) and value.strip()],
                    "rows": [value.strip() for value in rows if isinstance(value, str) and value.strip()],
                    "columns": [value.strip() for value in columns if isinstance(value, str) and value.strip()],
                })
            if not invalid_module:
                validated_modules.append({
                    "title": title,
                    "category": category,
                    "description": module.get("description", "")[:2000]
                    if isinstance(module.get("description", ""), str) else "",
                    "theme": module.get("theme", "")[:120]
                    if isinstance(module.get("theme", ""), str) else "",
                    "instructions": module.get("instructions", "")[:2000]
                    if isinstance(module.get("instructions", ""), str) else "",
                    "fields": validated_fields,
                })
        if not cleaned.get("existing_modules") and not validated_modules:
            self.add_error(
                "existing_modules",
                "Selecteer minstens één bestaand onderdeel of maak minstens één nieuwe module.",
            )
        cleaned["new_modules"] = validated_modules
        return cleaned


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
