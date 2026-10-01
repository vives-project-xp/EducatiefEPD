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
    LibraryTemplate,
    Patient,
    Profile,
    StudentCase,
    TeachingGroup,
)
from .auth import EpdOIDCAuthenticationBackend
from .services import create_case_structure, start_student_case


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
