from django.db import migrations, models


def populate_source_template_id_snapshot(apps, schema_editor):
    ModuleResponse = apps.get_model("dossier", "ModuleResponse")
    database = schema_editor.connection.alias
    responses = ModuleResponse.objects.using(database).filter(
        module__source_template__isnull=False,
    ).values_list("pk", "module__source_template_id")
    for response_id, template_id in responses.iterator():
        ModuleResponse.objects.using(database).filter(pk=response_id).update(
            source_template_id_snapshot=template_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("dossier", "0013_alter_managedquestion_image_alter_patient_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="moduleresponse",
            name="source_template_id_snapshot",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(
            populate_source_template_id_snapshot,
            migrations.RunPython.noop,
        ),
    ]
