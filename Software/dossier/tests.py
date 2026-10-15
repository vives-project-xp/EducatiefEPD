import json
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.core.exceptions import SuspiciousOperation
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from .models import (
    Assignment,
    AssignmentSubmission,
    Case,
    Education,
    ExternalIdentity,
    LibraryDossier,
    LibraryField,
    LibraryTemplate,
    Patient,
    Profile,
    StudentCase,
    TeachingGroup,
)
from .auth import EpdOIDCAuthenticationBackend
from .services import create_case_structure, ensure_default_templates, start_student_case


@override_settings(SECURE_SSL_REDIRECT=False)
class EpdWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.education = Education.objects.get(slug="vroedkunde")
        cls.teacher = user_model.objects.create_user("teacher", password="testpass")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.education = cls.education
        cls.teacher.epd_profile.save()
        cls.student = user_model.objects.create_user("student", password="testpass")
        cls.other_student = user_model.objects.create_user("student2", password="testpass")
        for student in (cls.student, cls.other_student):
            student.epd_profile.education = cls.education
            student.epd_profile.save()
        cls.admin = user_model.objects.create_superuser("admin", password="testpass")
        cls.patient = Patient.objects.create(
            name="Test, Tessa", reference="TEST-001", created_by=cls.teacher
        )
        cls.case = Case.objects.create(
            title="Testcasus", patient=cls.patient, education=cls.education,
            course="Vroedkunde",
            introduction="Oorspronkelijke inleiding", created_by=cls.teacher,
        )
        cls.group = TeachingGroup.objects.create(
            name="Testgroep", education=cls.education, teacher=cls.teacher
        )
        cls.group.members.add(cls.student, cls.other_student)
        cls.case.allowed_groups.add(cls.group)
        create_case_structure(cls.case)
        cls.assignment = Assignment.objects.create(
            case=cls.case, phase="Opdracht 1", title="Observeer",
            content="Oorspronkelijke opdracht", position=1,
        )

    def test_login_is_required(self):
        response = self.client.get(reverse("dossier:home"))
        self.assertRedirects(
            response, f"{reverse('login')}?next=/", fetch_redirect_response=False
        )

    def test_oidc_failure_page_is_accessible_and_forbidden(self):
        response = self.client.get(reverse("login_failure"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Geen toegang tot het EPD", status_code=403)

    def test_health_endpoint_checks_database(self):
        response = self.client.get(reverse("dossier:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_student_cannot_open_teacher_dashboard(self):
        self.client.login(username="student", password="testpass")
        self.assertEqual(
            self.client.get(reverse("dossier:teacher_dashboard")).status_code, 403
        )

    def test_teacher_cannot_change_fixed_dossier_structure(self):
        self.client.login(username="teacher", password="testpass")
        response = self.client.get(reverse("dossier:teacher_module_create", args=[self.case.id]))
        self.assertEqual(response.status_code, 403)

    def test_new_case_receives_all_fixed_dossier_sections(self):
        self.assertEqual(
            self.case.modules.count(),
            LibraryTemplate.objects.filter(
                status=LibraryTemplate.Status.ACTIVE, is_fixed=True,
                education=self.education,
            ).count(),
        )
        self.assertTrue(self.case.modules.filter(title="Anamnese").exists())
        self.assertTrue(self.case.modules.filter(title="Klinisch redeneerplan").exists())

    def test_patient_can_have_only_one_case(self):
        with self.assertRaises(IntegrityError):
            Case.objects.create(
                title="Tweede casus", patient=self.patient, education=self.education,
                course="Vroedkunde",
                created_by=self.teacher,
            )

    def test_concept_case_is_not_available_to_new_student(self):
        self.client.login(username="student", password="testpass")
        response = self.client.get(reverse("dossier:case_detail", args=[self.case.id]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(StudentCase.objects.filter(student=self.student).exists())

    def test_student_copy_is_complete_and_immutable_from_source_changes(self):
        anamnese = self.case.modules.get(title="Anamnese")
        symptom_field = anamnese.fields.get(label="Huidige klachten en symptomen")
        anamnese.base_data = {symptom_field.key: "Hoofdpijn"}
        anamnese.save()
        self.case.publish()
        self.case.save()

        student_case, _ = start_student_case(self.case, self.student)
        copied_assignment = student_case.assignment_submissions.get()
        copied_anamnese = student_case.module_responses.get(title="Anamnese")

        self.case.introduction = "Gewijzigde inleiding"
        self.case.save()
        self.assignment.content = "Gewijzigde opdracht"
        self.assignment.save()
        anamnese.base_data = {symptom_field.key: "Buikpijn"}
        anamnese.save()

        student_case.refresh_from_db()
        copied_assignment.refresh_from_db()
        copied_anamnese.refresh_from_db()
        self.assertEqual(student_case.introduction, "Oorspronkelijke inleiding")
        self.assertEqual(copied_assignment.content, "Oorspronkelijke opdracht")
        self.assertEqual(copied_anamnese.data[symptom_field.key], "Hoofdpijn")

    def test_answers_are_isolated_per_student(self):
        self.case.publish()
        self.case.save()
        url = reverse("dossier:case_detail", args=[self.case.id])

        self.client.login(username="student", password="testpass")
        self.client.get(url)
        first = StudentCase.objects.get(case=self.case, student=self.student)
        first_submission = first.assignment_submissions.get()
        self.client.post(url, {
            "assignment": first_submission.id, "answer": "Antwoord student 1", "action": "save",
        })
        self.client.logout()

        self.client.login(username="student2", password="testpass")
        self.client.get(url)
        second = StudentCase.objects.get(case=self.case, student=self.other_student)
        second_submission = second.assignment_submissions.get()
        self.client.post(url, {
            "assignment": second_submission.id, "answer": "Antwoord student 2", "action": "submit",
        })

        first_submission.refresh_from_db()
        second_submission.refresh_from_db()
        self.assertEqual(first_submission.answer, "Antwoord student 1")
        self.assertEqual(first_submission.status, AssignmentSubmission.Status.TODO)
        self.assertEqual(second_submission.answer, "Antwoord student 2")
        self.assertEqual(second_submission.status, AssignmentSubmission.Status.SUBMITTED)

    def test_teacher_can_fill_patient_specific_base_dossier(self):
        self.client.login(username="teacher", password="testpass")
        module = self.case.modules.get(title="Anamnese")
        symptom_field = module.fields.get(label="Huidige klachten en symptomen")
        response = self.client.post(
            reverse("dossier:teacher_module", args=[self.case.id, module.id]),
            {f"field_{symptom_field.key}": "Misselijkheid en hoofdpijn", "action": "save"},
        )
        self.assertRedirects(
            response, reverse("dossier:teacher_module", args=[self.case.id, module.id])
        )
        module.refresh_from_db()
        self.assertEqual(module.base_data[symptom_field.key], "Misselijkheid en hoofdpijn")

    def test_case_lifecycle_publish_and_archive(self):
        self.client.login(username="teacher", password="testpass")
        transition = reverse("dossier:teacher_case_transition", args=[self.case.id])
        self.client.post(transition, {"action": "publish"})
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.PUBLISHED)
        self.assertIsNotNone(self.case.published_at)

        self.client.post(transition, {"action": "archive"})
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.ARCHIVED)
        self.assertIsNotNone(self.case.archived_at)

    def test_teacher_can_delete_archived_case_without_student_dossiers(self):
        self.client.force_login(self.teacher)
        self.case.archive()
        self.case.save()
        self.assertContains(
            self.client.get(reverse("dossier:teacher_case", args=[self.case.id])),
            "Casus verwijderen",
        )

        response = self.client.post(
            reverse("dossier:teacher_case_delete", args=[self.case.id])
        )
        self.assertRedirects(response, reverse("dossier:teacher_dashboard"))
        self.assertFalse(Case.objects.filter(id=self.case.id).exists())

    def test_only_teacher_can_delete_archived_case_and_student_data_is_preserved(self):
        student_case, _ = start_student_case(self.case, self.student)
        self.case.archive()
        self.case.save()
        delete_url = reverse("dossier:teacher_case_delete", args=[self.case.id])

        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.client.force_login(self.teacher)
        response = self.client.post(delete_url, follow=True)
        self.assertRedirects(
            response, reverse("dossier:teacher_case", args=[self.case.id])
        )
        self.assertContains(response, "studentendossiers aan gekoppeld")
        self.assertTrue(Case.objects.filter(id=self.case.id).exists())
        self.assertTrue(StudentCase.objects.filter(id=student_case.id).exists())

    def test_teacher_cannot_delete_case_that_is_not_archived(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("dossier:teacher_case_delete", args=[self.case.id])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Case.objects.filter(id=self.case.id).exists())

    def test_teacher_can_review_student_assignment(self):
        self.case.publish()
        self.case.save()
        student_case, _ = start_student_case(self.case, self.student)
        submission = student_case.assignment_submissions.get()
        submission.answer = "Ingevuld antwoord"
        submission.status = AssignmentSubmission.Status.SUBMITTED
        submission.save()

        self.client.login(username="teacher", password="testpass")
        response = self.client.post(
            reverse("dossier:teacher_review_assignment", args=[student_case.id, submission.id]),
            {"status": "approved", "feedback": "Correct en volledig."},
        )
        self.assertRedirects(
            response, reverse("dossier:teacher_student_case", args=[student_case.id])
        )
        submission.refresh_from_db()
        student_case.refresh_from_db()
        self.assertEqual(submission.status, AssignmentSubmission.Status.APPROVED)
        self.assertEqual(student_case.status, StudentCase.Status.REVIEWED)

    def test_teacher_can_create_patient_and_case_with_fixed_structure(self):
        self.client.login(username="teacher", password="testpass")
        response = self.client.post(reverse("dossier:teacher_case_create"), {
            "patient-name": "Voorbeeld, Vera", "patient-reference": "TEST-002",
            "patient-birth_date": "", "patient-gender": "female",
            "patient-image": "", "patient-context": "Andere symptomen",
            "case-title": "Nieuwe casus", "case-education": str(self.education.id),
            "case-course": "Zorgkunde",
            "case-introduction": "Inleiding", "case-learning_objectives": "Leerdoel",
        })
        created = Case.objects.get(patient__reference="TEST-002")
        self.assertRedirects(response, reverse("dossier:teacher_case", args=[created.id]))
        self.assertEqual(created.status, Case.Status.DRAFT)
        self.assertEqual(created.modules.count(), LibraryTemplate.objects.filter(is_fixed=True).count())

    def test_library_supports_search_and_filters(self):
        self.client.login(username="teacher", password="testpass")
        response = self.client.get(reverse("dossier:library_list"), {
            "q": "Anamnese", "education": "Vroedkunde", "theme": "Opname",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anamnese")
        self.assertNotContains(response, "Partusdossier")

    def test_teacher_and_student_core_pages_render(self):
        self.client.login(username="teacher", password="testpass")
        self.assertEqual(self.client.get(reverse("dossier:teacher_dashboard")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("dossier:teacher_case", args=[self.case.id])).status_code, 200
        )
        module = self.case.modules.get(title="Anamnese")
        self.assertEqual(
            self.client.get(
                reverse("dossier:teacher_module", args=[self.case.id, module.id])
            ).status_code,
            200,
        )
        self.client.logout()

        self.case.publish()
        self.case.save()
        self.client.login(username="student", password="testpass")
        self.assertEqual(self.client.get(reverse("dossier:home")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("dossier:case_detail", args=[self.case.id])).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("dossier:dossier", args=[self.case.id])).status_code, 200
        )

    def test_group_removal_revokes_existing_student_case_access(self):
        self.case.publish()
        self.case.save()
        self.client.login(username="student", password="testpass")
        case_url = reverse("dossier:case_detail", args=[self.case.id])
        self.assertEqual(self.client.get(case_url).status_code, 200)
        student_case = StudentCase.objects.get(student=self.student, case=self.case)
        self.group.members.remove(self.student)
        self.assertEqual(self.client.get(case_url).status_code, 403)
        self.assertEqual(self.client.get(reverse("dossier:dossier", args=[self.case.id])).status_code, 403)
        self.assertEqual(self.client.get(reverse("dossier:home")).status_code, 200)
        self.assertNotContains(self.client.get(reverse("dossier:home")), self.case.title)
        self.assertTrue(StudentCase.objects.filter(id=student_case.id).exists())

    def test_student_copy_does_not_gain_later_assignments_or_modules(self):
        self.case.publish()
        self.case.save()
        copy, _ = start_student_case(self.case, self.student)
        assignment_count = copy.assignment_submissions.count()
        module_count = copy.module_responses.count()
        Assignment.objects.create(case=self.case, phase="Later", title="Nieuw", position=99)
        template = LibraryTemplate.objects.create(
            title="Extra", category=LibraryTemplate.Category.MODULE,
            education=self.education, created_by=self.teacher,
        )
        from .services import copy_template_to_case
        copy_template_to_case(template, self.case)
        start_student_case(self.case, self.student)
        self.assertEqual(copy.assignment_submissions.count(), assignment_count)
        self.assertEqual(copy.module_responses.count(), module_count)
        newer, _ = start_student_case(self.case, self.other_student)
        self.assertEqual(newer.assignment_submissions.count(), assignment_count + 1)
        self.assertEqual(newer.module_responses.count(), module_count + 1)

    def test_teacher_can_manage_group_and_copy_own_template(self):
        self.client.login(username="teacher", password="testpass")
        group_response = self.client.get(reverse("dossier:group_detail", args=[self.group.id]))
        self.assertEqual(group_response.status_code, 200)
        response = self.client.post(reverse("dossier:library_create"), {
            "title": "Extra vragenlijst", "description": "Extra vragen",
            "category": LibraryTemplate.Category.QUESTIONNAIRE,
            "education": self.education.id, "theme": "Extra", "instructions": "Vul in",
        })
        template = LibraryTemplate.objects.get(title="Extra vragenlijst")
        self.assertRedirects(response, reverse("dossier:library_detail", args=[template.id]))
        self.assertFalse(template.is_fixed)
        add_url = reverse("dossier:teacher_case_add_template", args=[self.case.id])
        self.client.post(add_url, {"template_id": template.id})
        self.client.post(add_url, {"template_id": template.id})
        self.assertEqual(self.case.modules.filter(source_template=template).count(), 1)

    def test_teacher_can_edit_group_name_and_education(self):
        self.client.force_login(self.teacher)
        edit_url = reverse("dossier:group_edit", args=[self.group.id])
        page = self.client.get(edit_url)
        self.assertContains(page, "Groepsnaam")
        self.assertContains(page, "Opleiding")

        response = self.client.post(edit_url, {
            "name": "Aangepaste lesgroep",
            "education": self.education.id,
        })
        self.assertRedirects(response, reverse("dossier:group_detail", args=[self.group.id]))
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "Aangepaste lesgroep")
        self.assertEqual(self.group.teacher, self.teacher)

        other_education = Education.objects.create(name="Zorgkunde", slug="zorgkunde")
        response = self.client.post(edit_url, {
            "name": "Aangepaste lesgroep",
            "education": other_education.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "gekoppelde casussen")
        self.group.refresh_from_db()
        self.assertEqual(self.group.education, self.education)

    def test_teacher_can_delete_group_without_deleting_student_dossiers(self):
        student_case, _ = start_student_case(self.case, self.student)
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("dossier:group_delete", args=[self.group.id]))
        self.assertRedirects(response, reverse("dossier:group_list"))
        self.assertFalse(TeachingGroup.objects.filter(id=self.group.id).exists())
        self.assertFalse(self.case.allowed_groups.exists())
        self.assertTrue(StudentCase.objects.filter(id=student_case.id).exists())

    def test_admin_can_create_education_and_teacher_cannot(self):
        url = reverse("dossier:education_create")
        self.client.login(username="student", password="testpass")
        self.assertEqual(self.client.post(url, {"name": "Zorgkunde", "slug": "zorgkunde"}).status_code, 403)
        self.client.logout()
        self.client.login(username="admin", password="testpass")
        self.assertRedirects(
            self.client.post(url, {"name": "Zorgkunde", "slug": "zorgkunde"}),
            reverse("dossier:education_list"),
        )
        self.assertTrue(Education.objects.filter(slug="zorgkunde").exists())

    def test_admin_can_edit_and_delete_unused_education(self):
        self.client.force_login(self.admin)
        education = Education.objects.create(name="Testopleiding", slug="testopleiding")

        edit_url = reverse("dossier:education_edit", args=[education.id])
        response = self.client.post(edit_url, {
            "name": "Aangepaste opleiding",
            "slug": "aangepaste-opleiding",
        })
        self.assertRedirects(response, reverse("dossier:education_list"))
        education.refresh_from_db()
        self.assertEqual(education.name, "Aangepaste opleiding")

        list_page = self.client.get(reverse("dossier:education_list"))
        self.assertContains(list_page, "Aangepaste opleiding")
        self.assertContains(
            list_page,
            reverse("dossier:education_delete", args=[education.id]),
        )
        response = self.client.post(
            reverse("dossier:education_delete", args=[education.id])
        )
        self.assertRedirects(response, reverse("dossier:education_list"))
        self.assertFalse(Education.objects.filter(id=education.id).exists())

    def test_education_delete_requires_admin_and_preserves_linked_education(self):
        url = reverse("dossier:education_delete", args=[self.education.id])

        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.post(url, follow=True)
        self.assertRedirects(response, reverse("dossier:education_list"))
        self.assertContains(response, "kan niet worden verwijderd", status_code=200)
        self.assertTrue(Education.objects.filter(id=self.education.id).exists())

    def test_teacher_can_edit_fixed_library_template_without_teaching_group(self):
        self.group.delete()
        self.client.login(username="teacher", password="testpass")
        template = LibraryTemplate.objects.get(title="Anamnese")
        url = reverse("dossier:library_detail", args=[template.id])
        page = self.client.get(url)
        self.assertContains(page, "Nieuwe versie bewaren")
        self.assertContains(page, "Verwijderen")
        self.assertRedirects(self.client.post(url, {
            "title": "Anamnese aangepast", "description": "Aangepaste beschrijving",
            "category": template.category, "education": self.education.id,
            "theme": template.theme, "instructions": "Nieuwe instructies",
            "is_fixed": "",
        }), url)
        template.refresh_from_db()
        self.assertEqual(template.title, "Anamnese aangepast")
        self.assertEqual(template.version, 2)
        self.assertTrue(template.is_fixed)
        ensure_default_templates()
        self.assertFalse(LibraryTemplate.objects.filter(title="Anamnese").exists())
        self.assertEqual(self.case.modules.get(source_template=template).title, "Anamnese")

    def test_teacher_can_manage_fields_of_shared_library_template(self):
        self.client.login(username="teacher", password="testpass")
        template = LibraryTemplate.objects.create(
            title="Gedeelde module", category=LibraryTemplate.Category.MODULE,
            education=self.education, created_by=self.admin,
        )
        create_url = reverse("dossier:library_field_create", args=[template.id])
        detail_url = reverse("dossier:library_detail", args=[template.id])
        self.assertRedirects(self.client.post(create_url, {
            "label": "Zorgkeuze", "field_type": "select", "position": 1,
            "options_text": "Optie A\nOptie B", "rows_text": "", "columns_text": "",
        }), detail_url)
        field = template.fields.get()
        edit_url = reverse("dossier:library_field_edit", args=[template.id, field.id])
        self.assertRedirects(self.client.post(edit_url, {
            "label": "Zorgmatrix", "field_type": "matrix", "position": 2,
            "help_text": "Vul het plan in", "required": "on", "options_text": "",
            "rows_text": "Diagnose\nEvaluatie", "columns_text": "Omschrijving\nMotivatie",
        }), detail_url)
        field.refresh_from_db()
        self.assertEqual(field.label, "Zorgmatrix")
        self.assertEqual(field.rows, ["Diagnose", "Evaluatie"])
        self.assertEqual(field.columns, ["Omschrijving", "Motivatie"])
        self.assertTrue(field.required)
        delete_url = reverse("dossier:library_field_delete", args=[template.id, field.id])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        self.assertRedirects(self.client.post(delete_url), detail_url)
        self.assertFalse(LibraryField.objects.filter(id=field.id).exists())
        template.refresh_from_db()
        self.assertEqual(template.version, 4)

    def test_teacher_can_bundle_and_add_library_modules_as_a_dossier(self):
        self.client.force_login(self.teacher)
        existing_module = LibraryTemplate.objects.get(title="Anamnese", education=self.education)
        create_url = reverse("dossier:library_dossier_create")
        create_page = self.client.get(create_url)
        self.assertContains(create_page, "Anamnese")
        response = self.client.post(create_url, {
            "title": "Dossierbundel volledig", "description": "Bestaand onderdeel en nieuwe module",
            "education": self.education.id,
            "existing_modules": [str(existing_module.id)],
            "new_modules": json.dumps([
                {
                    "title": "Bundelmodule A",
                    "category": "module",
                    "description": "Nieuwe module met volledige velden",
                    "theme": "Opname",
                    "instructions": "Registreer de observatie.",
                    "fields": [
                        {
                            "label": "Observatie",
                            "type": "short_text",
                            "help_text": "Korte notitie",
                            "required": True,
                            "options": [],
                            "rows": [],
                            "columns": [],
                        },
                        {
                            "label": "Opvolging",
                            "type": "select",
                            "help_text": "",
                            "required": False,
                            "options": ["Controleren", "Afronden"],
                            "rows": [],
                            "columns": [],
                        },
                    ],
                },
            ]),
        })
        self.assertRedirects(response, reverse("dossier:library_list"))
        existing_module.refresh_from_db()
        self.assertEqual(existing_module.status, LibraryTemplate.Status.ACTIVE)
        self.assertTrue(LibraryTemplate.objects.filter(id=existing_module.id).exists())
        dossier = LibraryDossier.objects.get(title="Dossierbundel volledig")
        entries = list(dossier.module_entries.all())
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].template, existing_module)
        created_module = entries[1].template
        self.assertEqual(created_module.title, "Bundelmodule A")
        self.assertEqual(created_module.description, "Nieuwe module met volledige velden")
        self.assertEqual(created_module.theme, "Opname")
        self.assertEqual(created_module.instructions, "Registreer de observatie.")
        first_module = created_module
        self.assertEqual(first_module.category, LibraryTemplate.Category.MODULE)
        self.assertEqual(first_module.education, self.education)
        self.assertEqual(first_module.fields.count(), 2)
        self.assertTrue(first_module.fields.get(label="Observatie").required)
        self.assertEqual(
            first_module.fields.get(label="Opvolging").options,
            ["Controleren", "Afronden"],
        )

        list_response = self.client.get(reverse("dossier:library_list"))
        self.assertContains(list_response, "Dossierbundel volledig")
        self.assertContains(list_response, "Anamnese")
        self.assertContains(list_response, "Bundelmodule A")
        case_response = self.client.get(reverse("dossier:teacher_case", args=[self.case.id]))
        self.assertContains(case_response, "Dossierbundel volledig")

        add_url = reverse("dossier:teacher_case_add_dossier", args=[self.case.id])
        response = self.client.post(add_url, {"dossier_id": dossier.id})
        self.assertRedirects(response, reverse("dossier:teacher_case", args=[self.case.id]))
        copied = list(self.case.modules.filter(source_template__in=[existing_module, first_module]))
        self.assertEqual([module.source_template for module in copied], [existing_module, first_module])
        copied_new_module = next(module for module in copied if module.source_template == first_module)
        self.assertEqual(copied_new_module.fields.count(), 2)
        self.assertTrue(copied_new_module.fields.filter(label="Observatie").exists())

        copy_response = self.client.post(
            reverse("dossier:library_dossier_copy", args=[dossier.id])
        )
        self.assertRedirects(copy_response, reverse("dossier:library_list"))
        duplicate = LibraryDossier.objects.get(title=f"Kopie van {dossier.title}")
        self.assertEqual(
            list(duplicate.module_entries.values_list("template_id", flat=True)),
            [existing_module.id, first_module.id],
        )
        library_page = self.client.get(reverse("dossier:library_list"))
        visible_dossier_ids = [
            item.id for item in library_page.context["dossiers"]
        ]
        original_index = visible_dossier_ids.index(dossier.id)
        self.assertEqual(
            visible_dossier_ids[original_index - 1],
            duplicate.id,
        )

        archive_response = self.client.post(
            reverse("dossier:library_dossier_archive", args=[dossier.id])
        )
        self.assertRedirects(archive_response, reverse("dossier:library_list"))
        dossier.refresh_from_db()
        self.assertEqual(dossier.status, LibraryDossier.Status.ARCHIVED)
        self.assertTrue(self.case.modules.filter(source_template=first_module).exists())

    def test_multiple_library_dossiers_can_be_opened_independently(self):
        self.client.force_login(self.teacher)
        for title in ("Dossier een", "Dossier twee"):
            self.client.post(reverse("dossier:library_dossier_create"), {
                "title": title, "description": "", "education": self.education.id,
                "new_modules": json.dumps([{
                    "title": f"Module {title}",
                    "category": "module",
                    "fields": [],
                }]),
            })
        self.assertEqual(LibraryDossier.objects.count(), 2)
        self.assertEqual(LibraryTemplate.objects.filter(title__startswith="Module Dossier").count(), 2)
        page = self.client.get(reverse("dossier:library_list"))
        self.assertContains(page, "Dossier een")
        self.assertContains(page, "Dossier twee")
        self.assertNotContains(page, "Open om de modules te bekijken")
        self.assertEqual(
            [item.title for item in page.context["dossiers"]],
            ["Dossier twee", "Dossier een"],
        )
        filtered_page = self.client.get(
            reverse("dossier:library_list"), {"dossier_q": "Dossier een"}
        )
        self.assertContains(filtered_page, "Dossier een")
        self.assertNotContains(filtered_page, "Dossier twee")
        substring_page = self.client.get(
            reverse("dossier:library_list"), {"dossier_q": "ossier een"}
        )
        self.assertNotContains(substring_page, "Dossier een")
        education_filtered_page = self.client.get(
            reverse("dossier:library_list"),
            {"dossier_education": str(self.education.id)},
        )
        self.assertContains(education_filtered_page, "Dossier een")
        self.assertContains(education_filtered_page, "Dossier twee")

    def test_library_dashboard_hides_loose_templates_but_dossier_form_keeps_them_available(self):
        self.client.force_login(self.teacher)
        dashboard = self.client.get(reverse("dossier:library_list"))
        self.assertNotContains(dashboard, "Bibliotheekonderdelen")
        self.assertContains(dashboard, "Beschikbare onderdelen beheren")
        self.assertContains(
            dashboard, '<details class="library-component-management-details">',
            html=True,
        )
        self.assertNotContains(
            dashboard,
            '<details class="library-component-management-details" open>',
            html=True,
        )
        anamnese = LibraryTemplate.objects.get(title="Anamnese")
        self.assertContains(dashboard, anamnese.title)
        self.assertContains(
            dashboard, reverse("dossier:library_detail", args=[anamnese.id])
        )
        self.assertContains(
            dashboard, reverse("dossier:library_archive", args=[anamnese.id])
        )
        self.assertContains(dashboard, "Onderdeel toevoegen")

        for title in ("Anamnese", "Klinisch redeneerplan"):
            template = LibraryTemplate.objects.get(
                title=title,
                education=self.education,
                status=LibraryTemplate.Status.ACTIVE,
                is_fixed=True,
            )
            self.assertTrue(LibraryTemplate.objects.filter(pk=template.pk).exists())

        dossier_form = self.client.get(reverse("dossier:library_dossier_create"))
        self.assertContains(dossier_form, "Anamnese")
        self.assertContains(dossier_form, "Klinisch redeneerplan")

    def test_archived_standard_template_is_available_when_creating_a_dossier(self):
        self.client.force_login(self.teacher)
        template = LibraryTemplate.objects.get(
            title="Anamnese", education=self.education, is_fixed=True
        )
        template.status = LibraryTemplate.Status.ARCHIVED
        template.save(update_fields=["status", "updated_at"])

        create_url = reverse("dossier:library_dossier_create")
        dossier_form = self.client.get(create_url)
        self.assertContains(dossier_form, "Anamnese")

        response = self.client.post(create_url, {
            "title": "Dossier met standaardonderdeel",
            "description": "",
            "education": self.education.id,
            "existing_modules": [str(template.id)],
            "new_modules": "[]",
        })
        self.assertRedirects(response, reverse("dossier:library_list"))
        template.refresh_from_db()
        self.assertEqual(template.status, LibraryTemplate.Status.ACTIVE)
        self.assertTrue(
            LibraryDossier.objects.get(title="Dossier met standaardonderdeel")
            .modules.filter(pk=template.pk).exists()
        )

    def test_dossier_form_shows_and_accepts_modules_from_other_educations(self):
        self.client.force_login(self.teacher)
        other_education = Education.objects.create(
            name="Verpleegkunde", slug="verpleegkunde"
        )
        template = LibraryTemplate.objects.create(
            title="Verpleegkundig onderdeel",
            description="",
            category=LibraryTemplate.Category.MODULE,
            education=other_education,
        )
        create_url = reverse("dossier:library_dossier_create")
        form_page = self.client.get(create_url)
        self.assertContains(form_page, "Verpleegkundig onderdeel")

        response = self.client.post(create_url, {
            "title": "Vroedkundig dossier met ander onderdeel",
            "description": "",
            "education": self.education.id,
            "existing_modules": [str(template.id)],
            "new_modules": "[]",
        })
        self.assertRedirects(response, reverse("dossier:library_list"))
        dossier = LibraryDossier.objects.get(
            title="Vroedkundig dossier met ander onderdeel"
        )
        self.assertTrue(dossier.modules.filter(pk=template.pk).exists())

    def test_dossier_form_accepts_multiple_existing_modules(self):
        self.client.force_login(self.teacher)
        modules = list(LibraryTemplate.objects.filter(
            title__in=["Anamnese", "Klinisch redeneerplan"],
            education=self.education,
            status=LibraryTemplate.Status.ACTIVE,
        ))
        self.assertEqual(len(modules), 2)

        create_url = reverse("dossier:library_dossier_create")
        form_page = self.client.get(create_url)
        self.assertGreaterEqual(
            form_page.content.count(b'type="checkbox" name="existing_modules"'),
            2,
        )
        response = self.client.post(create_url, {
            "title": "Dossier met meerdere bestaande onderdelen",
            "description": "",
            "education": self.education.id,
            "existing_modules": [str(module.id) for module in modules],
            "new_modules": "[]",
        })
        self.assertRedirects(response, reverse("dossier:library_list"))
        dossier = LibraryDossier.objects.get(
            title="Dossier met meerdere bestaande onderdelen"
        )
        self.assertEqual(
            set(dossier.modules.values_list("id", flat=True)),
            {module.id for module in modules},
        )

    def test_invalid_library_choice_field_shows_validation_errors(self):
        self.client.login(username="teacher", password="testpass")
        template = LibraryTemplate.objects.get(title="Anamnese")
        response = self.client.post(reverse("dossier:library_field_create", args=[template.id]), {
            "label": "Keuze", "field_type": "select", "position": 1,
            "options_text": "", "rows_text": "", "columns_text": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["options_text"])
        self.assertFalse(template.fields.filter(label="Keuze").exists())

    def test_deleted_last_default_field_stays_deleted_and_copies_are_preserved(self):
        self.client.login(username="teacher", password="testpass")
        template = LibraryTemplate.objects.get(title="Uitwerking opdracht")
        field = template.fields.get()
        module = self.case.modules.get(source_template=template)
        original_kind = module.kind
        student_case, _ = start_student_case(self.case, self.student)
        snapshot = student_case.module_responses.get(module=module)
        original_schema = snapshot.schema
        self.client.post(reverse("dossier:library_field_delete", args=[template.id, field.id]))
        create_case_structure(self.case)
        self.assertFalse(template.fields.exists())
        module.refresh_from_db()
        snapshot.refresh_from_db()
        self.assertEqual(module.kind, original_kind)
        self.assertEqual(module.fields.count(), 1)
        self.assertEqual(snapshot.schema, original_schema)

    def test_teacher_can_remove_fixed_template_without_deleting_existing_dossiers(self):
        self.client.login(username="teacher", password="testpass")
        template = LibraryTemplate.objects.get(title="Anamnese")
        student_case, _ = start_student_case(self.case, self.student)
        url = reverse("dossier:library_archive", args=[template.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("dossier:library_list"))
        template.refresh_from_db()
        self.assertEqual(template.status, LibraryTemplate.Status.ARCHIVED)
        self.assertNotContains(self.client.get(reverse("dossier:library_list")), "Anamnese")
        self.assertEqual(self.client.get(reverse("dossier:library_detail", args=[template.id])).status_code, 404)
        ensure_default_templates()
        self.assertEqual(LibraryTemplate.objects.filter(title="Anamnese").count(), 1)
        patient = Patient.objects.create(name="Nieuw", reference="AFTER-DELETE")
        new_case = Case.objects.create(
            title="Nieuwe casus", patient=patient, education=self.education, course="Vroedkunde",
        )
        create_case_structure(new_case)
        self.assertFalse(new_case.modules.filter(source_template=template).exists())
        self.assertTrue(self.case.modules.filter(source_template=template).exists())
        self.assertTrue(student_case.module_responses.filter(title="Anamnese").exists())

    def test_student_cannot_manage_library_via_direct_requests(self):
        self.client.login(username="student", password="testpass")
        template = LibraryTemplate.objects.get(title="Anamnese")
        field = template.fields.first()
        targets = [
            ("library_list", []), ("library_create", []),
            ("library_detail", [template.id]), ("library_archive", [template.id]),
            ("library_field_create", [template.id]),
            ("library_field_edit", [template.id, field.id]),
            ("library_field_delete", [template.id, field.id]),
        ]
        for name, args in targets:
            with self.subTest(view=name):
                self.assertEqual(self.client.post(reverse(f"dossier:{name}", args=args)).status_code, 403)
        template.refresh_from_db()
        self.assertEqual(template.status, LibraryTemplate.Status.ACTIVE)
        self.assertTrue(template.fields.filter(id=field.id).exists())

    def test_library_field_delete_cannot_target_another_template(self):
        self.client.login(username="teacher", password="testpass")
        template = LibraryTemplate.objects.get(title="Anamnese")
        other_field = LibraryTemplate.objects.get(title="Partusdossier").fields.first()
        response = self.client.post(reverse("dossier:library_field_delete", args=[template.id, other_field.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(LibraryField.objects.filter(id=other_field.id).exists())

    def test_invalid_numeric_value_is_rejected(self):
        self.case.publish()
        self.case.save()
        student_case, _ = start_student_case(self.case, self.student)
        response = student_case.module_responses.get(title="Zwangerschapsdossier")
        field = next(item for item in response.schema if item["type"] == "number")
        self.client.login(username="student", password="testpass")
        self.client.post(reverse("dossier:dossier", args=[self.case.id]), {
            "module": response.id, f"field_{field['key']}": "geen getal",
        })
        response.refresh_from_db()
        self.assertNotIn(field["key"], response.data)

    @override_settings(EMERGENCY_LOGIN_ENABLED=True)
    def test_emergency_login_accepts_only_local_superuser(self):
        url = reverse("emergency_login")
        self.assertEqual(
            self.client.post(url, {"username": "student", "password": "testpass"}).status_code,
            200,
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post(url, {"username": "admin", "password": "testpass"})
        self.assertRedirects(response, reverse("dossier:home"), fetch_redirect_response=False)

    def test_emergency_login_is_disabled_by_default(self):
        self.assertEqual(self.client.get(reverse("emergency_login")).status_code, 404)
        self.assertEqual(self.client.get("/admin/login/").status_code, 404)


@override_settings(
    OIDC_ISSUER="https://auth.example.test/application/o/epd/",
    OIDC_RP_CLIENT_ID="epd", OIDC_RP_CLIENT_SECRET="test-secret",
    OIDC_OP_TOKEN_ENDPOINT="https://auth.example.test/token/",
    OIDC_OP_USER_ENDPOINT="https://auth.example.test/userinfo/",
    OIDC_OP_JWKS_ENDPOINT="https://auth.example.test/jwks/",
    OIDC_RP_SIGN_ALGO="RS256", OIDC_RP_SCOPES="openid email profile",
    OIDC_GROUP_CLAIM="groups", OIDC_STUDENT_GROUPS=["epd-studenten"],
    OIDC_TEACHER_GROUPS=["epd-docenten"], OIDC_ADMIN_GROUPS=["epd-beheerders"],
)
class OidcIdentityTests(TestCase):
    def setUp(self):
        self.backend = EpdOIDCAuthenticationBackend()
        self.issuer = "https://auth.example.test/application/o/epd/"

    def login_as(self, subject, groups, email="shared@example.test"):
        claims = {"sub": subject, "email": email, "groups": groups, "given_name": "Test"}
        with patch.object(self.backend, "get_userinfo", return_value=claims):
            return self.backend.get_or_create_user("access", "id", {"iss": self.issuer, "sub": subject})

    def test_same_email_different_subject_creates_separate_users(self):
        first = self.login_as("student-1", ["epd-studenten"])
        second = self.login_as("student-2", ["epd-studenten"])
        self.assertNotEqual(first.id, second.id)
        self.assertFalse(first.has_usable_password())
        self.assertEqual(ExternalIdentity.objects.count(), 2)

    def test_second_issuer_does_not_reuse_existing_local_identity(self):
        first = self.login_as("shared-subject", ["epd-studenten"])
        self.issuer = "https://second.example.test/application/o/epd/"
        with override_settings(OIDC_ISSUER=self.issuer):
            second = self.login_as("shared-subject", ["epd-studenten"])
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(ExternalIdentity.objects.count(), 2)

    def test_role_downgrade_removes_epd_admin_access(self):
        user = self.login_as("person-1", ["epd-beheerders"])
        self.assertEqual(user.epd_profile.role, Profile.Role.ADMIN)
        self.assertFalse(user.is_staff)
        self.login_as("person-1", ["epd-studenten"])
        user.refresh_from_db()
        user.epd_profile.refresh_from_db()
        self.assertEqual(user.epd_profile.role, Profile.Role.STUDENT)
        self.assertFalse(user.is_staff)

    def test_missing_role_and_wrong_issuer_are_denied(self):
        with self.assertRaises(SuspiciousOperation):
            self.login_as("person-1", [])
        with self.assertRaises(SuspiciousOperation):
            self.backend.get_or_create_user("access", "id", {"iss": "https://wrong.test/", "sub": "1"})
        self.assertFalse(ExternalIdentity.objects.exists())
