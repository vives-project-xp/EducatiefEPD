from django.db import migrations, models


def backfill_snapshot_source_functions(apps, schema_editor):
    Snapshot = apps.get_model("dossier", "CaseFunctionSnapshot")
    ManagedForm = apps.get_model("dossier", "ManagedForm")
    FunctionDefinition = apps.get_model("dossier", "FunctionDefinition")

    form_owners = dict(ManagedForm.objects.values_list("id", "function_id"))
    functions_by_name = {}
    for function_id, title, kind in FunctionDefinition.objects.values_list(
        "id", "title", "kind"
    ):
        functions_by_name.setdefault((title, kind), []).append(function_id)

    for snapshot in Snapshot.objects.filter(source_function_id__isnull=True).iterator():
        definition = snapshot.definition if isinstance(snapshot.definition, dict) else {}
        form_function_ids = {
            form_owners[int(form["id"])]
            for form in definition.get("forms", [])
            if isinstance(form, dict)
            and str(form.get("id", "")).isdigit()
            and int(form["id"]) in form_owners
        }
        if len(form_function_ids) == 1:
            snapshot.source_function_id = form_function_ids.pop()
        else:
            candidates = functions_by_name.get((snapshot.title, snapshot.kind), [])
            if len(candidates) == 1:
                snapshot.source_function_id = candidates[0]
        if snapshot.source_function_id is not None:
            snapshot.save(update_fields=["source_function_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("dossier", "0019_functiondefinition_locked_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="casefunctionsnapshot",
            name="source_function_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="casefunctionsnapshot",
            name="active",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(
            backfill_snapshot_source_functions,
            migrations.RunPython.noop,
        ),
    ]
