import re
from copy import deepcopy
from urllib.parse import urlencode, urlparse

from django.db import transaction
from django.db.models import Q
from django.utils.html import linebreaks
from django.utils.safestring import mark_safe

import nh3

from .models import (
    AssignmentSubmission,
    AuditEvent,
    Case,
    LibraryDossier,
    LibraryTemplate,
    CaseFunctionSnapshot,
    ManagedForm,
    Module,
    ModuleField,
    ModuleResponse,
    StudentCase,
)
from .matrix import legacy_definition

STUDENT_BASE_DATA_VERSION = "student_base_data_version"
STUDENT_BASE_DATA_HANDLED_VERSION = "student_base_data_handled_version"
STUDENT_BASE_DATA_APPROVED_VERSION = "student_base_data_approved_version"
STUDENT_BASE_DATA_APPLIED_VERSION = "student_base_data_applied_version"


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def audit(request, action, target, **details):
    AuditEvent.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        target_type=target.__class__.__name__,
        target_id=str(target.pk),
        details=details,
        ip_address=client_ip(request),
    )


def legacy_schema(module):
    if module.kind == Module.Kind.QUESTIONNAIRE:
        return [
            {
                "label": question, "key": f"q_{index}", "type": "long_text",
                "help_text": "", "required": False, "position": index,
                "options": [], "rows": [], "columns": [],
            }
            for index, question in enumerate(module.configuration.get("questions", []))
        ]
    if module.kind == Module.Kind.MATRIX and module.configuration.get("rows"):
        return [{
            "label": module.title, "key": "matrix_0", "type": "matrix",
            "help_text": "", "required": False, "position": 0, "options": [],
            "rows": module.configuration.get("rows", []),
            "columns": module.configuration.get("columns", []),
        }]
    if module.kind == Module.Kind.NOTES:
        return [{
            "label": "Notities", "key": "content", "type": "long_text",
            "help_text": "", "required": False, "position": 0,
            "options": [], "rows": [], "columns": [],
        }]
    return []


def module_schema(module):
    fields = list(module.fields.all())
    return [field.as_schema() for field in fields] if fields else legacy_schema(module)


def sync_student_module_response(response):
    """Refresh a student's structure from the case while preserving their edits."""
    module = response.module
    if module is None or response.status == ModuleResponse.Status.PUBLISHED:
        return False
    live_schema = module_schema(module)
    current_data = deepcopy(response.data if isinstance(response.data, dict) else {})
    source_data = deepcopy(response.source_data if isinstance(response.source_data, dict) else {})
    base_data = deepcopy(module.base_data if isinstance(module.base_data, dict) else {})
    if isinstance(current_data, dict) and not current_data.get("_functions"):
        current_data.pop("_functions", None)
    for key, default in base_data.items():
        if key not in current_data or current_data.get(key) == source_data.get(key):
            current_data[key] = deepcopy(default)
    changed = (
        response.schema != live_schema
        or response.data != current_data
        or response.source_data != base_data
    )
    if changed:
        response.schema = live_schema
        response.data = current_data
        response.source_data = base_data
        response.save(update_fields=["schema", "data", "source_data", "updated_at"])
    return changed


def build_function_hierarchy(functions):
    return [{
        "id": function["id"],
        "title": function["title"],
        "kind": function["kind"],
        "forms": [
            {"id": form["id"], "title": form["title"] or "Naamloos formulier"}
            for form in function.get("forms", [])
        ],
    } for function in functions]


def build_library_structure(module_entries):
    structure = []
    for entry in module_entries:
        functions = build_function_hierarchy([{
            "id": link.function_id,
            "title": link.function.title,
            "kind": "Formulierengroep" if link.function.kind == "groep" else "Formulier",
            "forms": [
                {"id": form.id, "title": form.title}
                for form in link.function.forms.all()
            ],
        } for link in entry.template.function_links.all()
          if link.function.deleted_at is None])
        structure.append({
            "title": entry.template.title,
            "template_id": entry.template_id,
            "kind": entry.template.get_category_display(),
            "functions": functions,
        })
    return structure


