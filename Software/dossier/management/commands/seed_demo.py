from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from dossier.models import Assignment, Case, Patient, Profile
from dossier.services import create_case_structure


class Command(BaseCommand):
    help = "Maak lokale demo-accounts en een voorbeeldcasus aan."

    def handle(self, *args, **options):
        user_model = get_user_model()
        teacher, _ = user_model.objects.get_or_create(
            username="docent", defaults={"first_name": "Demo", "last_name": "Docent"}
        )
        teacher.set_password("docent123")
        teacher.save()
        Profile.objects.update_or_create(
            user=teacher, defaults={"role": Profile.Role.TEACHER, "education": "Vroedkunde"}
        )

        student, _ = user_model.objects.get_or_create(
            username="student", defaults={"first_name": "Demo", "last_name": "Student"}
        )
        student.set_password("student123")
        student.save()
        Profile.objects.update_or_create(user=student, defaults={"role": Profile.Role.STUDENT})

        admin, _ = user_model.objects.get_or_create(
            username="beheerder",
            defaults={"first_name": "Demo", "last_name": "Beheerder", "is_staff": True, "is_superuser": True},
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password("beheerder123")
        admin.save()
        Profile.objects.update_or_create(user=admin, defaults={"role": Profile.Role.ADMIN})

        patient, _ = Patient.objects.update_or_create(
            reference="VRK-IC1-MIA",
            defaults={
                "name": "Vanbelle, Mia",
                "gender": Patient.Gender.FEMALE,
                "image": "/static/mia-avatar.svg",
                "context": "Vives Ziekenhuis - Moeder en Kind - Verloskamer",
                "created_by": teacher,
            },
        )
        case, _ = Case.objects.update_or_create(
            patient=patient,
            defaults={
                "title": "VRK IC1 - Vanbelle Mia",
                "course": "Vroedkunde Brugge - OLF1 - IC 1",
                "introduction": (
                    "Mia meldt zich aan op de verlosafdeling met spontane arbeid. "
                    "Ze is ongerust en denkt dat ze vruchtwater verliest."
                ),
                "learning_objectives": "De student maakt een zorgplan op volgens het klinisch redeneerplan.",
                "created_by": teacher,
            },
        )
        create_case_structure(case)

        anamnese = case.modules.filter(title="Anamnese").first()
        if anamnese:
            field_by_label = {field.label: field for field in anamnese.fields.all()}
            anamnese.base_data = {
                field_by_label["Reden van opname"].key: "Spontane arbeid met vermoeden van gebroken vliezen.",
                field_by_label["Huidige klachten en symptomen"].key: "Hevige pijnlijke contracties en mogelijk vruchtwaterverlies.",
                field_by_label["Medische voorgeschiedenis"].key: "Geen relevante voorgeschiedenis gekend.",
            }
            anamnese.save(update_fields=["base_data"])

        assignments = [
            ("Opdracht 1", "Diagnostische fase: gegevens verzamelen en een voorlopige diagnose vaststellen", "Welke gegevens zijn prioritair? Welke bijkomende gegevens verzamel je uit het dossier, het opnamegesprek en het onderzoek?"),
            ("Opdracht 2", "Planningsfase: risicofactoren, diagnose en zorgplan", "Formuleer de definitieve diagnoses, verwachte resultaten, evaluatiecriteria en interventies."),
            ("Opdracht 3", "Evaluatiefase: resultaat evalueren", "Zijn de verwachte resultaten bereikt en moet het zorgplan worden aangepast?"),
        ]
        for position, (phase, title, content) in enumerate(assignments, start=1):
            Assignment.objects.update_or_create(
                case=case, position=position,
                defaults={"phase": phase, "title": title, "content": content},
            )

        case.publish()
        case.save()
        self.stdout.write(self.style.SUCCESS(
            "Demo klaar: docent/docent123, student/student123, beheerder/beheerder123"
        ))
