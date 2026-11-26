from django.db import migrations, models


def copy_existing_source_data(apps, schema_editor):
    module_response = apps.get_model("dossier", "ModuleResponse")
    for response in module_response.objects.select_related("module").iterator():
        response.source_data = (response.module.base_data or {}) if response.module else {}
        response.save(update_fields=["source_data"])


class Migration(migrations.Migration):

    dependencies = [
        ("dossier", "0015_alter_managedquestion_field_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="moduleresponse",
            name="source_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(copy_existing_source_data, migrations.RunPython.noop),
    ]
