from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Controleer de actieve centrale MySQL-verbinding."

    def handle(self, *args, **options):
        if connection.vendor != "mysql":
            raise CommandError(
                f"Ongeldige database-engine: {connection.vendor}. MySQL is verplicht."
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT VERSION(), @@SESSION.sql_mode, "
                "@@SESSION.transaction_isolation, "
                "@@character_set_connection, DATABASE()"
            )
            version, sql_mode, isolation, charset, database = cursor.fetchone()

        self.stdout.write(f"Database: {database}")
        self.stdout.write(f"MySQL: {version}")
        self.stdout.write(f"Tekenset: {charset}")
        self.stdout.write(f"Isolatie: {isolation}")
        self.stdout.write(f"SQL-mode: {sql_mode}")
        self.stdout.write(self.style.SUCCESS("Centrale MySQL-verbinding is in orde."))
