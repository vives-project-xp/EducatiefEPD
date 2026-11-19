from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dossier", "0010_librarytemplatefunction_casefunctionsnapshot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="libraryfield",
            name="field_type",
            field=models.CharField(
                choices=[
                    ("short_text", "Korte tekst"),
                    ("long_text", "Vrije tekst"),
                    ("number", "Numeriek veld"),
                    ("date", "Datum"),
                    ("datetime", "Datum en tijd"),
                    ("select", "Keuzelijst"),
                    ("observation", "Observaties"),
                    ("matrix", "Matrix"),
                    ("rich_text", "Opgemaakte tekst"),
                ],
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="modulefield",
            name="field_type",
            field=models.CharField(
                choices=[
                    ("short_text", "Korte tekst"),
                    ("long_text", "Vrije tekst"),
                    ("number", "Numeriek veld"),
                    ("date", "Datum"),
                    ("datetime", "Datum en tijd"),
                    ("select", "Keuzelijst"),
                    ("observation", "Observaties"),
                    ("matrix", "Matrix"),
                    ("rich_text", "Opgemaakte tekst"),
                ],
                max_length=24,
            ),
        ),
    ]
