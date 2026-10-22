from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dossier", "0012_merge_matrix_main"),
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
                    ("date", "Datum"),
                    ("dateTime", "Datum en tijd"),
                    ("number", "Getal"),
                    ("matrix", "Matrix (maximaal 2)"),
                    ("multipleChoice", "Meerkeuze"),
                    ("text", "Tekst"),
                    ("time", "Tijd"),
                ],
                default="text",
                max_length=24,
            ),
        ),
    ]
