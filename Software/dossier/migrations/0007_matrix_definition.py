from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dossier", "0006_library_template_seed_key")]
    operations = [
        migrations.AddField(model_name=name, name="matrix_definition", field=models.JSONField(blank=True, default=dict))
        for name in ("libraryfield", "modulefield")
    ]
