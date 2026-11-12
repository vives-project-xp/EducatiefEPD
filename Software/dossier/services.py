from copy import deepcopy

from django.db import transaction

import nh3

from .models import (
    AssignmentSubmission,
    AuditEvent,
    Case,
    LibraryDossier,
    LibraryTemplate,
    Module,
    ModuleField,
    ModuleResponse,
    StudentCase,
)


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


@transaction.atomic
def synchronize_student_case(student_case):
    if student_case.locked:
        return False

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
    responses = {
        response.module_id: response
        for response in student_case.module_responses.all()
        if response.module_id is not None
    }
    for module in modules:
        response = responses.get(module.id)
        schema = module_schema(module)
        if response is None:
            response = ModuleResponse(student_case=student_case, module=module)
            response.hydrate_from_source()
            response.schema = schema
            response.data = deepcopy(module.base_data)
            response.save()
            changed = True
            continue
        source_values = (module.title, module.kind, module.instructions, module.position, schema)
        current_values = (
            response.title, response.kind, response.instructions, response.position, response.schema
        )
        if source_values != current_values:
            response.hydrate_from_source()
            response.schema = schema
            response.save(update_fields=[
                "title", "kind", "instructions", "position", "schema", "updated_at"
            ])
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
            response = ModuleResponse(student_case=student_case, module=module)
            response.hydrate_from_source()
            response.schema = module_schema(module)
            response.data = deepcopy(module.base_data)
            response.save()
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
def copy_template_to_case(template, case):
    template = LibraryTemplate.objects.select_for_update().prefetch_related("fields").get(
        pk=template.pk
    )
    existing = case.modules.filter(source_template=template).first()
    if existing:
        if (
            case.status == Case.Status.DRAFT
            and existing.source_template_version != template.version
        ):
            _synchronize_template_module(template, existing, list(template.fields.all()))
        return existing
    fields = list(template.fields.all())
    last_position = case.modules.order_by("-position").values_list("position", flat=True).first()
    module = Module.objects.create(
        case=case,
        title=template.title,
        kind=_template_module_kind(template, fields),
        instructions=template.instructions,
        position=(last_position if last_position is not None else -1) + 1,
        source_template=template,
        source_template_version=template.version,
        configuration={"library_snapshot": {"title": template.title, "version": template.version}},
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
    return module


@transaction.atomic
def copy_library_dossier_to_case(dossier, case):
    dossier = LibraryDossier.objects.prefetch_related(
        "module_entries__template__fields"
    ).get(pk=dossier.pk)
    return [
        copy_template_to_case(entry.template, case)
        for entry in dossier.module_entries.all()
        if entry.template.status == LibraryTemplate.Status.ACTIVE
    ]

ALLOWED_TAGS = {"p", "br", "strong", "em", "u", "ul", "ol", "li", "h1", "h2", "h3",
                "table", "thead", "tbody", "tr", "th", "td", "a", "blockquote", "img"}

def clean_html(value):
    return nh3.clean(value, tags=ALLOWED_TAGS, attributes={"a": {"href"}, "img": {"src", "alt"}}, url_schemes={"http", "https", "mailto", "data"})