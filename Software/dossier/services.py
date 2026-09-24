from copy import deepcopy

from django.db import transaction

from .models import (
    AssignmentSubmission,
    AuditEvent,
    FieldDefinition,
    LibraryField,
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
    for blueprint in DEFAULT_DOSSIER:
        template, _ = LibraryTemplate.objects.get_or_create(
            title=blueprint["title"],
            defaults={
                "description": blueprint["description"],
                "category": blueprint["category"],
                "education": "Vroedkunde",
                "theme": blueprint["theme"],
                "is_fixed": True,
            },
        )
        if template.fields.exists():
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
    ).order_by("id"):
        copied = case.modules.filter(source_template=template).first()
        if copied:
            if not template.fields.exists() and copied.kind != Module.Kind.INFORMATION:
                copied.kind = Module.Kind.INFORMATION
                copied.save(update_fields=["kind"])
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
        else:
            copy_template_to_case(template, case)


@transaction.atomic
def start_student_case(case, student):
    student_case, created = StudentCase.objects.select_for_update().get_or_create(
        case=case, student=student
    )
    if created or not student_case.case_title:
        student_case.case_title = case.title
        student_case.course = case.course
        student_case.introduction = case.introduction
        student_case.learning_objectives = case.learning_objectives
        student_case.patient_name = case.patient.name
        student_case.patient_reference = case.patient.reference
        student_case.patient_image = case.patient.image
        student_case.patient_context = case.patient.context
        student_case.save()

    for assignment in case.assignments.all():
        submission, submission_created = AssignmentSubmission.objects.get_or_create(
            student_case=student_case, assignment=assignment
        )
        if submission_created or not submission.title:
            submission.hydrate_from_source()
            submission.save()

    for module in case.modules.prefetch_related("fields").all():
        response, response_created = ModuleResponse.objects.get_or_create(
            student_case=student_case, module=module
        )
        if response_created or not response.title:
            response.hydrate_from_source()
            response.schema = module_schema(module)
            if response_created:
                response.data = deepcopy(module.base_data)
            response.save()
    return student_case, created


@transaction.atomic
def copy_template_to_case(template, case):
    template = LibraryTemplate.objects.select_for_update().prefetch_related("fields").get(
        pk=template.pk
    )
    kind_map = {
        LibraryTemplate.Category.MODULE: Module.Kind.FORM,
        LibraryTemplate.Category.QUESTIONNAIRE: Module.Kind.QUESTIONNAIRE,
        LibraryTemplate.Category.MATRIX: Module.Kind.MATRIX,
    }
    module_kind = kind_map[template.category]
    if template.category == LibraryTemplate.Category.MODULE and not template.fields.exists():
        module_kind = Module.Kind.INFORMATION
    last_position = case.modules.order_by("-position").values_list("position", flat=True).first()
    module = Module.objects.create(
        case=case,
        title=template.title,
        kind=module_kind,
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
        )
        for field in template.fields.all()
    ])
    return module
