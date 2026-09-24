from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AssignmentForm,
    CaseForm,
    LibraryFieldForm,
    LibraryTemplateForm,
    ModuleFieldForm,
    ModuleForm,
    PatientForm,
    ReviewForm,
)
from .models import (
    Assignment,
    AssignmentSubmission,
    Case,
    FieldDefinition,
    LibraryField,
    LibraryTemplate,
    Module,
    ModuleField,
    ModuleResponse,
    Profile,
    StudentCase,
)
from .services import audit, create_case_structure, module_schema, start_student_case


def user_role(user):
    if user.is_superuser or user.is_staff:
        return Profile.Role.ADMIN
    return getattr(getattr(user, "epd_profile", None), "role", Profile.Role.STUDENT)


def is_teacher(user):
    return user_role(user) in {Profile.Role.TEACHER, Profile.Role.ADMIN}


def is_admin(user):
    return user_role(user) == Profile.Role.ADMIN


def require_teacher(user):
    if not is_teacher(user):
        raise PermissionDenied


def teacher_cases(user):
    cases = Case.objects.select_related("patient", "created_by").prefetch_related(
        "modules__fields", "assignments", "student_cases__student"
    )
    return cases if is_admin(user) else cases.filter(created_by=user)


def editable_case(user, case_id):
    return get_object_or_404(teacher_cases(user), id=case_id)


def require_post(request):
    if request.method != "POST":
        raise PermissionDenied


def get_student_case(request, case_id):
    case = get_object_or_404(Case.objects.select_related("patient"), id=case_id)
    existing = StudentCase.objects.filter(case=case, student=request.user).first()
    if not existing and case.status != Case.Status.PUBLISHED:
        raise PermissionDenied
    student_case, created = start_student_case(case, request.user)
    if created:
        audit(request, "student_case.started", student_case, case_id=case.id)
    return case, student_case


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)


@login_required
def home(request):
    if is_teacher(request.user):
        return redirect("dossier:teacher_dashboard")
    cases = list(
        Case.objects.filter(
            Q(status=Case.Status.PUBLISHED) | Q(student_cases__student=request.user)
        )
        .select_related("patient")
        .prefetch_related("assignments")
        .distinct()
        .order_by("title")
    )
    instances = {
        item.case_id: item
        for item in StudentCase.objects.filter(student=request.user, case__in=cases).prefetch_related(
            "assignment_submissions"
        )
    }
    for case in cases:
        case.student_instance = instances.get(case.id)
        case.display_assignments = (
            list(case.student_instance.assignment_submissions.all())
            if case.student_instance else list(case.assignments.all())
        )
    return render(request, "dossier/home.html", {"cases": cases})


@login_required
def case_detail(request, case_id):
    if is_teacher(request.user):
        return redirect("dossier:teacher_case", case_id=case_id)
    case, student_case = get_student_case(request, case_id)
    assignments = list(student_case.assignment_submissions.all())
    selected_id = request.POST.get("assignment") or request.GET.get("assignment")
    selected = next((item for item in assignments if str(item.id) == selected_id), None)

    if request.method == "POST" and selected:
        if student_case.locked:
            messages.error(request, "Dit dossier is ingediend en kan niet meer worden gewijzigd.")
        else:
            selected.answer = request.POST.get("answer", "").strip()
            if request.POST.get("action") == "submit":
                if not selected.answer:
                    messages.error(request, "Vul eerst een antwoord in.")
                else:
                    selected.status = AssignmentSubmission.Status.SUBMITTED
                    selected.submitted_at = timezone.now()
                    messages.success(request, "Je opdracht is ingediend.")
            else:
                if selected.status == AssignmentSubmission.Status.RESUBMIT:
                    selected.status = AssignmentSubmission.Status.TODO
                messages.success(request, "Je antwoord is bewaard.")
            selected.save()
            audit(request, "assignment.updated", selected, status=selected.status)
        return redirect(f"{request.path}?assignment={selected.id}")

    selected_index = assignments.index(selected) if selected in assignments else None
    previous_assignment = (
        assignments[selected_index - 1]
        if selected_index is not None and selected_index > 0
        else None
    )
    next_assignment = (
        assignments[selected_index + 1]
        if selected_index is not None and selected_index < len(assignments) - 1
        else assignments[0] if selected is None and assignments else None
    )
    return render(request, "dossier/case_detail.html", {
        "case": case, "student_case": student_case, "assignments": assignments,
        "selected": selected, "submission": selected,
        "previous_assignment": previous_assignment, "next_assignment": next_assignment,
    })


