import json

from django import forms
from django.utils.text import slugify
from django.core.files.uploadedfile import UploadedFile
from django.core.exceptions import ValidationError

from .matrix import blank, convert_base_values, empty_values, fingerprint, legacy_definition, normalize_definition

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
            "image": "Upload hier een afbeelding", "context": "Korte context",
        }
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"})}

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if isinstance(upload, UploadedFile) and upload.size > 10 * 1024 * 1024:
            raise forms.ValidationError("De foto mag maximaal 10 MB groot zijn.")
        return upload


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
            "phase": "Fase", "title": "Titel",
            "content": "Beschrijving", "position": "Nummer",
        }
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Geef hier een titel aan je opdracht"
                }),
            "content": forms.Textarea(attrs={
                "class": "rich",
                "placeholder": "Schrijf hier de beschrijving of instructies van de opdracht"
                })
            }


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
        fields = ["title", "description", "category", "education", "theme", "instructions"]
        labels = {
            "title": "Naam", "description": "Beschrijving", "category": "Categorie",
            "education": "Opleiding", "theme": "Thema", "instructions": "Instructies",
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
        widget=forms.CheckboxSelectMultiple,
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
                pk__in=self.fields["existing_modules"].queryset.values("pk")
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
                if any(
                    not isinstance(value, str) or len(value) > 500
                    for values in (options, rows, columns) for value in values
                ):
                    self.add_error("new_modules", f"Keuzeopties of matrix van '{label}' is ongeldig.")
                    invalid_module = True
                    break
                options = [value.strip() for value in options if value.strip()]
                rows = [value.strip() for value in rows if value.strip()]
                columns = [value.strip() for value in columns if value.strip()]
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
                    "options": options,
                    "rows": rows,
                    "columns": columns,
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

    def clean(self):
        cleaned_data = super().clean()
        education = cleaned_data.get("education")
        if self.instance.pk and education and education.pk != self.instance.education_id:
            if self.instance.cases.exclude(education=education).exists():
                self.add_error(
                    "education",
                    "Wijzig de opleiding pas nadat alle gekoppelde casussen bij deze opleiding horen.",
                )
            if self.instance.members.filter(
                epd_profile__education__isnull=False
            ).exclude(epd_profile__education=education).exists():
                self.add_error(
                    "education",
                    "Verwijder eerst studenten van een andere opleiding uit deze lesgroep.",
                )
        return cleaned_data


class LibraryFieldForm(FieldConfigurationForm):
    class Meta:
        model = LibraryField
        fields = ["label", "field_type", "help_text", "required", "position"]
        labels = ModuleFieldForm.Meta.labels


class ReviewForm(forms.Form):
    field_order = ["feedback", "status"]

    status = forms.ChoiceField(
        label="Beoordeling",
        choices=[("approved", "Goedgekeurd"), ("resubmit", "Opnieuw inleveren")],
    )
    feedback = forms.CharField(
        label="Feedback", required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "js-tinymce"})
    )
