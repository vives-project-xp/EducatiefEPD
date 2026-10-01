from django.core.management.base import BaseCommand

from dossier.services import ensure_default_templates


class Command(BaseCommand):
    help = "Initialiseer de centraal beheerde dossierstructuur."

    def handle(self, *args, **options):
        ensure_default_templates()
        self.stdout.write(self.style.SUCCESS("Platformstructuur is bijgewerkt."))