def build_sidebar_structure(module_responses, query=""):
    query = query.casefold()
    structure = []
    for item in module_responses:
        entry = item if hasattr(item, "meta_key") else None
        response = entry.representative if entry else item
        module = entry.module if entry else response.module
        snapshots = (
            [snapshot for snapshot in module.function_snapshots.all() if snapshot.active]
            if module else []
        )
        functions = []
        for snapshot in snapshots:
            definition = snapshot.definition or {}
            functions.append({
                "id": snapshot.id, "title": snapshot.title,
                "kind": "Formulierengroep" if snapshot.kind == "groep" else "Formulier",
                "forms": [
                    {"id": form.get("id", form.get("position", 0)), "title": form.get("title", "")}
                    for form in definition.get("forms", [])
                ],
            })
        functions = build_function_hierarchy(functions)
        module_key = entry.meta_key if entry else str(response.id)
        registration_id = entry.registrations[0].id if entry else response.id
        for function in functions:
            params = {
                "module": module_key,
                "function": function["id"],
                "weergave": "invoer",
                "registratie": registration_id,
            }
            if query:
                params["q"] = query
            function["url"] = f"?{urlencode(params)}"
        searchable = " ".join(
            [response.title, *(item["title"] for item in functions)]
        ).casefold()
        if not query or query in searchable:
            registrations = entry.responses if entry else [response]
            structure.append({
                "id": module_key,
                "title": response.title,
                "kind": response.kind,
                "registration_id": registration_id,
                "functions": functions,
                "revision_requested": any(
                    registration.revision_requested for registration in registrations
                ),
                "feedback": any(registration.feedback for registration in registrations),
            })
    return structure


DEFAULT_DOSSIER = [
    {
        "title": "Dashboard", "category": "module", "theme": "Algemeen",
        "description": "Samenvatting van de fictieve patiënt.", "fields": [],
    },
    {
        "title": "Anamnese", "category": "questionnaire", "theme": "Opname",
        "description": "Klachten, symptomen en relevante voorgeschiedenis.",
        "fields": [
            ("Reden van opname", "long_text"), ("Huidige klachten en symptomen", "long_text"),
            ("Medische voorgeschiedenis", "long_text"), ("Allergieën", "long_text"),
            ("Medicatie", "long_text"), ("Obstetrische voorgeschiedenis", "long_text"),
        ],
    },
    {
        "title": "Zwangerschapsdossier", "category": "module", "theme": "Zwangerschap",
        "description": "Basisgegevens van de zwangerschap.",
        "fields": [
            ("Zwangerschapsduur (weken)", "number"), ("Uitgerekende datum", "date"),
            ("Gravida", "number"), ("Para", "number"), ("Risicofactoren", "long_text"),
        ],
    },
    {
        "title": "Partusdossier", "category": "module", "theme": "Partus",
        "description": "Registratie van arbeid en bevalling.",
        "fields": [
            ("Start contracties", "datetime"), ("Vliezen gebroken", "datetime"),
            ("Ontsluiting (cm)", "number"), ("Foetale hartfrequentie", "number"),
            ("Klinische observaties", "observation"),
        ],
    },
    {
        "title": "MIC dossier", "category": "module", "theme": "Risicozorg",
        "description": "Maternal intensive care registratie.",
        "fields": [("Indicatie", "long_text"), ("Opnamedatum", "date"), ("Observaties", "observation")],
    },
    {
        "title": "Postpartumdossier", "category": "module", "theme": "Postpartum",
        "description": "Opvolging na de bevalling.",
        "fields": [("Bloedverlies (ml)", "number"), ("Toestand moeder en kind", "long_text"), ("Observaties", "observation")],
    },
    {
        "title": "Kort verslag graviditeit, partus en postpartum", "category": "module", "theme": "Verslag",
        "description": "Beknopt klinisch verslag.", "fields": [("Verslag", "long_text")],
    },
    {
        "title": "NICU / N*-dossier", "category": "module", "theme": "Neonatologie",
        "description": "Registratie voor neonatale opvolging.",
        "fields": [("Indicatie", "long_text"), ("Neonatale observaties", "observation")],
    },
    {
        "title": "Screening emotioneel welzijn", "category": "questionnaire", "theme": "Welzijn",
        "description": "Screening van het emotioneel welzijn.",
        "fields": [("Actuele beleving", "long_text"), ("Signalen of aandachtspunten", "long_text")],
    },
    {
        "title": "Klinisch redeneerplan", "category": "matrix", "theme": "Klinisch redeneren",
        "description": "Gestructureerd zorg- en redeneerplan.",
        "matrix": {
            "label": "Klinisch redeneerplan",
            "rows": ["Probleem of diagnose", "Gewenst resultaat", "Interventie", "Evaluatie"],
            "columns": ["Beschrijving", "Motivatie"],
        },
    },
    {
        "title": "Uitwerking opdracht", "category": "module", "theme": "Opdrachten",
        "description": "Vrije uitwerking van de onderwijsopdracht.", "fields": [("Uitwerking", "long_text")],
    },
]


