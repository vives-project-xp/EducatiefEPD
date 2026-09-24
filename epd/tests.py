from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import BasisCasus, BasisCasusData, FictievePatient, StudentUitwerking, StudentUitwerkingData, User


class CaseWorkflowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username="student", password="test", role=User.Role.STUDENT)
        self.other_student = User.objects.create_user(username="other", password="test", role=User.Role.STUDENT)
        docent = User.objects.create_user(username="docent", password="test", role=User.Role.DOCENT)
        patient = FictievePatient.objects.create(
            voornaam="Test", achternaam="Patiënt", geboortedatum=date(1990, 1, 1), biologisch_geslacht="vrouw"
        )
        self.casus = BasisCasus.objects.create(
            docent=docent,
            patient=patient,
            titel="Testcasus",
            opdracht_instructie="Registreer de meting.",
            publicatie_status=BasisCasus.PublicationStatus.OPEN,
            inlever_deadline=timezone.now() + timedelta(days=1),
        )
        BasisCasusData.objects.create(casus=self.casus, sjabloon_onderdeel_id="parameters", waarde={"pols": 80})
        self.client.login(username="student", password="test")

    def test_briefing_does_not_create_workspace(self):
        response = self.client.get(reverse("casus_overzicht", args=[self.casus.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Casus briefing")
        self.assertFalse(StudentUitwerking.objects.filter(student=self.student, casus=self.casus).exists())

    def test_open_dossier_creates_and_clones_workspace(self):
        response = self.client.get(reverse("open_dossier", args=[self.casus.id]))
        uitwerking = StudentUitwerking.objects.get(student=self.student, casus=self.casus)
        self.assertRedirects(response, reverse("uitwerking", args=[uitwerking.id]))
        self.assertEqual(StudentUitwerkingData.objects.get(uitwerking=uitwerking).waarde, {"pols": 80})

    def test_dashboard_has_briefing_and_dossier_actions(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, reverse("casus_overzicht", args=[self.casus.id]))
        self.assertContains(response, reverse("open_dossier", args=[self.casus.id]))

    def test_start_clones_all_case_data_and_is_idempotent(self):
        response = self.client.get(reverse("start_casus", args=[self.casus.id]))
        self.assertEqual(response.status_code, 302)
        uitwerking = StudentUitwerking.objects.get(student=self.student, casus=self.casus)
        self.assertEqual(StudentUitwerkingData.objects.get(uitwerking=uitwerking).waarde, {"pols": 80})
        self.client.get(reverse("start_casus", args=[self.casus.id]))
        self.assertEqual(StudentUitwerking.objects.filter(student=self.student, casus=self.casus).count(), 1)
        self.assertEqual(StudentUitwerkingData.objects.filter(uitwerking=uitwerking).count(), 1)

    def test_submitting_makes_workspace_read_only(self):
        self.client.get(reverse("start_casus", args=[self.casus.id]))
        uitwerking = StudentUitwerking.objects.get(student=self.student, casus=self.casus)
        response = self.client.post(reverse("submit_uitwerking", args=[uitwerking.id]))
        self.assertRedirects(response, reverse("dashboard"))
        uitwerking.refresh_from_db()
        self.assertEqual(uitwerking.status, StudentUitwerking.Status.INGELEVERD)
        response = self.client.post(reverse("uitwerking", args=[uitwerking.id]), {"data-1-waarde": '{"pols": 99}'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StudentUitwerkingData.objects.get(uitwerking=uitwerking).waarde, {"pols": 80})

    def test_student_cannot_view_another_students_workspace(self):
        uitwerking = StudentUitwerking.objects.create(student=self.other_student, casus=self.casus)
        response = self.client.get(reverse("uitwerking", args=[uitwerking.id]))
        self.assertEqual(response.status_code, 404)
