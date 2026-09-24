from django.core.management.base import BaseCommand
from dossier.models import Assignment, Case, Module, Patient


class Command(BaseCommand):
    def handle(self, *args, **options):
        patient, _ = Patient.objects.update_or_create(
            reference="VRK-IC1-MIA",
            defaults={
                "name": "Vanbelle, Mia",
                "image": "/static/mia-avatar.svg",
                "context": "Vives_Ziekenhuis - Moeder - Kind - 2de - 3de lijn, Verloskamer, Vroedvrouw",
            },
        )
        case, _ = Case.objects.update_or_create(
            title="VRK IC1 - Vanbelle Mia",
            defaults={"patient": patient, "course": "Vroedkunde Brugge_OLF1_IC 1", "published": True},
        )
        titles = [
            "Dashboard", "Anamnese", "Zwangerschapsdossier", "Partusdossier", "MIC dossier",
            "Postpartumdossier", "Kort verslag graviditeit, partus en postpartum", "NICU / N*-dossier",
            "Screening emotioneel welzijn", "Klinisch redeneerplan", "Uitwerking opdracht",
        ]
        for position, title in enumerate(titles):
            Module.objects.update_or_create(case=case, title=title, defaults={"position": position})
        Assignment.objects.update_or_create(case=case, position=1, defaults={
            "phase": "Opdracht 1", "title": "Diagnostische fase: Gegevens verzamelen + (voorlopige) diagnose vaststellen", "status": "resubmit",
            "content": "1. Welke gegevens uit de omschrijving van de situatie zijn prioritair?\n\n2. Welke voorlopige potentiële of dreigende vroedkundige diagnose(s) stel je vast op basis van deze gegevens?\n\n3. Welke bijkomende gegevens verzamel je uit het dossier (anamnese)?\n\n4. Welke bijkomende gegevens verzamel je door het opnamegesprek?\n\n5. Welke bijkomende gegevens verzamel je door het opname-onderzoek?\n\nBeantwoord de 5 vragen in 1 registratie onder de functie 'Uitwerking opdracht.'",
        })
        Assignment.objects.update_or_create(case=case, position=2, defaults={
            "phase": "Opdracht 2", "title": "Planningsfase: Risicofactoren + definitieve diagnose vaststellen + opmaken van een zorgplan", "status": "todo",
            "content": "1. Welke risicofactoren stel je vast op basis van de bijkomende gegevensverzameling?\n\n2. Welke definitieve diagnoses stel je vast op basis van de bijkomende gegevensverzameling?\n\n3. Formuleer bij de definitieve diagnoses het verwachte resultaat.\n\n4. Formuleer telkens de bijhorende evaluatiecriteria waaraan je kan zien dat het resultaat is bereikt.\n\n5. Formuleer de vroedkundige interventies om het resultaat te bekomen.\n\n6. Welke bijkomende gegevens verzamel je tijdens het vervolggesprek en/of -onderzoek?\n\nBeantwoord de 6 vragen in 1 registratie onder de functie 'Uitwerking opdracht.'",
        })
        Assignment.objects.update_or_create(case=case, position=3, defaults={
            "phase": "Opdracht 3", "title": "Evaluatiefase: Resultaat evalueren", "status": "todo",
            "content": "Zijn de verwachte resultaten bereikt? Moet het zorgplan worden aangepast?\n\nBeantwoord de vraag in 1 registratie onder de functie 'Uitwerking opdracht.'",
        })
        self.stdout.write(self.style.SUCCESS("Voorbeeldcasus klaar."))