@transaction.atomic
def ensure_default_templates():
    education, _ = Education.objects.get_or_create(
        slug="vroedkunde", defaults={"name": "Vroedkunde"}
    )
    for blueprint in DEFAULT_DOSSIER:
        template, created = LibraryTemplate.objects.get_or_create(
            seed_key=f"vroedkunde-{slugify(blueprint['title'])}",
            defaults={
                "title": blueprint["title"],
                "education": education,
                "description": blueprint["description"],
                "category": blueprint["category"],
                "theme": blueprint["theme"],
                "is_fixed": True,
            },
        )
        if not created:
            continue
        for position, (label, field_type) in enumerate(blueprint.get("fields", [])):
            LibraryField.objects.create(
                template=template, label=label, key=f"veld-{position + 1}",
                field_type=field_type, position=position,
            )
        matrix = blueprint.get("matrix")
        if matrix:
            LibraryField.objects.create(
                template=template, label=matrix["label"], key="matrix-1",
                field_type=FieldDefinition.FieldType.MATRIX,
                rows=matrix["rows"], columns=matrix["columns"], position=0,
            )


@transaction.atomic
def create_case_structure(case):
    ensure_default_templates()
    for template in LibraryTemplate.objects.filter(
        status=LibraryTemplate.Status.ACTIVE, is_fixed=True
    ).filter(Q(education=case.education) | Q(education__isnull=True)).order_by("id"):
        copied = case.modules.filter(source_template=template).first()
        if copied:
            continue
        existing = case.modules.filter(title=template.title).first()
        if existing:
            existing.source_template = template
            existing.source_template_version = template.version
            existing.save(update_fields=["source_template", "source_template_version"])
            if not existing.fields.exists():
                ModuleField.objects.bulk_create([
                    ModuleField(
                        module=existing, label=field.label, key=field.key,
                        field_type=field.field_type, help_text=field.help_text,
                        required=field.required, position=field.position,
                        options=field.options, rows=field.rows, columns=field.columns,
                    )
                    for field in template.fields.all()
                ])
            snapshot_template_functions(existing, template)
        else:
            copy_template_to_case(template, case)
def pending_student_base_data_version(configuration):
    version = configuration.get(STUDENT_BASE_DATA_VERSION)
    if type(version) is int and version > 0 and configuration.get(
        STUDENT_BASE_DATA_HANDLED_VERSION
    ) != version:
        return version
    return None


def merge_empty_values(data, defaults):
    if isinstance(data, dict) and isinstance(defaults, dict):
        merged = deepcopy(data)
        for key, default in defaults.items():
            if key in merged:
                merged[key] = merge_empty_values(merged[key], default)
            else:
                merged[key] = deepcopy(default)
        return merged
    if data is None or data == "" or data == []:
        return deepcopy(defaults)
    return data


def new_registration(student_case, module, *, author):
    """Maakt een nieuwe, lege registratie (invulling) voor één module van een dossier."""
    if student_case.locked:
        raise ValueError("Een ingeleverd dossier kan niet bewerkt worden.")
    with transaction.atomic():

        response = student_case.module_responses.create(
            module=module,
            created_by=author,
            source_template_id_snapshot=module.source_template_id,
        )

        response.hydrate_from_source()
        response.schema = module_schema(module)
        response.data = deepcopy(module.base_data if isinstance(module.base_data, dict) else {})
        response.source_data = deepcopy(response.data)
        response.save()
    return response


def _filled(value):
    if isinstance(value, dict):
        return any(_filled(item) for item in value.values())
    if isinstance(value, list):
        return any(_filled(item) for item in value)
    return bool(value)


