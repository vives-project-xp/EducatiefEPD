from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dossier", "0013_remove_broken_function_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedquestion",
            name="matrix_definition",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="managedquestion",
            name="field_type",
            field=models.CharField(
                choices=[
                    ("image", "Afbeelding weergeven"),
                    ("link", "Hyperlink"),
                    ("info", "Toelichting"),
                    ("imageUpload", "Afbeelding uploaden"),
                    ("fileUpload", "Bestand uploaden"),
                    ("date", "Datum"),
                    ("dateTime", "Datum en tijd"),
                    ("number", "Getal"),
                    ("matrix", "Matrix (maximaal 2)"),
                    ("multipleChoice", "Meerkeuze"),
                    ("text", "Tekst"),
                    ("observation", "Observaties"),
                ],
                default="text",
                max_length=24,
            ),
        ),
    ]
