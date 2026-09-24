from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Assignment,
    AssignmentSubmission,
    Case,
    LibraryTemplate,
    Patient,
    Profile,
    StudentCase,
)
from .services import create_case_structure, start_student_case


@override_settings(SECURE_SSL_REDIRECT=False)
class EpdWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.teacher = user_model.objects.create_user("teacher", password="testpass")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.save()
        cls.student = user_model.objects.create_user("student", password="testpass")
        cls.other_student = user_model.objects.create_user("student2", password="testpass")
        cls.admin = user_model.objects.create_superuser("admin", password="testpass")
        cls.patient = Patient.objects.create(
            name="Test, Tessa", reference="TEST-001", created_by=cls.teacher
        )
        cls.case = Case.objects.create(
            title="Testcasus", patient=cls.patient, course="Vroedkunde",
            introduction="Oorspronkelijke inleiding", created_by=cls.teacher,
        )
        create_case_structure(cls.case)
        cls.assignment = Assignment.objects.create(
            case=cls.case, phase="Opdracht 1", title="Observeer",
            content="Oorspronkelijke opdracht", position=1,
        )

    def test_login_is_required(self):
        response = self.client.get(reverse("dossier:home"))
        self.assertRedirects(response, f"{reverse('login')}?next=/")

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
            LibraryTemplate.objects.filter(status=LibraryTemplate.Status.ACTIVE, is_fixed=True).count(),
        )
        self.assertTrue(self.case.modules.filter(title="Anamnese").exists())
        self.assertTrue(self.case.modules.filter(title="Klinisch redeneerplan").exists())

    def test_patient_can_have_only_one_case(self):
        with self.assertRaises(IntegrityError):
            Case.objects.create(
                title="Tweede casus", patient=self.patient, course="Vroedkunde",
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
            "case-title": "Nieuwe casus", "case-course": "Zorgkunde",
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