def registration_is_empty(response):
    """Check both module fields and function answers for submitted content."""
    module_values = any(
        _filled(response.data.get(field.get("key")))
        for field in response.schema
    )
    function_values = response.data.get("_functions", {})
    return not module_values and not bool(function_values)


@transaction.atomic
def synchronize_student_case(student_case, *, base_data_module_ids=None):
    if student_case.locked:
        return False

    base_data_module_ids = set(base_data_module_ids or ())
    changed = False
    assignments = list(student_case.case.assignments.all())
    submissions = {
        submission.assignment_id: submission
        for submission in student_case.assignment_submissions.all()
        if submission.assignment_id is not None
    }
    for assignment in assignments:
        submission = submissions.get(assignment.id)
        if submission is None:
            submission = AssignmentSubmission(student_case=student_case, assignment=assignment)
            submission.hydrate_from_source()
            submission.save()
            changed = True
            continue
        source_values = (assignment.phase, assignment.title, assignment.content, assignment.position)
        current_values = (submission.phase, submission.title, submission.content, submission.position)
        if source_values != current_values:
            submission.hydrate_from_source()
            submission.save(update_fields=["phase", "title", "content", "position", "updated_at"])
            changed = True

    modules = list(student_case.case.modules.prefetch_related("fields").all())
    all_responses = list(student_case.module_responses.all())
    responses_by_module = {}
    detached_by_template = {}
    detached_by_title = {}
    for response in all_responses:
        if response.module_id is not None:
            responses_by_module.setdefault(response.module_id, []).append(response)
            continue
        if response.source_template_id_snapshot is None:
            detached_by_title.setdefault(response.title, []).append(response)
        else:
            detached_by_template.setdefault(
                response.source_template_id_snapshot, []
            ).append(response)
    title_counts = {}
    for module in modules:
        title_counts[module.title] = title_counts.get(module.title, 0) + 1

    for module in modules:
        module_responses = responses_by_module.get(module.id, [])
        detached_responses = (
            detached_by_template.pop(module.source_template_id, [])
            if module.source_template_id
            else []
        )
        legacy_responses = []
        if (
            module.source_template_id
            and title_counts[module.title] == 1
        ):
            legacy_responses = detached_by_title.pop(module.title, [])
        schema = module_schema(module)
        module_responses.extend(detached_responses)
        if not module_responses and legacy_responses:
            module_responses.append(
                max(legacy_responses, key=lambda item: item.updated_at)
            )
            legacy_responses.remove(module_responses[0])
        if not module_responses:
            new_registration(student_case, module, author=student_case.student)
            changed = True
            continue
        if legacy_responses:
            response = max(module_responses, key=lambda item: item.updated_at)
            data_sources = sorted(
                [response, *legacy_responses],
                key=lambda item: item.updated_at,
            )
            merged_data = {}
            for item in data_sources:
                merged_data.update(item.data or {})
            if merged_data != response.data:
                response.data = merged_data
                changed = True
            for item in legacy_responses:
                item.delete()
                changed = True

        for response in module_responses:
            detached = response.module_id is None
            response.module = module
            if module.pk in base_data_module_ids:
                merged_data = merge_empty_values(
                    response.data or {}, module.base_data or {}
                )
            else:
                merged_data = response.data
            data_changed = merged_data != response.data
            if data_changed:
                response.data = merged_data

            source_values = (
                module.title, module.kind, module.instructions, module.position, schema
            )
            current_values = (
                response.title, response.kind, response.instructions,
                response.position, response.schema
            )
            if (
                detached
                or data_changed
                or response.source_template_id_snapshot != module.source_template_id
                or source_values != current_values
            ):
                response.hydrate_from_source()
                response.schema = schema
                response.source_template_id_snapshot = module.source_template_id
                response.save(update_fields=[
                    "module", "source_template_id_snapshot", "title", "kind",
                    "instructions", "position", "schema", "data", "updated_at",
                ])
                changed = True
            if sync_student_module_response(response):
                changed = True
    return changed


