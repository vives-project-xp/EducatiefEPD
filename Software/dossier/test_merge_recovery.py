import base64
from io import BytesIO
import json

from docx import Document

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .forms import LibraryDossierForm, PatientForm
from .models import (
    Case, Education, FunctionDefinition, LibraryDossier, LibraryTemplate,
    ManagedForm, ManagedQuestion, Patient, Profile,
)
from .test_fixtures import create_library_fixtures


@override_settings(SECURE_SSL_REDIRECT=False)
class MergeRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_library_fixtures()
        cls.education = Education.objects.get(slug="vroedkunde")
        cls.teacher = get_user_model().objects.create_user("merge-teacher")
        cls.teacher.epd_profile.role = Profile.Role.TEACHER
        cls.teacher.epd_profile.education = cls.education
        cls.teacher.epd_profile.save()
        cls.function = FunctionDefinition.objects.create(
            title="Intake", kind=FunctionDefinition.Kind.GROUP
        )
        cls.form = ManagedForm.objects.create(function=cls.function, title="Eerste formulier")
        cls.question = ManagedQuestion.objects.create(form=cls.form, question="Behoud deze vraag")

    def setUp(self):
        self.client.force_login(self.teacher)

    def post_json(self, route, payload, args=None):
        return self.client.post(
            reverse(f"dossier:{route}", args=args),
            json.dumps(payload), content_type="application/json",
        )

    def test_function_apis_reject_non_object_json_without_changing_forms(self):
        for payload in ([], None, "invalid", 1):
            for route, args in (
                ("function_action", [self.function.pk]), ("function_trash_action", None)
            ):
                with self.subTest(route=route, payload=payload):
                    self.assertEqual(self.post_json(route, payload, args).status_code, 400)
        self.assertTrue(ManagedQuestion.objects.filter(pk=self.question.pk).exists())

    def test_function_apis_reject_invalid_ids_and_duplicate_order(self):
        url_args = [self.function.pk]
        for value in ("invalid", None, True, -1):
            with self.subTest(value=value):
                response = self.post_json("function_action", {
                    "action": "save_form", "formId": value, "title": "Changed", "questions": [],
                }, url_args)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.post_json("function_trash_action", {
                    "action": "restore", "functionId": value,
                }).status_code, 400)
        response = self.post_json("function_action", {
            "action": "reorder_forms", "formIds": [self.form.pk, self.form.pk],
        }, url_args)
        self.assertEqual(response.status_code, 400)
        self.form.refresh_from_db()
        self.assertEqual(self.form.position, 0)
        self.assertTrue(self.form.questions.filter(pk=self.question.pk).exists())

    def test_direct_function_pages_supply_csrf_for_ajax(self):
        for route, args in (
            ("function_management", None), ("function_detail", [self.function.pk]),
            ("function_deleted", None),
        ):
            with self.subTest(route=route):
                client = Client(enforce_csrf_checks=True)
                client.force_login(self.teacher)
                self.assertEqual(client.get(reverse(f"dossier:{route}", args=args)).status_code, 200)
                token = client.cookies["csrftoken"].value
                response = client.post(
                    reverse("dossier:function_action", args=[self.function.pk]),
                    json.dumps({"action": "rename", "title": "Intake"}),
                    content_type="application/json", HTTP_X_CSRFTOKEN=token,
                )
                self.assertEqual(response.status_code, 200)

    def test_cleaned_choice_and_matrix_lists_must_remain_nonempty(self):
        for field in (
            {"type": "select", "options": ["   "]},
            {"type": "matrix", "rows": ["   "], "columns": ["Column"]},
            {"type": "select", "options": [12]},
        ):
            with self.subTest(field=field):
                form = LibraryDossierForm(data={
                    "title": "Bundle", "education": self.education.pk,
                    "new_modules": json.dumps([{
                        "title": "Module", "category": "module",
                        "fields": [{"label": "Choice", **field}],
                    }]),
                })
                self.assertFalse(form.is_valid())
                self.assertIn("new_modules", form.errors)

    def test_deleting_unused_archived_case_releases_patient_reference(self):
        patient = Patient.objects.create(name="Fictief", reference="MERGE-DELETE")
        case = Case.objects.create(
            title="Verwijderbaar", patient=patient, education=self.education,
            created_by=self.teacher, status=Case.Status.ARCHIVED,
        )
        response = self.client.post(reverse("dossier:teacher_case_delete", args=[case.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Patient.objects.filter(pk=patient.pk).exists())
        form = PatientForm(data={"name": "Nieuw fictief", "reference": "MERGE-DELETE", "gender": "unknown"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_library_filters_have_independent_querysets(self):
        LibraryDossier.objects.create(title="Intakebundel", education=self.education)
        LibraryDossier.objects.create(title="Andere bundel", education=self.education)
        response = self.client.get(reverse("dossier:library_list"), {
            "dossier_q": "Intake", "q": "Anamnese", "category": "questionnaire",
            "education": "Vroedkunde", "theme": "Opname",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item.title for item in response.context["dossiers"]], ["Intakebundel"])
        self.assertEqual([item.title for item in response.context["available_templates"]], ["Anamnese"])
        self.assertContains(response, 'class="library-component-management-details" open')
        self.assertContains(response, reverse("dossier:function_management"))

    def test_shared_dossier_access_rule_preserves_education_restrictions(self):
        other = Education.objects.create(name="Andere opleiding", slug="andere")
        foreign = LibraryDossier.objects.create(title="Afgeschermd", education=other)
        response = self.client.get(reverse("dossier:library_list"))
        self.assertNotIn(foreign, list(response.context["dossiers"]))
        for route in ("library_dossier_edit", "library_dossier_copy", "library_dossier_archive"):
            with self.subTest(route=route):
                method = self.client.get if route.endswith("edit") else self.client.post
                self.assertEqual(method(reverse(f"dossier:{route}", args=[foreign.pk])).status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, LibraryDossier.Status.ACTIVE)

    def test_docx_export_and_import_preserve_formatted_content(self):
        response = self.client.post(reverse("dossier:export_docx"), {
            "html": "<p><strong>Voorinvulling</strong> voor de casus.</p>",
            "filename": "Les casus.docx",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="Les_casus.docx"')
        document = Document(BytesIO(response.content))
        self.assertIn("Voorinvulling voor de casus.", "\n".join(p.text for p in document.paragraphs))
        upload = SimpleUploadedFile("les.docx", response.content, content_type=response["Content-Type"])
        imported = self.client.post(reverse("dossier:import_docx"), {"file": upload})
        self.assertEqual(imported.status_code, 200)
        self.assertIn("<strong>Voorinvulling</strong>", imported.json()["html"])

    def test_function_save_accepts_image_and_link_and_rejects_invalid_base64_atomically(self):
        image = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")
        payload = {
            "action": "save_form", "formId": self.form.pk, "title": "Intake",
            "questions": [
                {"fieldType": ManagedQuestion.FieldType.IMAGE, "image": image, "url": "https://example.org/casus"},
            ],
        }
        response = self.post_json("function_action", payload, [self.function.pk])
        self.assertEqual(response.status_code, 200)
        question = self.form.questions.get()
        self.assertEqual(question.image, image)
        self.assertEqual(question.url, "https://example.org/casus")
        payload["questions"][0]["image"] = "data:image/png;base64,%%%"
        response = self.post_json("function_action", payload, [self.function.pk])
        self.assertEqual(response.status_code, 400)
        question.refresh_from_db()
        self.assertEqual(question.image, image)
        self.assertEqual(self.form.questions.get().pk, question.pk)