def prepare_schema_fields(schema, data):
    prepared = []
    for field in schema:
        item = dict(field)
        key = item["key"]
        value = data.get(key, [] if item["type"] == "observation" else "")
        item["value"] = value
        if item["type"] == "matrix":
            matrix_values = value if isinstance(value, dict) else {}
            item["prepared_rows"] = [
                {
                    "label": row,
                    "cells": [
                        {
                            "name": f"field_{key}_{row_index}_{column_index}",
                            "value": matrix_values.get(f"{row_index}_{column_index}", ""),
                        }
                        for column_index, _ in enumerate(item.get("columns", []))
                    ],
                }
                for row_index, row in enumerate(item.get("rows", []))
            ]
        prepared.append(item)
    return prepared


def parsed_module_data(request, schema, current_data):
    data = dict(current_data)
    missing = []
    for field in schema:
        key = field["key"]
        field_type = field["type"]
        if field_type == FieldDefinition.FieldType.OBSERVATION:
            if field.get("required") and not data.get(key):
                missing.append(field["label"])
            continue
        if field_type == FieldDefinition.FieldType.MATRIX:
            value = {
                f"{row_index}_{column_index}": request.POST.get(
                    f"field_{key}_{row_index}_{column_index}", ""
                ).strip()
                for row_index, _ in enumerate(field.get("rows", []))
                for column_index, _ in enumerate(field.get("columns", []))
            }
            has_value = any(value.values())
        else:
            value = request.POST.get(f"field_{key}", "").strip()
            has_value = bool(value)
        if field.get("required") and not has_value:
            missing.append(field["label"])
        data[key] = value
    if missing:
        return None, missing
    return data, []


@login_required
def dossier(request, case_id):
    if is_teacher(request.user):
        return redirect("dossier:teacher_case", case_id=case_id)
    case, student_case = get_student_case(request, case_id)
    query = request.GET.get("q", "").strip()
    modules = list(student_case.module_responses.all())
    visible_modules = [item for item in modules if query.lower() in item.title.lower()] if query else modules
    selected_id = request.POST.get("module") or request.GET.get("module")
    selected = next((item for item in modules if str(item.id) == selected_id), None)
    if selected is None and modules:
        selected = modules[0]

    if request.method == "POST" and selected:
        if student_case.locked:
            messages.error(request, "Dit dossier is ingediend en kan niet meer worden gewijzigd.")
        elif request.POST.get("action", "").startswith("add_observation:"):
            key = request.POST["action"].split(":", 1)[1]
            valid_keys = {field["key"] for field in selected.schema if field["type"] == "observation"}
            if key in valid_keys:
                data = dict(selected.data)
                observations = list(data.get(key, []))
                observations.append({
                    "timestamp": request.POST.get(f"observation_timestamp_{key}", ""),
                    "value": request.POST.get(f"observation_value_{key}", "").strip(),
                    "note": request.POST.get(f"observation_note_{key}", "").strip(),
                })
                data[key] = observations
                selected.data = data
                selected.save(update_fields=["data", "updated_at"])
                messages.success(request, "Observatie toegevoegd.")
        else:
            data, missing = parsed_module_data(request, selected.schema, selected.data)
            if missing:
                messages.error(request, f"Vul de verplichte velden in: {', '.join(missing)}.")
            else:
                selected.data = data
                selected.save(update_fields=["data", "updated_at"])
                messages.success(request, "Dossieronderdeel bewaard.")
                audit(request, "module_response.updated", selected)
        return redirect(f"{request.path}?module={selected.id}")

    return render(request, "dossier/dossier.html", {
        "case": case, "student_case": student_case, "modules": visible_modules,
        "selected": selected, "query": query,
        "fields": prepare_schema_fields(selected.schema, selected.data) if selected else [],
    })


@login_required
def submit_student_case(request, case_id):
    require_post(request)
    if is_teacher(request.user):
        raise PermissionDenied
    _, student_case = get_student_case(request, case_id)
    incomplete = student_case.assignment_submissions.filter(
        status__in=[AssignmentSubmission.Status.TODO, AssignmentSubmission.Status.RESUBMIT]
    ).exists()
    if incomplete:
        messages.error(request, "Dien eerst alle opdrachten in.")
    else:
        student_case.status = StudentCase.Status.SUBMITTED
        student_case.submitted_at = timezone.now()
        student_case.save(update_fields=["status", "submitted_at", "updated_at"])
        audit(request, "student_case.submitted", student_case)
        messages.success(request, "Je volledige dossier is ingediend.")
    return redirect("dossier:case_detail", case_id=case_id)