@transaction.atomic
def start_student_case(case, student):
    student_case, created = StudentCase.objects.select_for_update().get_or_create(
        case=case, student=student
    )
    if created:
        student_case.case_title = case.title
        student_case.course = case.course
        student_case.introduction = case.introduction
        student_case.learning_objectives = case.learning_objectives
        student_case.patient_name = case.patient.name
        student_case.patient_reference = case.patient.reference
        student_case.patient_image = case.patient.image.url if case.patient.image else ""
        student_case.patient_context = case.patient.context
        student_case.save()

        for assignment in case.assignments.all():
            submission = AssignmentSubmission(student_case=student_case, assignment=assignment)
            submission.hydrate_from_source()
            submission.save()

        for module in case.modules.prefetch_related("fields").all():
            new_registration(student_case, module, author=student)
    else:
        synchronize_student_case(student_case)
    return student_case, created


def _template_module_kind(template, fields):
    kind_map = {
        LibraryTemplate.Category.MODULE: Module.Kind.FORM,
        LibraryTemplate.Category.QUESTIONNAIRE: Module.Kind.QUESTIONNAIRE,
        LibraryTemplate.Category.MATRIX: Module.Kind.MATRIX,
    }
    kind = kind_map[template.category]
    if template.category == LibraryTemplate.Category.MODULE and not fields:
        kind = Module.Kind.INFORMATION
    return kind


def _synchronize_template_module(template, module, fields=None):
    fields = list(fields if fields is not None else template.fields.all())
    module.title = template.title
    module.kind = _template_module_kind(template, fields)
    module.instructions = template.instructions
    module.source_template_version = template.version
    configuration = dict(module.configuration or {})
    configuration["library_snapshot"] = {
        **dict(configuration.get("library_snapshot") or {}),
        "title": template.title,
        "version": template.version,
    }
    module.configuration = configuration
    module.save(update_fields=[
        "title", "kind", "instructions", "source_template_version", "configuration"
    ])

    existing_fields = {field.key: field for field in module.fields.all()}
    source_keys = {field.key for field in fields}
    for source_field in fields:
        values = {
            "label": source_field.label,
            "field_type": source_field.field_type,
            "help_text": source_field.help_text,
            "required": source_field.required,
            "position": source_field.position,
            "options": deepcopy(source_field.options),
            "rows": deepcopy(source_field.rows),
            "columns": deepcopy(source_field.columns),
            "matrix_definition": deepcopy(source_field.matrix_definition),
        }
        field = existing_fields.get(source_field.key)
        if field is None:
            ModuleField.objects.create(module=module, key=source_field.key, **values)
        else:
            for name, value in values.items():
                setattr(field, name, value)
            field.save(update_fields=list(values))
    module.fields.exclude(key__in=source_keys).delete()
    return module


def synchronize_template_module(template, module):
    return _synchronize_template_module(template, module)


def _function_snapshot_values(link):
    return {
        "source_function_id": link.function_id,
        "title": link.function.title,
        "kind": link.function.kind,
        "position": link.position,
        "definition": {
            "title": link.function.title,
            "kind": link.function.kind,
            "forms": [
                {
                    "id": form.id,
                    "title": form.title,
                    "position": form.position,
                    "questions": [
                        {
                            "id": question.id,
                            "fieldType": question.field_type,
                            "question": question.question,
                            "unit": question.unit,
                            "required": question.required,
                            "options": question.options,
                            "columns": question.columns,
                            "rows": question.rows,
                            "matrixDefinition": deepcopy(question.matrix_definition) or (
                                legacy_definition(question.rows, question.columns)
                                if question.field_type == "matrix" else {}
                            ),
                            "url": question.url,
                            "buttonText": question.button_text,
                            "image": question.image,
                            "caption": question.caption,
                            "explanation": question.explanation,
                            "position": question.position,
                        }
                        for question in form.questions.all()
                    ],
                }
                for form in link.function.forms.all()
            ],
        },
    }


def _template_function_links(template):
    return list(
        template.function_links.filter(function__deleted_at__isnull=True)
        .select_related("function")
        .prefetch_related("function__forms__questions")
    )


@transaction.atomic
def synchronize_module_to_students(module, *, apply_base_data=False):
    base_data_module_ids = {module.pk} if apply_base_data else set()
    for student_case in module.case.student_cases.select_for_update().all():
        synchronize_student_case(
            student_case,
            base_data_module_ids=base_data_module_ids,
        )


