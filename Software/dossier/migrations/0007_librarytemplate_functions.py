from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dossier", "0006_library_template_seed_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="librarytemplate",
            name="functions",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