@login_required
def teacher_dashboard(request):
    require_teacher(request.user)
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    cases = teacher_cases(request.user)
    if status in Case.Status.values:
        cases = cases.filter(status=status)
    if query:
        cases = cases.filter(Q(title__icontains=query) | Q(patient__name__icontains=query))
    counts = {key: teacher_cases(request.user).filter(status=key).count() for key in Case.Status.values}
    return render(request, "dossier/teacher_dashboard.html", {
        "cases": cases, "status_filter": status, "query": query, "counts": counts,
    })


@login_required
@transaction.atomic
def teacher_case_create(request):
    require_teacher(request.user)
    patient_form = PatientForm(request.POST or None, prefix="patient")
    case_form = CaseForm(request.POST or None, prefix="case")
    if request.method == "POST" and patient_form.is_valid() and case_form.is_valid():
        patient = patient_form.save(commit=False)
        patient.created_by = request.user
        patient.save()
        case = case_form.save(commit=False)
        case.patient = patient
        case.created_by = request.user
        case.save()
        create_case_structure(case)
        audit(request, "case.created", case)
        messages.success(request, "Patiënt en casus zijn aangemaakt.")
        return redirect("dossier:teacher_case", case_id=case.id)
    return render(request, "dossier/teacher_case_form.html", {
        "patient_form": patient_form, "case_form": case_form, "mode": "create",
    })


@login_required
@transaction.atomic
def teacher_case_edit(request, case_id):
    require_teacher(request.user)
    case = editable_case(request.user, case_id)
    patient_form = PatientForm(request.POST or None, instance=case.patient, prefix="patient")
    case_form = CaseForm(request.POST or None, instance=case, prefix="case")
    if request.method == "POST" and patient_form.is_valid() and case_form.is_valid():
        patient_form.save()
        case_form.save()
        audit(request, "case.updated", case)
        messages.success(request, "Casusgegevens bijgewerkt. Bestaande studentkopieën blijven ongewijzigd.")
        return redirect("dossier:teacher_case", case_id=case.id)
    return render(request, "dossier/teacher_case_form.html", {
        "patient_form": patient_form, "case_form": case_form,
        "mode": "edit", "case": case,
    })


@login_required
def teacher_case(request, case_id):
    require_teacher(request.user)
    case = editable_case(request.user, case_id)
    students = list(case.student_cases.select_related("student").all())
    return render(request, "dossier/teacher_case.html", {
        "case": case, "students": students,
        "assignment_form": AssignmentForm(prefix="assignment"),
    })


@login_required
def teacher_case_transition(request, case_id):
    require_teacher(request.user)
    require_post(request)
    case = editable_case(request.user, case_id)
    action = request.POST.get("action")
    if action == "publish":
        invalid_modules = [
            module for module in case.modules.prefetch_related("fields")
            if module.kind != Module.Kind.INFORMATION
            and not module.fields.exists()
            and not module.configuration
        ]
        if not case.assignments.exists() or not case.modules.exists() or invalid_modules:
            messages.error(request, "Voor publicatie zijn een opdracht en volledig geconfigureerde dossieronderdelen nodig.")
        else:
            case.publish()
            case.save()
            audit(request, "case.published", case)
            messages.success(request, "Casus gepubliceerd voor studenten.")
    elif action == "archive":
        case.archive()
        case.save()
        audit(request, "case.archived", case)
        messages.success(request, "Casus gearchiveerd. Bestaande studentkopieën blijven bewaard.")
    elif action == "draft":
        case.move_to_draft()
        case.save()
        audit(request, "case.moved_to_draft", case)
        messages.success(request, "Casus teruggezet naar concept.")
    else:
        raise PermissionDenied
    return redirect("dossier:teacher_case", case_id=case.id)


@login_required
def teacher_assignment(request, case_id, assignment_id=None):
    require_teacher(request.user)
    case = editable_case(request.user, case_id)
    assignment = get_object_or_404(case.assignments, id=assignment_id) if assignment_id else None
    form = AssignmentForm(request.POST or None, instance=assignment, prefix="assignment")
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.case = case
        item.save()
        audit(request, "assignment.updated" if assignment else "assignment.created", item)
        messages.success(request, "Opdracht bewaard.")
        return redirect("dossier:teacher_case", case_id=case.id)
    return render(request, "dossier/teacher_item_form.html", {
        "form": form, "case": case, "title": "Opdracht aanpassen" if assignment else "Opdracht toevoegen",
    })


