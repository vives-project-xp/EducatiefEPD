from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dossier", "0014_managedquestion_matrix_definition_and_more"),
    ]

    operations = [
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
                    ("matrix", "Matrix"),
                    ("multipleChoice", "Meerkeuze"),
                    ("text", "Tekst"),
                    ("observation", "Observaties"),
                ],
                default="text",
                max_length=24,
            ),
        ),
    ]
