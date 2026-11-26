from copy import deepcopy

from django.db import transaction
from django.db.models import Q

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
    responses = {
        response.module_id: response
        for response in all_responses
        if response.module_id is not None
    }
    detached_by_template = {}
    detached_by_title = {}
    for response in all_responses:
        if response.module_id is not None:
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
        response = responses.get(module.id)
        detached_responses = detached_by_template.pop(module.source_template_id, [])
        if (
            module.source_template_id
            and title_counts[module.title] == 1
        ):
            detached_responses.extend(detached_by_title.pop(module.title, []))
        reattached = response is None and bool(detached_responses)
        schema = module_schema(module)
        if response is None:
            if reattached:
                response = max(detached_responses, key=lambda item: item.updated_at)
                response.module = module
            else:
                response = ModuleResponse(
                    student_case=student_case,
                    module=module,
                    source_template_id_snapshot=module.source_template_id,
                )
                response.hydrate_from_source()
                response.schema = schema
                response.data = deepcopy(module.base_data)
                response.save()
                changed = True
                continue

        if reattached:
            data_sources = sorted(detached_responses, key=lambda item: item.updated_at)
        else:
            data_sources = sorted(
                [response, *detached_responses],
                key=lambda item: item.updated_at,
            )
        merged_data = {}
        for item in data_sources:
            merged_data.update(item.data or {})
        if module.pk in base_data_module_ids:
            merged_data = merge_empty_values(merged_data, module.base_data or {})
        data_changed = merged_data != response.data
        if data_changed:
            response.data = merged_data

        source_values = (module.title, module.kind, module.instructions, module.position, schema)
        current_values = (
            response.title, response.kind, response.instructions, response.position, response.schema
        )
        if (
            reattached
            or data_changed
            or response.source_template_id_snapshot != module.source_template_id
            or source_values != current_values
        ):
            response.hydrate_from_source()
            response.schema = schema
            response.source_template_id_snapshot = module.source_template_id
            response.save(update_fields=[
                "module", "source_template_id_snapshot", "title", "kind", "instructions",
                "position", "schema", "data", "updated_at",
            ])
            changed = True
        duplicate_ids = [
            item.pk for item in detached_responses if item.pk != response.pk
        ]
        if duplicate_ids:
            ModuleResponse.objects.filter(pk__in=duplicate_ids).delete()
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
            response = ModuleResponse(
                student_case=student_case,
                module=module,
                source_template_id_snapshot=module.source_template_id,
            )
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


def synchronize_template_module(template, module):
    return _synchronize_template_module(template, module)


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
        if (
            case.status == Case.Status.DRAFT
            and existing.source_template_version != template.version
        ):
            _synchronize_template_module(template, existing, list(template.fields.all()))
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
    return module


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
                "table", "thead", "tbody", "tr", "th", "td", "a", "blockquote", "img"}

def clean_html(value):
    return nh3.clean(value, tags=ALLOWED_TAGS, attributes={"a": {"href"}, "img": {"src", "alt"}}, url_schemes={"http", "https", "mailto", "data"})