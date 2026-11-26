from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_created_at(apps, schema_editor):
    ModuleResponse = apps.get_model("dossier", "ModuleResponse")
    for response in ModuleResponse.objects.all():
        response.created_at = response.updated_at
        response.save(update_fields=["created_at"])


def backfill_created_by(apps, schema_editor):
    ModuleResponse = apps.get_model("dossier", "ModuleResponse")
    for response in ModuleResponse.objects.select_related("student_case"):
        response.created_by_id = response.student_case.student_id
        response.save(update_fields=["created_by"])


class Migration(migrations.Migration):

    dependencies = [
        ("dossier", "0013_alter_managedquestion_image_alter_patient_image"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="moduleresponse",
            name="unique_module_response",
        ),
        migrations.AddField(
            model_name="moduleresponse",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="module_responses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="moduleresponse",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.RunPython(
            backfill_created_at, migrations.RunPython.noop, elidable=True
        ),
        migrations.RunPython(
            backfill_created_by, migrations.RunPython.noop, elidable=True
        ),
        migrations.AlterModelOptions(
            name="moduleresponse",
            options={"ordering": ["position", "created_at", "id"]},
        ),
    ]
