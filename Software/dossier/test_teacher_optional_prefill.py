from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Assignment, AuditEvent, Case, Education, Module, ModuleField, Patient,
    Profile, TeachingGroup,
)
from .services import start_student_case


@override_settings(SECURE_SSL_REDIRECT=False)
class TeacherOptionalPrefillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.education = Education.objects.get(slug="vroedkunde")
        cls.teacher = get_user_model().objects.create_user("optional-teacher")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.save()
        cls.admin = get_user_model().objects.create_superuser("optional-admin", password="test-only")
        cls.student = get_user_model().objects.create_user("optional-student")
        cls.case = Case.objects.create(
            title="Optionele voorinvulling", education=cls.education, created_by=cls.teacher,
            patient=Patient.objects.create(name="Fictief", reference="OPTIONAL-PREFILL"),
        )
        cls.module = Module.objects.create(case=cls.case, title="Lege module")
        for position, field_type in enumerate((
            "short_text", "long_text", "rich_text", "number", "date", "datetime",
            "select", "matrix", "observation",
        )):
            ModuleField.objects.create(
                module=cls.module, key=field_type, label=field_type, field_type=field_type,
                required=True, position=position,
                options=["Ja", "Nee"] if field_type == "select" else [],
                rows=["Rij"] if field_type == "matrix" else [],
                columns=["Kolom"] if field_type == "matrix" else [],
            )
        Assignment.objects.create(case=cls.case, title="Opdracht", phase="Eerste")
        group = TeachingGroup.objects.create(
            name="Testgroep", education=cls.education, teacher=cls.teacher
        )
        group.members.add(cls.student)
        cls.case.allowed_groups.add(group)

    def setUp(self):
        self.client.force_login(self.teacher)
        self.publish_url = reverse("dossier:teacher_case_transition", args=[self.case.pk])
        self.module_url = reverse("dossier:teacher_module", args=[self.case.pk, self.module.pk])

    def test_publish_accepts_unfilled_required_fields(self):
        response = self.client.post(self.publish_url, {"action": "publish"}, follow=True)
        self.assertContains(response, "Casus gepubliceerd voor studenten.")
        self.case.refresh_from_db()
        self.module.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.PUBLISHED)
        self.assertEqual(self.module.base_data, {})
        self.assertTrue(all(self.module.fields.values_list("required", flat=True)))
        self.assertEqual(AuditEvent.objects.filter(action="case.published", target_id=str(self.case.pk)).count(), 1)

    def test_publish_accepts_unconfigured_empty_module(self):
        empty = Module.objects.create(case=self.case, title="Later in te vullen", kind=Module.Kind.FORM)
        self.assertFalse(empty.fields.exists())
        self.assertEqual(empty.configuration, {})
        response = self.client.post(self.publish_url, {"action": "publish"}, follow=True)
        self.assertContains(response, "Casus gepubliceerd voor studenten.")
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.Status.PUBLISHED)
        self.assertTrue(self.case.modules.filter(pk=empty.pk).exists())

    def test_missing_assignment_or_module_has_accurate_message_and_stays_draft(self):
        for has_assignment, has_module in ((False, True), (True, False), (False, False)):
            with self.subTest(assignment=has_assignment, module=has_module):
                case = Case.objects.create(
                    title="Onvolledige structuur", education=self.education, created_by=self.teacher,
                    patient=Patient.objects.create(name="Fictief", reference=f"MISSING-{has_assignment}-{has_module}"),
                )
                if has_assignment:
                    Assignment.objects.create(case=case, title="Opdracht", phase="Eerste")
                if has_module:
                    Module.objects.create(case=case, title="Module")
                response = self.client.post(
                    reverse("dossier:teacher_case_transition", args=[case.pk]),
                    {"action": "publish"}, follow=True,
                )
                if not has_assignment:
                    self.assertContains(response, "Voeg minstens één opdracht toe voordat je de casus publiceert.")
                if not has_module:
                    self.assertContains(response, "Voeg minstens één dossiermodule toe voordat je de casus publiceert.")
                self.assertNotContains(response, "volledig geconfigureerde dossieronderdelen")
                case.refresh_from_db()
                self.assertEqual(case.status, Case.Status.DRAFT)
                self.assertIsNone(case.published_at)
                self.assertFalse(AuditEvent.objects.filter(action="case.published", target_id=str(case.pk)).exists())

    def test_teacher_and_admin_can_save_all_required_fields_empty(self):
        for user in (self.teacher, self.admin):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post(self.module_url, {"action": "save"}, follow=True)
                self.assertContains(response, "Basisdossier bijgewerkt.")
                self.assertContains(response, "Voorinvullen is optioneel.")
                self.module.refresh_from_db()
                for key in ("short_text", "long_text", "rich_text", "number", "date", "datetime", "select"):
                    self.assertEqual(self.module.base_data[key], "")
                self.assertEqual(self.module.base_data["matrix"], {"0_0": ""})
                self.assertEqual(self.module.base_data.get("observation", []), [])

    def test_partial_prefill_accepts_zero_and_preserves_required_schema(self):
        response = self.client.post(self.module_url, {
            "action": "save", "field_number": "0", "field_short_text": "Gedeeltelijk ingevuld",
        }, follow=True)
        self.assertContains(response, "Basisdossier bijgewerkt.")
        self.module.refresh_from_db()
        self.assertEqual(self.module.base_data["number"], "0")
        self.assertEqual(self.module.base_data["short_text"], "Gedeeltelijk ingevuld")
        self.assertTrue(all(self.module.fields.values_list("required", flat=True)))

    def test_invalid_nonempty_prefill_is_rejected_without_partial_save(self):
        original = {"number": "5", "short_text": "Bestaand"}
        self.module.base_data = original
        self.module.save(update_fields=["base_data"])
        for key, value in (
            ("number", "ongeldig"), ("number", "NaN"), ("number", "Infinity"),
            ("date", "2026-02-30"), ("datetime", "geen tijdstip"), ("select", "Niet toegestaan"),
        ):
            with self.subTest(field=key, value=value):
                response = self.client.post(self.module_url, {
                    "action": "save", f"field_{key}": value, "field_short_text": "Niet bewaren",
                }, follow=True)
                self.assertContains(response, "Controleer deze velden:")
                self.module.refresh_from_db()
                self.assertEqual(self.module.base_data, original)
        self.assertFalse(AuditEvent.objects.filter(action="base_dossier.updated").exists())

    def test_student_required_validation_and_teacher_access_rule_are_preserved(self):
        self.case.publish()
        self.case.save()
        student_case, _ = start_student_case(self.case, self.student)
        module_response = student_case.module_responses.get(module=self.module)
        self.client.force_login(self.student)
        response = self.client.post(reverse("dossier:dossier", args=[self.case.pk]), {
            "action": "save", "module": module_response.pk,
        }, follow=True)
        self.assertContains(response, "Controleer deze velden:")
        module_response.refresh_from_db()
        self.assertEqual(module_response.data, {})
        self.assertTrue(all(field["required"] for field in module_response.schema))
        self.assertFalse(AuditEvent.objects.filter(action="module_response.updated").exists())
        self.assertEqual(self.client.post(self.module_url, {"action": "save"}).status_code, 403)

    def test_explicit_invalid_observation_still_requires_time_and_value(self):
        response = self.client.post(self.module_url, {
            "action": "add_observation:observation", "observation_value_observation": "Observatie",
            "observation_timestamp_observation": "ongeldig",
        }, follow=True)
        self.assertContains(response, "Geef een geldig tijdstip en een observatie op.")
        self.module.refresh_from_db()
        self.assertEqual(self.module.base_data, {})
