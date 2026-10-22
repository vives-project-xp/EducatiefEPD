from copy import deepcopy

from django.db import transaction

import nh3

from .models import (
    AssignmentSubmission,
    AuditEvent,
    LibraryDossier,
    LibraryTemplate,
    CaseFunctionSnapshot,
    Module,
    ModuleField,
    ModuleResponse,
    StudentCase,
)
from .matrix import legacy_definition


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
        } for link in entry.template.function_links.all()])
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
    for response in module_responses:
        snapshots = list(response.module.function_snapshots.all()) if response.module else []
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
        for function in functions:
            function["url"] = f"?module={response.id}&function={function['id']}"
        searchable = " ".join(
            [response.title, *(item["title"] for item in functions)]
        ).casefold()
        if not query or query in searchable:
            structure.append({
                "id": response.id,
                "title": response.title,
                "kind": response.kind,
                "functions": functions,
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
        student_case.patient_image = case.patient.image
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
    return student_case, created


@transaction.atomic
def copy_template_to_case(template, case):
    template = LibraryTemplate.objects.select_for_update().prefetch_related("fields").get(
        pk=template.pk
    )
    existing = case.modules.filter(source_template=template).first()
    if existing:
        return existing
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
            matrix_definition=deepcopy(field.matrix_definition),
        )
        for field in template.fields.all()
    ])
    snapshot_template_functions(module, template)
    return module


def snapshot_template_functions(module, template):
    if module.function_snapshots.exists():
        return
    function_links = list(
        template.function_links.filter(function__deleted_at__isnull=True)
        .select_related("function")
        .prefetch_related("function__forms__questions")
    )
    CaseFunctionSnapshot.objects.bulk_create([
        CaseFunctionSnapshot(
            module=module,
            title=link.function.title,
            kind=link.function.kind,
            position=link.position,
            definition={
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
                                "matrixDefinition": legacy_definition(
                                    question.rows, question.columns
                                ) if question.field_type == "matrix" else {},
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
        )
        for link in function_links
    ])


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
                "table", "thead", "tbody", "tr", "th", "td", "a", "blockquote"}

def clean_html(value):
    return nh3.clean(value, tags=ALLOWED_TAGS, attributes={"a": {"href"}}, url_schemes={"http", "https", "mailto"})
