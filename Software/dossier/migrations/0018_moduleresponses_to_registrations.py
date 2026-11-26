from django.db import migrations


def forwards(apps, schema_editor):
    ModuleResponse = apps.get_model("dossier", "ModuleResponse")
    Registration = apps.get_model("dossier", "Registration")
    database = schema_editor.connection.alias
    batch = []
    for response in ModuleResponse.objects.using(database).select_related("student_case").iterator():
        batch.append(Registration(
            case_id=response.student_case.case_id,
            module_id=response.module_id,
            title=response.title,
            kind=response.kind,
            instructions=response.instructions,
            position=response.position,
            schema=response.schema,
            data=response.data,
            status=response.status,
            author_id=response.created_by_id or response.student_case.student_id,
            author_role="student",
            created_at=response.created_at,
        ))
        if len(batch) >= 500:
            Registration.objects.using(database).bulk_create(batch)
            batch = []
    if batch:
        Registration.objects.using(database).bulk_create(batch)


class Migration(migrations.Migration):
    dependencies = [("dossier", "0017_registration")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]