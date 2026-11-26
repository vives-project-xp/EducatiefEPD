from django.db import migrations


class Migration(migrations.Migration):
    """Voegt de docentfeedback-tak (0014_docent_feedback) en de registratie-tak
    (0014–0017) samen. Beide takken raken verschillende kolommen."""

    dependencies = [
        ("dossier", "0014_docent_feedback"),
        ("dossier", "0017_merge_20261126_1327"),
    ]

    operations = []
