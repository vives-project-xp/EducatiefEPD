from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from epd.models import BasisCasus, BasisCasusData, FictievePatient, User


class Command(BaseCommand):
    help = "Maak lokale demo-gebruikers en een voorbeeldcasus aan."

    def handle(self, *args, **options):
        docent, _ = User.objects.get_or_create(username="docent", defaults={"first_name": "Demo", "last_name": "Docent", "role": User.Role.DOCENT})
        docent.role = User.Role.DOCENT
        docent.set_password("docent123")
        docent.save()

        student, _ = User.objects.get_or_create(username="student", defaults={"first_name": "Demo", "last_name": "Student", "role": User.Role.STUDENT})
        student.role = User.Role.STUDENT
        student.set_password("student123")
        student.save()

        patient, _ = FictievePatient.objects.get_or_create(
            voornaam="Emma",
            achternaam="Peeters",
            defaults={
                "geboortedatum": date(1994, 5, 12),
                "biologisch_geslacht": FictievePatient.BiologicalSex.VROUW,
                "context_beschrijving": "VIVES Ziekenhuis · Moeder-kind",
            },
        )
        patient.context_beschrijving = "VIVES Ziekenhuis · Moeder-kind"
        patient.save(update_fields=["context_beschrijving"])
        casus, created = BasisCasus.objects.get_or_create(
            docent=docent,
            patient=patient,
            defaults={
                "titel": "Opvolging tijdens de arbeid",
                "inleiding": "Emma wordt opgenomen op de materniteit voor opvolging tijdens de arbeid.",
                "leerdoelen": "Je verzamelt relevante gegevens en onderbouwt je vroedkundige observaties.",
                "afdeling": "Materniteit",
                "rol": "Vroedvrouw",
                "opdracht_instructie": "Observeer de parameters en registreer je klinische redenering.",
                "publicatie_status": BasisCasus.PublicationStatus.OPEN,
                "inlever_deadline": timezone.now() + timedelta(days=14),
            },
        )
        casus.inleiding = "Emma wordt opgenomen op de materniteit voor opvolging tijdens de arbeid."
        casus.leerdoelen = "Je verzamelt relevante gegevens en onderbouwt je vroedkundige observaties."
        casus.afdeling = "Materniteit"
        casus.rol = "Vroedvrouw"
        casus.save(update_fields=["inleiding", "leerdoelen", "afdeling", "rol"])
        if created:
            BasisCasusData.objects.create(casus=casus, sjabloon_onderdeel_id="parameters", waarde={"bloeddruk": "120/80", "pols": 82, "temperatuur": 36.8})
            BasisCasusData.objects.create(casus=casus, sjabloon_onderdeel_id="medicatie", waarde={"actief": [], "allergieën": []})
        self.stdout.write(self.style.SUCCESS("Demo klaar: docent/docent123 en student/student123"))
