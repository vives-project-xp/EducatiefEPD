from django.core.management.base import BaseCommand

from dossier.models import Case
from dossier.services import create_case_structure, ensure_default_templates


class Command(BaseCommand):
    help = "Initialiseer de centraal beheerde dossierstructuur."

    def handle(self, *args, **options):
        ensure_default_templates()
        for case in Case.objects.all():
            create_case_structure(case)
        self.stdout.write(self.style.SUCCESS("Platformstructuur is bijgewerkt."))