@login_required
def teacher_assignment_delete(request, case_id, assignment_id):
    require_teacher(request.user)
    require_post(request)
    case = editable_case(request.user, case_id)
    assignment = get_object_or_404(case.assignments, id=assignment_id)
    audit(request, "assignment.deleted", assignment, title=assignment.title)
    assignment.delete()
    messages.success(request, "Opdracht verwijderd. Bestaande studentkopieën blijven bewaard.")
    return redirect("dossier:teacher_case", case_id=case.id)


@login_required
def teacher_module_create(request, case_id):
    require_teacher(request.user)
    if not is_admin(request.user):
        raise PermissionDenied
    case = editable_case(request.user, case_id)
    form = ModuleForm(request.POST or None, prefix="module")
    if request.method == "POST" and form.is_valid():
        module = form.save(commit=False)
        module.case = case
        module.save()
        audit(request, "module.created", module)
        messages.success(request, "Dossieronderdeel aangemaakt. Voeg nu de velden toe.")
        return redirect("dossier:teacher_module", case_id=case.id, module_id=module.id)
    return render(request, "dossier/teacher_item_form.html", {
        "form": form, "case": case, "title": "Dossieronderdeel toevoegen",
    })


@login_required
def teacher_module(request, case_id, module_id):
    require_teacher(request.user)
    case = editable_case(request.user, case_id)
    module = get_object_or_404(case.modules.prefetch_related("fields"), id=module_id)
    schema = module_schema(module)
    if request.method == "POST":
        if request.POST.get("action", "").startswith("add_observation:"):
            key = request.POST["action"].split(":", 1)[1]
            valid_keys = {field["key"] for field in schema if field["type"] == "observation"}
            if key not in valid_keys:
                raise PermissionDenied
            data = dict(module.base_data)
            observations = list(data.get(key, []))
            observations.append({
                "timestamp": request.POST.get(f"observation_timestamp_{key}", ""),
                "value": request.POST.get(f"observation_value_{key}", "").strip(),
                "note": request.POST.get(f"observation_note_{key}", "").strip(),
            })
            data[key] = observations
            module.base_data = data
            module.save(update_fields=["base_data"])
            audit(request, "base_dossier.observation_added", module)
            messages.success(request, "Observatie aan het basisdossier toegevoegd.")
        else:
            data, missing = parsed_module_data(request, schema, module.base_data)
            if missing:
                messages.error(request, f"Vul de verplichte velden in: {', '.join(missing)}.")
            else:
                module.base_data = data
                module.save(update_fields=["base_data"])
                audit(request, "base_dossier.updated", module)
                messages.success(request, "Basisdossier bijgewerkt. Nieuwe studenten starten met deze gegevens.")
        return redirect("dossier:teacher_module", case_id=case.id, module_id=module.id)
    return render(request, "dossier/teacher_base_module.html", {
        "case": case, "module": module,
        "fields": prepare_schema_fields(schema, module.base_data),
    })


@login_required
def teacher_module_field(request, case_id, module_id, field_id=None):
    require_teacher(request.user)
    if not is_admin(request.user):
        raise PermissionDenied
    case = editable_case(request.user, case_id)
    module = get_object_or_404(case.modules, id=module_id)
    field = get_object_or_404(module.fields, id=field_id) if field_id else None
    form = ModuleFieldForm(request.POST or None, instance=field, parent=module)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.module = module
        item.save()
        audit(request, "module_field.updated" if field else "module_field.created", item)
        messages.success(request, "Veld bewaard.")
        return redirect("dossier:teacher_module", case_id=case.id, module_id=module.id)
    return render(request, "dossier/teacher_item_form.html", {
        "form": form, "case": case, "module": module,
        "title": "Veld aanpassen" if field else "Veld toevoegen",
    })


@login_required
def teacher_module_field_delete(request, case_id, module_id, field_id):
    require_teacher(request.user)
    if not is_admin(request.user):
        raise PermissionDenied
    require_post(request)
    case = editable_case(request.user, case_id)
    module = get_object_or_404(case.modules, id=module_id)
    field = get_object_or_404(module.fields, id=field_id)
    audit(request, "module_field.deleted", field, label=field.label)
    field.delete()
    messages.success(request, "Veld verwijderd.")
    return redirect("dossier:teacher_module", case_id=case.id, module_id=module.id)


@login_required
def teacher_student_case(request, student_case_id):
    require_teacher(request.user)
    student_case = get_object_or_404(
        StudentCase.objects.select_related("case", "student").prefetch_related(
            "assignment_submissions", "module_responses"
        ), id=student_case_id
    )
    editable_case(request.user, student_case.case_id)
    for module in student_case.module_responses.all():
        module.display_values = [
            {"label": field["label"], "value": module.data.get(field["key"], "")}
            for field in module.schema
        ]
    return render(request, "dossier/teacher_student_case.html", {
        "student_case": student_case, "review_form": ReviewForm(),
    })