@transaction.atomic
def detach_module_responses(module):
    ModuleResponse.objects.filter(module=module).update(
        module=None,
        source_template_id_snapshot=module.source_template_id,
    )


@transaction.atomic
def synchronize_template_to_draft_cases(template):
    template = LibraryTemplate.objects.prefetch_related("fields").get(pk=template.pk)
    fields = list(template.fields.all())
    modules = Module.objects.filter(
        source_template=template,
        case__status=Case.Status.DRAFT,
    ).prefetch_related("fields")
    updated_modules = 0
    for module in modules:
        if module.source_template_version == template.version:
            continue
        _synchronize_template_module(template, module, fields)
        updated_modules += 1
    return updated_modules


@transaction.atomic
def copy_template_to_case(template, case, source_dossier=None):
    template = LibraryTemplate.objects.select_for_update().prefetch_related("fields").get(
        pk=template.pk
    )
    existing = case.modules.filter(source_template=template).first()
    if existing:
        return existing
    fields = list(template.fields.all())
    last_position = case.modules.order_by("-position").values_list("position", flat=True).first()
    configuration = {"library_snapshot": {"title": template.title, "version": template.version}}
    if source_dossier is not None:
        configuration["source_library_dossier_id"] = source_dossier.pk
    module = Module.objects.create(
        case=case,
        title=template.title,
        kind=_template_module_kind(template, fields),
        instructions=template.instructions,
        position=(last_position if last_position is not None else -1) + 1,
        source_template=template,
        source_template_version=template.version,
        configuration=configuration,
    )
    ModuleField.objects.bulk_create([
        ModuleField(
            module=module, label=field.label, key=field.key,
            field_type=field.field_type, help_text=field.help_text,
            required=field.required, position=field.position,
            options=field.options, rows=field.rows, columns=field.columns,
            matrix_definition=deepcopy(field.matrix_definition),
        )
        for field in fields
    ])
    snapshot_template_functions(module, template)
    return module


def snapshot_template_functions(module, template):
    if module.function_snapshots.exists():
        return
    CaseFunctionSnapshot.objects.bulk_create([
        CaseFunctionSnapshot(module=module, **_function_snapshot_values(link))
        for link in _template_function_links(template)
    ])


@transaction.atomic
def synchronize_template_function_snapshots(template, module):
    links = _template_function_links(template)
    live_function_ids = {link.function_id for link in links}
    all_snapshots = list(module.function_snapshots.all())
    active_snapshots = [snapshot for snapshot in all_snapshots if snapshot.active]
    legacy_form_ids = {
        int(form["id"])
        for snapshot in active_snapshots
        for form in (snapshot.definition or {}).get("forms", [])
        if isinstance(form, dict) and str(form.get("id", "")).isdigit()
    }
    form_owners = dict(
        ManagedForm.objects.filter(id__in=legacy_form_ids).values_list("id", "function_id")
    )
    existing_function_ids = set()
    inactive_by_function_id = {}

    for snapshot in active_snapshots:
        source_function_id = snapshot.source_function_id
        source_id_was_missing = source_function_id is None
        if source_function_id is None:
            form_function_ids = {
                form_owners[int(form["id"])]
                for form in (snapshot.definition or {}).get("forms", [])
                if isinstance(form, dict)
                and str(form.get("id", "")).isdigit()
                and int(form["id"]) in form_owners
            }
            if len(form_function_ids) == 1:
                source_function_id = form_function_ids.pop()
                snapshot.source_function_id = source_function_id

        if source_function_id not in live_function_ids:
            snapshot.active = False
            snapshot.save(update_fields=["source_function_id", "active"])
            continue

        existing_function_ids.add(source_function_id)
        link = next(item for item in links if item.function_id == source_function_id)
        if snapshot.position != link.position or source_id_was_missing:
            snapshot.position = link.position
            snapshot.save(update_fields=["source_function_id", "position"])

    for snapshot in all_snapshots:
        if not snapshot.active and snapshot.source_function_id is not None:
            inactive_by_function_id.setdefault(snapshot.source_function_id, []).append(snapshot)

    new_snapshots = []
    for link in links:
        if link.function_id in existing_function_ids:
            continue
        values = _function_snapshot_values(link)
        previous = inactive_by_function_id.get(link.function_id, [])
        reusable = next((
            snapshot for snapshot in reversed(previous)
            if (
                snapshot.title == values["title"]
                and snapshot.kind == values["kind"]
                and snapshot.definition == values["definition"]
            )
        ), None)
        if reusable:
            reusable.active = True
            reusable.position = link.position
            reusable.save(update_fields=["active", "position"])
        else:
            new_snapshots.append(CaseFunctionSnapshot(module=module, **values))

    CaseFunctionSnapshot.objects.bulk_create(new_snapshots)


