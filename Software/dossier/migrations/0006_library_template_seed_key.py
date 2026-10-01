from django.db import migrations, models
from django.utils.text import slugify


DEFAULT_TITLES = [
    "Dashboard",
    "Anamnese",
    "Zwangerschapsdossier",
    "Partusdossier",
    "MIC dossier",
    "Postpartumdossier",
    "Kort verslag graviditeit, partus en postpartum",
    "NICU / N*-dossier",
    "Screening emotioneel welzijn",
    "Klinisch redeneerplan",
    "Uitwerking opdracht",
]


def identify_existing_defaults(apps, schema_editor):
    templates = apps.get_model("dossier", "LibraryTemplate").objects.using(
        schema_editor.connection.alias
    )
    for title in DEFAULT_TITLES:
        template = templates.filter(title=title, education__slug="vroedkunde").order_by("id").first()
        if template:
            template.seed_key = f"vroedkunde-{slugify(title)}"
            template.save(update_fields=["seed_key"])


class Migration(migrations.Migration):
    dependencies = [("dossier", "0005_oidc_education_groups")]

    operations = [
        migrations.AddField(
            model_name="librarytemplate",
            name="seed_key",
            field=models.SlugField(blank=True, editable=False, max_length=80, null=True, unique=True),
        ),
        migrations.RunPython(identify_existing_defaults, migrations.RunPython.noop),
    ]