@login_required
def teacher_review_assignment(request, student_case_id, submission_id):
    require_teacher(request.user)
    require_post(request)
    student_case = get_object_or_404(StudentCase.objects.select_related("case"), id=student_case_id)
    editable_case(request.user, student_case.case_id)
    submission = get_object_or_404(student_case.assignment_submissions, id=submission_id)
    form = ReviewForm(request.POST)
    if form.is_valid():
        submission.status = form.cleaned_data["status"]
        submission.feedback = form.cleaned_data["feedback"]
        submission.reviewed_at = timezone.now()
        submission.save()
        if submission.status == AssignmentSubmission.Status.RESUBMIT:
            student_case.status = StudentCase.Status.ACTIVE
        elif not student_case.assignment_submissions.exclude(
            status=AssignmentSubmission.Status.APPROVED
        ).exists():
            student_case.status = StudentCase.Status.REVIEWED
            student_case.reviewed_at = timezone.now()
        student_case.save()
        audit(request, "assignment.reviewed", submission, status=submission.status)
        messages.success(request, "Beoordeling opgeslagen.")
    return redirect("dossier:teacher_student_case", student_case_id=student_case.id)


@login_required
def library_list(request):
    require_teacher(request.user)
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    education = request.GET.get("education", "").strip()
    theme = request.GET.get("theme", "").strip()
    templates = LibraryTemplate.objects.filter(status=LibraryTemplate.Status.ACTIVE).select_related("created_by")
    if query:
        templates = templates.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if category in LibraryTemplate.Category.values:
        templates = templates.filter(category=category)
    if education:
        templates = templates.filter(education__icontains=education)
    if theme:
        templates = templates.filter(theme__icontains=theme)
    return render(request, "dossier/library_list.html", {
        "templates": templates, "query": query, "category_filter": category,
        "education_filter": education, "theme_filter": theme,
        "categories": LibraryTemplate.Category.choices,
    })


@login_required
def library_template(request, template_id=None):
    require_teacher(request.user)
    if not template_id and not is_admin(request.user):
        raise PermissionDenied
    template = get_object_or_404(LibraryTemplate, id=template_id) if template_id else None
    form = LibraryTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and not is_admin(request.user):
        raise PermissionDenied
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        if not item.pk:
            item.created_by = request.user
        else:
            item.version += 1
        item.save()
        audit(request, "library.updated" if template else "library.created", item)
        messages.success(request, "Bibliotheektemplate bewaard. Bestaande casuskopieën blijven ongewijzigd.")
        return redirect("dossier:library_detail", template_id=item.id)
    if template:
        return render(request, "dossier/library_detail.html", {
            "template_item": template, "form": form, "can_manage": is_admin(request.user),
        })
    return render(request, "dossier/teacher_item_form.html", {
        "form": form, "title": "Nieuw bibliotheektemplate", "library_mode": True,
    })


@login_required
def library_field(request, template_id, field_id=None):
    require_teacher(request.user)
    if not is_admin(request.user):
        raise PermissionDenied
    template = get_object_or_404(LibraryTemplate, id=template_id)
    if not (is_admin(request.user) or template.created_by == request.user):
        raise PermissionDenied
    field = get_object_or_404(template.fields, id=field_id) if field_id else None
    form = LibraryFieldForm(request.POST or None, instance=field, parent=template)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.template = template
        item.save()
        template.version += 1
        template.save(update_fields=["version", "updated_at"])
        audit(request, "library_field.updated" if field else "library_field.created", item)
        messages.success(request, "Templateveld bewaard.")
        return redirect("dossier:library_detail", template_id=template.id)
    return render(request, "dossier/teacher_item_form.html", {
        "form": form, "title": "Templateveld aanpassen" if field else "Templateveld toevoegen",
        "library_item": template,
    })


@login_required
def library_archive(request, template_id):
    require_teacher(request.user)
    if not is_admin(request.user):
        raise PermissionDenied
    require_post(request)
    template = get_object_or_404(LibraryTemplate, id=template_id)
    if not (is_admin(request.user) or template.created_by == request.user):
        raise PermissionDenied
    template.status = LibraryTemplate.Status.ARCHIVED
    template.save(update_fields=["status", "updated_at"])
    audit(request, "library.archived", template)
    messages.success(request, "Bibliotheektemplate gearchiveerd.")
    return redirect("dossier:library_list")
