from copy import deepcopy
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Assignment, Case, Education, LibraryDossier, LibraryDossierModule, LibraryField,
    LibraryTemplate, Patient, Profile, TeachingGroup,
)
from .services import copy_library_dossier_to_case, start_student_case


@override_settings(SECURE_SSL_REDIRECT=False)
class DynamicCaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.education = Education.objects.get(slug="vroedkunde")
        cls.teacher = get_user_model().objects.create_user("dynamic-teacher")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.education = cls.education
        cls.teacher.epd_profile.save()
        cls.group = TeachingGroup.objects.create(
            name="Dynamische lesgroep", education=cls.education, teacher=cls.teacher
        )

    def setUp(self):
        self.client.force_login(self.teacher)

    def new_case(self, reference="DYNAMIC"):
        return Case.objects.create(
            title="Dynamische casus", education=self.education, course="Zorg",
            patient=Patient.objects.create(name="Fictief", reference=reference),
            created_by=self.teacher,
        )

    def new_bundle(self):
        dossier = LibraryDossier.objects.create(title="Gekozen dossier", education=self.education)
        templates = []
        for position, title in enumerate(("Intake", "Evaluatie")):
            template = LibraryTemplate.objects.create(
                title=title, education=self.education, category="questionnaire"
            )
            LibraryField.objects.create(template=template, key="notitie", label="Notitie", field_type="long_text")
            LibraryDossierModule.objects.create(dossier=dossier, template=template, position=position)
            templates.append(template)
        return dossier, templates

    def test_new_patient_and_case_start_without_modules_despite_existing_library(self):
        LibraryTemplate.objects.create(
            title="Oud standaardonderdeel", category="module", education=self.education,
            seed_key="vroedkunde-anamnese",
        )
        response = self.client.post(reverse("dossier:teacher_case_create"), {
            "patient-name": "Fictieve patiënt", "patient-reference": "DYNAMIC-POST",
            "patient-gender": "unknown", "case-title": "Nieuwe casus",
            "case-education": self.education.pk, "case-course": "Zorg",
        })
        case = Case.objects.get(patient__reference="DYNAMIC-POST")
        self.assertRedirects(response, reverse("dossier:teacher_case", args=[case.pk]))
        self.assertFalse(case.modules.exists())
        self.assertEqual(LibraryTemplate.objects.count(), 1)
        page = self.client.get(reverse("dossier:teacher_case", args=[case.pk]))
        self.assertContains(page, "Nog geen dossiermodules")
        self.assertNotContains(page, "vaste dossierstructuur")

    def test_selected_bundle_copies_exactly_its_active_modules_in_order_once(self):
        dossier, templates = self.new_bundle()
        LibraryTemplate.objects.create(title="Niet gekozen", category="module", education=self.education)
        archived = LibraryTemplate.objects.create(title="Gearchiveerd", category="module", status="archived")
        LibraryDossierModule.objects.create(dossier=dossier, template=archived, position=2)
        case = self.new_case()
        url = reverse("dossier:teacher_case_add_dossier", args=[case.pk])
        for _ in range(2):
            self.assertRedirects(self.client.post(url, {"dossier_id": dossier.pk}),
                                 reverse("dossier:teacher_case", args=[case.pk]))
        self.assertEqual(list(case.modules.values_list("source_template_id", flat=True)),
                         [template.pk for template in templates])
        self.assertEqual(list(case.modules.values_list("position", flat=True)), [0, 1])
        self.assertEqual([module.fields.count() for module in case.modules.all()], [1, 1])

    def test_student_snapshots_and_existing_cases_survive_source_changes(self):
        dossier, templates = self.new_bundle()
        existing = self.new_case("DYNAMIC-EXISTING")
        copied_modules = copy_library_dossier_to_case(dossier, existing)
        copied_modules[0].base_data = {"notitie": "Bestaande voorinvulling"}
        copied_modules[0].save(update_fields=["base_data"])
        student = get_user_model().objects.create_user("dynamic-student")
        first, _ = start_student_case(existing, student)
        response = first.module_responses.get(module=copied_modules[0])
        original_schema = deepcopy(response.schema)
        original_data = deepcopy(response.data)
        templates[0].fields.update(label="Nieuw bronlabel")
        templates[0].title = "Nieuwe brontitel"
        templates[0].save()
        new = self.new_case("DYNAMIC-NEW")
        copy_library_dossier_to_case(dossier, new)
        self.assertEqual(new.modules.first().title, "Nieuwe brontitel")
        response.refresh_from_db()
        self.assertEqual(response.schema, original_schema)
        self.assertEqual(response.data, original_data)
        self.assertEqual(existing.modules.first().title, "Intake")
        self.assertEqual(existing.modules.count(), 2)
        self.assertEqual(first.module_responses.count(), 2)
        again, created = start_student_case(existing, student)
        self.assertFalse(created)
        self.assertEqual(again.pk, first.pk)

    def test_empty_case_cannot_be_published_before_choosing_modules(self):
        case = self.new_case()
        Assignment.objects.create(case=case, title="Opdracht", content="Test", phase="Eerste")
        url = reverse("dossier:teacher_case_transition", args=[case.pk])
        self.client.post(url, {"action": "publish"})
        case.refresh_from_db()
        self.assertEqual(case.status, Case.Status.DRAFT)
        dossier, _ = self.new_bundle()
        copy_library_dossier_to_case(dossier, case)
        self.client.post(url, {"action": "publish"})
        case.refresh_from_db()
        self.assertEqual(case.status, Case.Status.PUBLISHED)

    def test_auto_add_setting_is_absent_for_admin_and_teacher(self):
        admin = get_user_model().objects.create_superuser("dynamic-admin", password="test-only")
        for user in (self.teacher, admin):
            with self.subTest(role=user.username):
                self.client.force_login(user)
                page = self.client.get(reverse("dossier:library_create"))
                self.assertNotIn("is_fixed", page.context["form"].fields)
                self.assertNotContains(page, "Automatisch toevoegen")

    def test_demo_uses_its_own_selected_bundle_and_is_repeatable(self):
        for _ in range(2):
            call_command("seed_demo", stdout=StringIO())
        case = Case.objects.get(patient__reference="VRK-IC1-MIA")
        dossier = LibraryDossier.objects.get(title="Demo: opname")
        self.assertEqual(list(case.modules.values_list("source_template_id", flat=True)),
                         list(dossier.module_entries.values_list("template_id", flat=True)))
        self.assertEqual(case.modules.count(), 1)
        self.assertEqual(LibraryTemplate.objects.count(), 1)
