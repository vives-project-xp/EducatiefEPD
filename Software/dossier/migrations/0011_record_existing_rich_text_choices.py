from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dossier", "0010_remove_librarytemplate_is_fixed")]

    # Record the rich-text type already present in the text-editor model code.
    operations = [
        migrations.AlterField(
            model_name=model_name,
            name="field_type",
            field=models.CharField(max_length=24, choices=[
                ("short_text", "Korte tekst"), ("long_text", "Vrije tekst"),
                ("number", "Numeriek veld"), ("date", "Datum"),
                ("datetime", "Datum en tijd"), ("select", "Keuzelijst"),
                ("observation", "Observaties"), ("matrix", "Matrix"),
                ("rich_text", "Opgemaakte tekst"),
            ]),
        )
        for model_name in ("libraryfield", "modulefield")
    ]
