from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import PatientForm
from .models import Case, Education, Patient, Profile, StudentCase


def photo(name="photo.png", color="blue"):
    content = BytesIO()
    Image.new("RGB", (8, 8), color).save(content, "PNG")
    return SimpleUploadedFile(name, content.getvalue(), content_type="image/png")


@override_settings(SECURE_SSL_REDIRECT=False)
class PatientImageTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings_override = override_settings(MEDIA_ROOT=directory.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.education = Education.objects.get(slug="vroedkunde")
        self.teacher = get_user_model().objects.create_user("photo-teacher")
        self.teacher.epd_profile.role = Profile.Role.TEACHER
        self.teacher.epd_profile.save()
        self.patient = Patient.objects.create(
            name="Fictieve patiënt", reference="PHOTO-TEST", image=photo(), created_by=self.teacher,
        )
        self.case = Case.objects.create(
            title="Fotocasus", patient=self.patient, education=self.education,
            course="Test", created_by=self.teacher,
        )
        self.original_name = self.patient.image.name
        self.storage = self.patient.image.storage
        student = get_user_model().objects.create_user("photo-student")
        self.student_case = StudentCase.objects.create(
            case=self.case, student=student, patient_image=self.patient.image.url,
        )
        self.original_snapshot_url = self.student_case.patient_image
        self.url = reverse("dossier:teacher_case_edit", args=[self.case.pk])
        self.client.force_login(self.teacher)

    def data(self, **changes):
        return {
            "patient-name": self.patient.name, "patient-reference": self.patient.reference,
            "patient-gender": Patient.Gender.UNKNOWN, "patient-context": "Testcontext",
            "case-title": self.case.title, "case-education": self.education.pk, "case-course": "Test",
            **changes,
        }

    def assert_original_file_and_snapshot_exist(self):
        self.assertTrue(self.storage.exists(self.original_name))
        self.student_case.refresh_from_db()
        self.assertEqual(self.student_case.patient_image, self.original_snapshot_url)

    def test_edit_page_renders_preview_and_buttons_without_clear_checkbox(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Afbeelding wijzigen")
        self.assertContains(response, "Afbeelding verwijderen")
        self.assertContains(response, f'src="{self.patient.image.url}"')
        self.assertContains(response, 'name="patient-image-clear"')
        self.assertNotContains(response, 'type="checkbox"')
        self.assertContains(response, "patient-image.js")

    def test_unchanged_form_keeps_existing_image(self):
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.image.name, self.original_name)
        self.assert_original_file_and_snapshot_exist()

    def test_removal_waits_for_valid_save_and_keeps_student_snapshot(self):
        response = self.client.post(self.url, self.data(**{
            "patient-name": "", "patient-image-clear": "on",
        }))
        self.assertEqual(response.status_code, 200)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.image.name, self.original_name)
        self.assertContains(response, "De afbeelding wordt verwijderd wanneer je de wijzigingen bewaart.")
        self.assertContains(response, 'value="on" data-image-clear>')
        self.assert_original_file_and_snapshot_exist()

        self.assertEqual(self.client.post(self.url, self.data(**{"patient-image-clear": "on"})).status_code, 302)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.image)
        self.assert_original_file_and_snapshot_exist()

    def test_replacement_keeps_original_file_and_student_snapshot(self):
        response = self.client.post(self.url, self.data(**{"patient-image": photo("replacement.png", "red")}))
        self.assertEqual(response.status_code, 302)
        self.patient.refresh_from_db()
        self.assertNotEqual(self.patient.image.name, self.original_name)
        self.assertTrue(self.storage.exists(self.patient.image.name))
        self.assert_original_file_and_snapshot_exist()

    def test_invalid_image_does_not_replace_existing_image(self):
        invalid = SimpleUploadedFile("invalid.png", b"not an image", content_type="image/png")
        response = self.client.post(self.url, self.data(**{"patient-image": invalid}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("image", response.context["patient_form"].errors)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.image.name, self.original_name)
        self.assert_original_file_and_snapshot_exist()

    def test_conflicting_upload_and_remove_are_rejected(self):
        response = self.client.post(self.url, self.data(**{
            "patient-image": photo(), "patient-image-clear": "on",
        }))
        self.assertEqual(response.status_code, 200)
        self.assertIn("image", response.context["patient_form"].errors)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.image.name, self.original_name)

    def test_existing_upload_size_limit_is_preserved(self):
        upload = photo()
        upload.size = 10 * 1024 * 1024 + 1
        form = PatientForm(self.data(), files={"patient-image": upload}, instance=self.patient, prefix="patient")
        self.assertFalse(form.is_valid())
        self.assertIn("De foto mag maximaal 10 MB groot zijn.", form.errors["image"])