@transaction.atomic
def copy_library_dossier_to_case(dossier, case):
    dossier = LibraryDossier.objects.prefetch_related(
        "module_entries__template__fields"
    ).get(pk=dossier.pk)
    return [
        copy_template_to_case(entry.template, case, source_dossier=dossier)
        for entry in dossier.module_entries.all()
        if entry.template.status == LibraryTemplate.Status.ACTIVE
    ]


@transaction.atomic
def synchronize_dossier_additions_to_cases(dossier, previous_template_ids):
    entries = list(
        dossier.module_entries.select_related("template").filter(
            template__status=LibraryTemplate.Status.ACTIVE,
        )
    )
    added_entries = [
        entry for entry in entries if entry.template_id not in previous_template_ids
    ]
    current_template_ids = {entry.template_id for entry in entries}
    membership_changed = previous_template_ids != current_template_ids

    case_ids = Module.objects.filter(
        Q(configuration__source_library_dossier_id=dossier.pk)
        | Q(configuration__source_library_dossier_id=str(dossier.pk))
    ).values_list("case_id", flat=True).distinct()
    cases = Case.objects.filter(id__in=case_ids)
    added_modules = 0
    for case in cases:
        for module in case.modules.select_for_update().all():
            configuration = dict(module.configuration or {})
            if str(configuration.get("source_library_dossier_id")) == str(dossier.pk):
                if module.source_template_id not in current_template_ids:
                    configuration["library_dossier_module_removed"] = True
                    if membership_changed:
                        configuration.pop("library_removal_handled", None)
                    configuration.pop("library_dossier_order_changed", None)
                    configuration.pop("library_dossier_pending_position", None)
                    configuration.pop("library_dossier_order_handled_position", None)
                else:
                    configuration.pop("library_dossier_module_removed", None)
                    configuration.pop("library_removal_handled", None)
                module.configuration = configuration
                module.save(update_fields=["configuration"])
        for entry in added_entries:
            existing_module = case.modules.filter(source_template=entry.template).first()
            if existing_module:
                configuration = dict(existing_module.configuration or {})
                if str(configuration.get("source_library_dossier_id")) == str(dossier.pk):
                    configuration.pop("library_dossier_module_removed", None)
                    configuration.pop("library_removal_handled", None)
                    configuration.pop("library_change_handled_version", None)
                    existing_module.configuration = configuration
                    existing_module.source_template_version = max(entry.template.version - 1, 0)
                    existing_module.save(update_fields=[
                        "configuration", "source_template_version"
                    ])
                continue
            module = copy_template_to_case(entry.template, case, source_dossier=dossier)
            module.source_template_version = max(entry.template.version - 1, 0)
            module.save(update_fields=["source_template_version"])
            added_modules += 1

        modules_by_template = {
            module.source_template_id: module
            for module in case.modules.all()
            if (
                str((module.configuration or {}).get("source_library_dossier_id"))
                == str(dossier.pk)
                and module.source_template_id in current_template_ids
            )
        }
        ordered_modules = [
            modules_by_template[entry.template_id]
            for entry in entries
            if entry.template_id in modules_by_template
        ]
        position_slots = sorted(module.position for module in ordered_modules)
        for module, position in zip(ordered_modules, position_slots):
            configuration = dict(module.configuration or {})
            if module.position == position:
                configuration.pop("library_dossier_order_changed", None)
                configuration.pop("library_dossier_pending_position", None)
                configuration.pop("library_dossier_order_handled_position", None)
            elif configuration.get("library_dossier_order_handled_position") != position:
                configuration["library_dossier_order_changed"] = True
                configuration["library_dossier_pending_position"] = position
                configuration.pop("library_dossier_order_handled_position", None)
            module.configuration = configuration
            module.save(update_fields=["configuration"])
    return added_modules


@transaction.atomic
def resolve_dossier_module_order(case, dossier_id, apply):
    modules = case.modules.select_for_update().filter(
        Q(configuration__source_library_dossier_id=dossier_id)
        | Q(configuration__source_library_dossier_id=str(dossier_id))
    )
    updated_modules = []
    for module in modules:
        configuration = dict(module.configuration or {})
        if not configuration.get("library_dossier_order_changed"):
            continue
        position = configuration.get("library_dossier_pending_position")
        if not isinstance(position, int):
            continue
        if apply:
            module.position = position
            configuration.pop("library_dossier_order_handled_position", None)
        else:
            configuration["library_dossier_order_handled_position"] = position
        configuration.pop("library_dossier_order_changed", None)
        configuration.pop("library_dossier_pending_position", None)
        module.configuration = configuration
        update_fields = ["configuration"]
        if apply:
            update_fields.append("position")
            updated_modules.append(module)
        module.save(update_fields=update_fields)
    return updated_modules


ALLOWED_TAGS = {"p", "br", "strong", "em", "u", "ul", "ol", "li", "h1", "h2", "h3",
                "h4", "h5", "h6", "pre", "span",
                "table", "thead", "tbody", "tr", "th", "td", "a", "blockquote", "img"}
# Alleen tekst- en markeerkleur uit TinyMCE (forecolor/backcolor) blijven
# behouden, zodat docenten correcties kunnen kleuren. Andere CSS (position,
# url(...), ...) wordt verwijderd.
ALLOWED_STYLE_PROPERTIES = {"color", "background-color"}
ALLOWED_ATTRIBUTES = {"a": {"href"}, "img": {"src", "alt"}, "span": {"style"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "data"}
_UNSAFE_LINK_SCHEMES = {"data", "javascript"}
_HTML_TAG = re.compile(r"<[a-zA-Z/!]")


def _reject_unsafe_link(tag, attr, value):
    if attr == "href" and value:
        if urlparse(value).scheme.lower() in _UNSAFE_LINK_SCHEMES:
            return None
    return value


def clean_html(value):
    """Saneer HTML van gebruikers (studentantwoorden, feedback, rich text)."""
    return nh3.clean(
        value or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        filter_style_properties=ALLOWED_STYLE_PROPERTIES,
        attribute_filter=_reject_unsafe_link,
    )


def render_rich_text(value):
    """Gesaneerde, veilig te tonen HTML voor opgeslagen tekst.

    Oude of gewone tekst zonder HTML-tags krijgt alinea's en regeleindes;
    HTML uit de editor wordt alleen gesaneerd (geen extra <p>/<br>). nh3
    escapet losse tekens zoals '<' en '&', dus linebreaks hoeft niet opnieuw
    te escapen.
    """
    cleaned = clean_html(value)
    if not _HTML_TAG.search(cleaned):
        cleaned = linebreaks(cleaned, autoescape=False)
    return mark_safe(cleaned)

def update_student_case_review_state(student_case, *, require_submitted=False):
    """Leid de status van een studentversie af uit de beoordelingen.

    - Een opdracht op 'Opnieuw inleveren' of een module waarvoor de docent een
      aanpassing vraagt, heropent de studentversie (Bezig).
    - Zijn alle opdrachten goedgekeurd en staat er niets meer open, dan is de
      studentversie Beoordeeld. Met require_submitted gebeurt dat alleen als de
      student het dossier (opnieuw) heeft ingediend, zodat modulefeedback geen
      onafgewerkt dossier afsluit.
    """
    from django.utils import timezone

    pending = (
        student_case.assignment_submissions.filter(status=AssignmentSubmission.Status.RESUBMIT).exists()
        or student_case.module_responses.filter(revision_requested=True).exists()
    )
    if pending:
        student_case.status = StudentCase.Status.ACTIVE
    elif not student_case.assignment_submissions.exclude(
        status=AssignmentSubmission.Status.APPROVED
    ).exists() and (not require_submitted or student_case.status == StudentCase.Status.SUBMITTED):
        student_case.status = StudentCase.Status.REVIEWED
        student_case.reviewed_at = timezone.now()
    else:
        return
    student_case.save(update_fields=["status", "reviewed_at", "updated_at"])
